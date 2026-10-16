"""Content-pack submission, review and signing — no third-party dependencies.

Why this exists: a pack is data, and the point of data is that other people can
author it. Without a submission path, "community content" means "send the maintainer
a patch", and without a signature a pack cannot be told apart from a tampered copy of
a pack. See docs/records/platform-research-2026-10/03-content-pipeline.md for the
survey this follows.

Three properties this module is built around:

* **The digest is over content, not over bytes-on-disk.** It hashes the manifest's
  semantic fields plus every content file, with keys sorted, so re-indenting a JSON
  file or reordering object keys does not invalidate a signature. Otherwise every
  formatting change would read as tampering and the signature would be ignored.
* **Signing never has to be trusted silently.** The signature names the algorithm and
  the key used, and verification compares that key against a keyring. A pack signed by
  an unknown key is *rejected* under a required policy rather than accepted because
  "there is a signature".
* **Absent is not the same as invalid.** A development pack has no signature at all,
  which is fine; a pack whose signature does not match its content is a hard error even
  in the most permissive policy, because that is what tampering looks like.

Cryptography note: this uses HMAC-SHA256, i.e. a **shared secret**. Python 3.14 has no
Ed25519 in the standard library (``crypto`` arrives in 3.15) and this project has no
third-party dependencies, so the choice was between HMAC over an audited primitive and
a hand-written curve implementation. A hand-written Ed25519 would be the wrong kind of
clever: it is where subtle, silent, security-relevant bugs live. HMAC fits the actual
threat — a maintainer and a contributor who can exchange a key out of band, and a
reviewer who must detect a pack that changed after signing. Asymmetric signatures are
the better fit once a key can be built without new dependencies; ``ALGORITHM`` and the
signature file's ``algorithm`` field exist so that switch does not break old packs.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from puzzle_service.content import (
    ContentPack,
    ContentPackError,
    ENGINE_VERSION,
    PACK_FORMAT_VERSION,
    load_pack,
    validate_pack,
)

__all__ = [
    "ALGORITHM",
    "KEY_BYTES",
    "SignatureError",
    "SubmissionError",
    "PolicyError",
    "pack_digest",
    "content_digest",
    "sign_pack",
    "verify_signature",
    "generate_key",
    "load_keyring",
    "Submission",
    "load_submission",
    "review",
    "accept",
    "Policy",
]

#: Signature algorithm id. Stored in every signature file.
ALGORITHM = "hmac-sha256"

#: Key length in bytes. 32 bytes of entropy, hex-encoded on disk.
KEY_BYTES = 32

#: Files a pack directory may contain. Anything else is reported, not copied.
CONTENT_FILES = (
    "manifest.json",
    "riddles.json",
    "hangman_words.json",
    "anagram_words.json",
    "word_ladders.json",
    "crosswords.json",
)

#: Signature file name. Never part of the digest (it signs the digest).
SIGNATURE_FILE = "signature.json"


class SubmissionError(Exception):
    """A submission directory is unusable."""


class SignatureError(SubmissionError):
    """A signature is present but does not verify."""


class PolicyError(SubmissionError):
    """The pack does not satisfy the signing policy in force."""


@dataclass
class Policy:
    """What verification requires.

    ``required`` defaults to ``False``: the shipped packs are maintainer-authored and
    unsigned, and refusing to load them would break the game to satisfy a policy
    nobody asked for. A reviewer or a strict deployment turns it on.
    """

    required: bool = False
    keyring: dict[str, str] = field(default_factory=dict)  # key_id -> label

    def known(self, key_id: str) -> bool:
        return key_id in self.keyring


# ---------------------------------------------------------------------------
# Digests
# ---------------------------------------------------------------------------


def content_digest(root: Path) -> str:
    """SHA-256 over every content file, order-independent and path-prefixed.

    Each entry contributes ``<relative path>\\0<sha256 of file bytes>\\n`` so that a
    file cannot be renamed without changing the digest, and the whole thing is sorted
    so that filesystem enumeration order does not matter.
    """
    entries: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == SIGNATURE_FILE:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append(f"{relative}\0{digest}\n")
    return hashlib.sha256("".join(entries).encode("utf-8")).hexdigest()


def pack_digest(pack: ContentPack) -> str:
    """SHA-256 over the pack's *semantics*: manifest fields plus each kind's items.

    Deliberately not the bytes of the files. Two packs that say the same thing in
    different formatting are the same pack, and a signature must survive a formatter.
    Items keep their order (order is observable — it changes which item a seeded draw
    reaches), but object keys within an item do not affect the result.
    """
    payload: dict[str, Any] = {
        "name": pack.name,
        "format_version": pack.manifest.get("format_version"),
        "languages": sorted(pack.languages),
        "content": {
            kind: _canonical(items) for kind, items in sorted(pack.content.items())
        },
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(value: Any) -> Any:
    """Recursively sort object keys so key order cannot change the digest."""
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# Keys and signatures
# ---------------------------------------------------------------------------


def key_id(secret_hex: str) -> str:
    """A public name for a key: derived from it, revealing nothing usable.

    ``key_id`` is what a keyring lists, what a signature records and what a review
    prints. Publishing it is intended; publishing the key itself would let anyone
    sign.
    """
    raw = bytes.fromhex(secret_hex.strip())
    return "k-" + hashlib.sha256(b"text-adventure-pack-key:" + raw).hexdigest()[:16]


def generate_key() -> tuple[str, str]:
    """Return ``(secret_hex, key_id)`` for a new signing key."""
    return os.urandom(KEY_BYTES).hex(), ""


def sign_pack(root: Path, secret_hex: str, *, signer: str = "") -> dict[str, Any]:
    """Sign the pack at *root*, writing ``signature.json`` and returning it."""
    pack = load_pack(root)
    digest = pack_digest(pack)
    mac = hmac.new(bytes.fromhex(secret_hex.strip()), digest.encode("ascii"), hashlib.sha256)
    signature = {
        "algorithm": ALGORITHM,
        "key_id": key_id(secret_hex),
        "digest": digest,
        "signature": mac.hexdigest(),
        "signed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "signer": signer or getpass.getuser(),
        "pack_version": pack.version,
    }
    (root / SIGNATURE_FILE).write_text(
        json.dumps(signature, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return signature


def verify_signature(
    root: Path, secret_hex: str | None = None, policy: Policy | None = None
) -> dict[str, Any]:
    """Check the pack's signature. Returns ``{status, ...}`` or raises.

    ``status`` is one of ``valid`` / ``unsigned``. Both are returns; a *bad* signature
    raises :class:`SignatureError`, and a missing signature raises
    :class:`PolicyError` when the policy requires one. Keeping "unsigned" a return
    value rather than an exception is what lets the reviewer print a run of warnings
    instead of stopping at the first development pack.
    """
    policy = policy or Policy()
    signature_path = root / SIGNATURE_FILE
    if not signature_path.is_file():
        if policy.required:
            raise PolicyError(f"{root}: no {SIGNATURE_FILE} and signatures are required")
        return {"status": "unsigned", "reason": f"no {SIGNATURE_FILE}"}

    try:
        record = json.loads(signature_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SignatureError(f"{signature_path}: invalid JSON: {exc}") from exc
    if not isinstance(record, dict):
        raise SignatureError(f"{signature_path}: signature must be a JSON object")

    algorithm = record.get("algorithm")
    if algorithm != ALGORITHM:
        raise SignatureError(
            f"{signature_path}: algorithm {algorithm!r} is not supported "
            f"(this verifier implements {ALGORITHM!r})"
        )
    recorded_key = str(record.get("key_id", ""))
    if not recorded_key:
        raise SignatureError(f"{signature_path}: the signature does not name a key")
    if policy.keyring and not policy.known(recorded_key):
        raise PolicyError(
            f"{signature_path}: signed by unknown key {recorded_key!r}; "
            f"keyring knows {sorted(policy.keyring)}"
        )

    pack = load_pack(root)
    digest = pack_digest(pack)
    if digest != record.get("digest"):
        raise SignatureError(
            f"{root}: content does not match the signature — the pack changed after it "
            f"was signed (signed {str(record.get('digest'))[:16]}…, now {digest[:16]}…)"
        )

    if secret_hex is None:
        # Without the secret, the digest match is all that can be checked. Reported
        # honestly instead of as "verified".
        return {
            "status": "digest-match",
            "key_id": recorded_key,
            "signer": record.get("signer", ""),
            "note": "signature not cryptographically verified (no key supplied)",
        }

    expected = hmac.new(
        bytes.fromhex(secret_hex.strip()), digest.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, str(record.get("signature", ""))):
        raise SignatureError(
            f"{root}: signature does not verify with key {key_id(secret_hex)!r} "
            f"(the pack is signed by {recorded_key!r})"
        )
    return {
        "status": "valid",
        "key_id": recorded_key,
        "signer": record.get("signer", ""),
        "signed_at": record.get("signed_at", ""),
    }


def load_keyring(path: Path | str) -> dict[str, str]:
    """Read a keyring file: ``{"keys": {"k-…": "label", …}}`` or a bare mapping."""
    path = Path(path)
    if not path.is_file():
        raise SubmissionError(f"keyring not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionError(f"{path}: invalid JSON: {exc}") from exc
    keys = payload.get("keys", payload) if isinstance(payload, dict) else None
    if not isinstance(keys, dict):
        raise SubmissionError(f"{path}: expected an object mapping key ids to labels")
    return {str(name): str(label) for name, label in keys.items()}


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------


@dataclass
class Submission:
    """A pack prepared for review, plus its provenance."""

    root: Path
    manifest: dict[str, Any]
    signature: dict[str, Any] | None
    body: dict[str, Any]

    @property
    def pack_name(self) -> str:
        return str(self.manifest.get("name", self.root.name))

    @property
    def version(self) -> str:
        return str(self.manifest.get("version", "0"))

    @property
    def languages(self) -> list[str]:
        return [str(code) for code in self.manifest.get("languages", [])]

    @property
    def submitter(self) -> str:
        return str(self.body.get("submitter", "unknown"))

    @property
    def license(self) -> str:
        return str(self.body.get("license", "unspecified"))


def load_submission(root: Path | str) -> Submission:
    """Load a submission directory (a pack plus ``submission.json``)."""
    root = Path(root)
    body_path = root / "submission.json"
    if not body_path.is_file():
        raise SubmissionError(
            f"{root}: not a submission — no submission.json "
            "(a pack alone can still be loaded with load_pack)"
        )
    try:
        body = json.loads(body_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubmissionError(f"{body_path}: invalid JSON: {exc}") from exc
    if not isinstance(body, dict):
        raise SubmissionError(f"{body_path}: submission metadata must be a JSON object")

    signature_path = root / SIGNATURE_FILE
    signature = None
    if signature_path.is_file():
        try:
            signature = json.loads(signature_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SubmissionError(f"{signature_path}: invalid JSON: {exc}") from exc

    # load_pack validates the pack itself; a submission is a pack first.
    pack = load_pack(root)
    return Submission(root=root, manifest=pack.manifest, signature=signature, body=body)


def review(
    submission: Submission,
    target: Path | str | None = None,
    *,
    policy: Policy | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """Produce a reviewer's report: validation, signature, and the content delta.

    Never raises for content problems — a reviewer wants the whole list, not the first
    error. It raises only when the submission cannot be read at all (and then
    :func:`load_submission` raised first).
    """
    policy = policy or Policy()
    report: dict[str, Any] = {
        "name": submission.pack_name,
        "version": submission.version,
        "languages": submission.languages,
        "submitter": submission.submitter,
        "license": submission.license,
        "problems": [],
        "warnings": [],
    }

    pack = load_pack(submission.root)
    validation = validate_pack(pack, language=submission.languages[0] if submission.languages else None)
    report["counts"] = validation["counts"]
    if not validation["ok"]:
        report["problems"].extend(validation["problems"])

    # Provenance fields a reviewer needs before accepting anything.
    if submission.license in ("", "unspecified"):
        report["problems"].append("submission.json is missing a 'license'")
    if submission.submitter in ("", "unknown"):
        report["warnings"].append("submission.json does not name the submitter")

    engine_min = str(submission.manifest.get("min_engine_version", ""))
    if engine_min and _newer(engine_min, ENGINE_VERSION):
        report["problems"].append(
            f"pack needs engine >= {engine_min}, this engine is {ENGINE_VERSION}"
        )
    format_version = submission.manifest.get("format_version")
    if format_version != PACK_FORMAT_VERSION:
        report["warnings"].append(
            f"pack format_version is {format_version}, engine writes {PACK_FORMAT_VERSION}"
        )

    # Signature. A missing signature is judged by the policy *here*, not inside
    # verify_signature: the report must distinguish "absent" from "untrusted" and from
    # "tampered", and reporting an unsigned pack under a `required` policy as plain
    # "unsigned" reads as if nothing were wrong. Passing `required=False` down keeps
    # the two decisions separate.
    lookup_policy = Policy(required=False, keyring=policy.keyring)
    try:
        report["signature"] = verify_signature(submission.root, key, lookup_policy)
    except SignatureError as exc:
        report["problems"].append(str(exc))
        report["signature"] = {"status": "invalid", "reason": str(exc)}
    except PolicyError as exc:
        report["problems"].append(str(exc))
        report["signature"] = {"status": "untrusted-key", "reason": str(exc)}
    if report["signature"]["status"] == "unsigned":
        if policy.required:
            reason = f"no {SIGNATURE_FILE} and signatures are required"
            report["problems"].append(f"{submission.root}: {reason}")
            report["signature"] = {"status": "missing-required", "reason": reason}
        else:
            report["warnings"].append("pack is unsigned (see docs/content-submission.md)")

    # Files a pack is allowed to contain.
    unexpected = sorted(
        path.name
        for path in submission.root.iterdir()
        if path.is_file() and path.name not in CONTENT_FILES + (SIGNATURE_FILE, "submission.json")
    )
    if unexpected:
        report["warnings"].append(f"unexpected file(s), will not be copied: {unexpected}")

    # Content delta against whatever is already shipped.
    if target is not None:
        report["delta"] = _delta(submission, Path(target))
    report["ok"] = not report["problems"]
    return report


def _delta(submission: Submission, target_root: Path) -> dict[str, Any]:
    """What accepting this submission would change, item by item."""
    destination = target_root / submission.pack_name
    if not destination.is_dir():
        return {"new_pack": True, "summary": f"creates a new pack {submission.pack_name!r}"}

    current = load_pack(destination)
    delta: dict[str, Any] = {"new_pack": False, "kinds": {}}
    for kind in sorted(set(current.content) | set(submission.manifest.get("content", {}))):
        old_ids = {_item_id(item) for item in current.items(kind)}
        new_items = load_pack(submission.root).items(kind)
        new_ids = {_item_id(item) for item in new_items}
        delta["kinds"][kind] = {
            "before": len(old_ids),
            "after": len(new_ids),
            "added": sorted(new_ids - old_ids),
            "removed": sorted(old_ids - new_ids),
            "unchanged": len(old_ids & new_ids),
        }
    return delta


def _item_id(item: dict[str, Any]) -> str:
    for key in ("id", "word", "question", "start"):
        if key in item:
            return str(item[key])
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def accept(
    submission: Submission,
    target_root: Path | str,
    *,
    policy: Policy | None = None,
    key: str | None = None,
    actor: str = "",
    force: bool = False,
) -> dict[str, Any]:
    """Copy a reviewed submission into the packs directory.

    Refuses when the review found problems unless *force* is set, and records the
    provenance in ``content/provenance.json`` (outside the pack) so the pack directory
    keeps exactly the files a pack is defined to have — which is what keeps the digest
    stable across accept/re-sign cycles.
    """
    target_root = Path(target_root)
    report = review(submission, target_root, policy=policy, key=key)
    if report["problems"] and not force:
        raise PolicyError(
            "refusing to accept a submission with problems: "
            + "; ".join(report["problems"][:3])
        )

    destination = target_root / submission.pack_name
    destination.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in CONTENT_FILES:
        source = submission.root / name
        if source.is_file():
            shutil.copyfile(source, destination / name)
            copied.append(name)
    if SIGNATURE_FILE and (submission.root / SIGNATURE_FILE).is_file():
        shutil.copyfile(submission.root / SIGNATURE_FILE, destination / SIGNATURE_FILE)
        copied.append(SIGNATURE_FILE)

    provenance_path = target_root / "provenance.json"
    provenance: dict[str, Any] = {}
    if provenance_path.is_file():
        try:
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SubmissionError(f"{provenance_path}: invalid JSON: {exc}") from exc
    record = {
        "pack": submission.pack_name,
        "version": submission.version,
        "submitter": submission.submitter,
        "license": submission.license,
        "digest": pack_digest(load_pack(destination)),
        "signed_by": (submission.signature or {}).get("key_id", ""),
        "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "accepted_by": actor or getpass.getuser(),
        "copied": copied,
    }
    provenance.setdefault("packs", {})[submission.pack_name] = record
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"accepted": submission.pack_name, "copied": copied, "provenance": record, "report": report}


def _newer(candidate: str, current: str) -> bool:
    def parts(value: str) -> tuple[int, ...]:
        out: list[int] = []
        for chunk in value.split("."):
            digits = "".join(character for character in chunk if character.isdigit())
            out.append(int(digits) if digits else 0)
        return tuple(out)

    return parts(candidate) > parts(current)


# ---------------------------------------------------------------------------
# Author-side scaffolding
# ---------------------------------------------------------------------------


def new_draft(destination: Path | str, name: str, language: str, *, submitter: str = "",
              license_name: str = "") -> Path:
    """Create an empty, valid pack skeleton a contributor can fill in.

    Valid on creation on purpose: an author should be able to run the validator and
    see a clean report before writing a single item, so a later failure is theirs.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "0.1.0",
        "format_version": PACK_FORMAT_VERSION,
        "min_engine_version": ENGINE_VERSION,
        "languages": [language],
        "description": f"{name}: {language} content pack",
        "content": {
            "riddles": {"file": "riddles.json", "count": 1},
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "riddles.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "id": "example-1",
                        "difficulty": "easy",
                        "question": "填一个谜面" if language == "zh" else "Write a question",
                        "options": ["A", "B"],
                        "answer": 0,
                    }
                ]
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (destination / "submission.json").write_text(
        json.dumps(
            {
                "submitter": submitter or getpass.getuser(),
                "license": license_name or "CC-BY-4.0",
                "notes": "Replace this skeleton: see docs/content-submission.md",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination
