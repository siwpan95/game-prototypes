"""The pack registry: what a client is offered, signed as one document.

A client that downloads content over a network needs an answer to "which packs exist,
and how do I know this list is the one the maintainer published?" Serving each pack
with its own signature answers the second question only *after* the download; the list
itself is what tells the client what to fetch, so it needs its own signature. Otherwise
an attacker who can rewrite the list can point clients at their own pack — or, worse,
at a pack that is individually valid but was never offered.

Shape of the document:

    {
      "registry_version": 1,
      "generated_at": "...",
      "packs": [ {name, version, languages, digest, key_id, signer, files, url, size, ...} ],
      "signature": {algorithm, key_id, digest, signature}
    }

``digest`` per pack is the pack's *content semantics* digest, the same value its own
signature covers (:func:`puzzle_service.submission.pack_digest`), so the client can
check a download against the index and the index against its own signature.

The signature covers the pack list, not the file bytes: re-indenting the JSON or
reordering object keys must not invalidate the registry, and the per-file hashes are
inside the signed list anyway.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from puzzle_service.content import ContentPackError, load_pack
from puzzle_service.submission import (
    ALGORITHM,
    Policy,
    PolicyError,
    SignatureError,
    key_id,
    pack_digest,
    verify_signature,
)

__all__ = [
    "REGISTRY_VERSION",
    "REGISTRY_FILE",
    "RegistryError",
    "RegistryEntry",
    "build_registry",
    "sign_registry",
    "verify_registry",
    "load_registry",
    "registry_digest",
    "entry_for",
]

REGISTRY_VERSION = 1
REGISTRY_FILE = "registry.json"

#: Files a published pack bundle carries. The server renames the pack manifest to
#: ``bundle.json`` so that downloading a bundle into a pack directory is not mistaken
#: for installing a pack: the client pulls it into its cache, validates, and only then
#: writes ``manifest.json`` into place.
BUNDLE_MANIFEST = "bundle.json"

#: Content files a bundle may contain (the manifest is renamed).
BUNDLE_FILES = (
    "riddles.json",
    "hangman_words.json",
    "anagram_words.json",
    "word_ladders.json",
    "crosswords.json",
)


class RegistryError(Exception):
    """The registry is unusable: malformed, unverifiable, or inconsistent."""


@dataclass
class RegistryEntry:
    """One offered pack."""

    name: str
    version: str
    digest: str
    languages: list[str] = field(default_factory=list)
    key_id: str = ""
    signer: str = ""
    files: dict[str, str] = field(default_factory=dict)  # file name -> sha256 of bytes
    size: int = 0
    counts: dict[str, int] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "digest": self.digest,
            "languages": list(self.languages),
            "key_id": self.key_id,
            "signer": self.signer,
            "files": dict(sorted(self.files.items())),
            "size": self.size,
            "counts": dict(sorted(self.counts.items())),
            "description": self.description,
            "url": f"packs/{self.name}.json",
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "RegistryEntry":
        files = payload.get("files")
        return cls(
            name=str(payload.get("name", "")),
            version=str(payload.get("version", "0")),
            digest=str(payload.get("digest", "")),
            languages=[str(code) for code in payload.get("languages", [])],
            key_id=str(payload.get("key_id", "")),
            signer=str(payload.get("signer", "")),
            files={str(k): str(v) for k, v in files.items()} if isinstance(files, dict) else {},
            size=int(payload.get("size", 0) or 0),
            counts={
                str(k): int(v)
                for k, v in (payload.get("counts") or {}).items()
            },
            description=str(payload.get("description", "")),
        )


# ---------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------


def _is_bundle(directory: Path) -> bool:
    return (directory / BUNDLE_MANIFEST).is_file()


def _load_bundle(directory: Path):
    """Load a published pack bundle (``bundle.json`` instead of ``manifest.json``).

    The loader knows ``manifest.json``, so the bundle is staged under a temporary name
    it accepts. Deliberately not by copying files into place first: a half-installed
    pack that then fails validation would leave a pack directory that looks loadable.
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="pack-bundle-") as staging:
        staging_path = Path(staging)
        (staging_path / "manifest.json").write_bytes((directory / BUNDLE_MANIFEST).read_bytes())
        for name in BUNDLE_FILES:
            source = directory / name
            if source.is_file():
                (staging_path / name).write_bytes(source.read_bytes())
        signature = directory / "signature.json"
        if signature.is_file():
            (staging_path / "signature.json").write_bytes(signature.read_bytes())
        return load_pack(staging_path), staging_path


def build_registry(root: Path | str, *, base_url: str = "") -> dict[str, Any]:
    """Index every valid, signed pack bundle under *root*.

    A directory that is not a valid pack is **reported and skipped**, not indexed.
    Indexing something the client will then reject turns a packaging mistake into a
    client-side failure with no maintainer-visible cause.
    """
    root = Path(root)
    if not root.is_dir():
        raise RegistryError(f"registry root not found: {root}")

    entries: list[RegistryEntry] = []
    skipped: list[str] = []
    for directory in sorted(path for path in root.iterdir() if path.is_dir()):
        try:
            if _is_bundle(directory):
                pack, staging = _load_bundle(directory)
                signature_path = staging / "signature.json"
                signature = (
                    json.loads(signature_path.read_text(encoding="utf-8"))
                    if signature_path.is_file()
                    else {}
                )
            else:
                pack = load_pack(directory)
                signature_path = directory / "signature.json"
                signature = (
                    json.loads(signature_path.read_text(encoding="utf-8"))
                    if signature_path.is_file()
                    else {}
                )
        except (ContentPackError, json.JSONDecodeError) as exc:
            skipped.append(f"{directory.name}: {exc}")
            continue

        files: dict[str, str] = {}
        size = 0
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            # Only files this server actually serves go into the index. Listing the
            # others (a maintainer's review record, scratch notes) made the client's
            # "does the bundle match the index?" check fail on a perfectly good pack —
            # the index promised a file the bundle never carries.
            served_name = BUNDLE_MANIFEST if path.name == "manifest.json" else path.name
            if served_name not in (BUNDLE_MANIFEST, *BUNDLE_FILES):
                continue
            # `signature.json` is deliberately excluded: it is verified
            # cryptographically against the pack's content, which is a stronger check
            # than a byte hash — and a byte hash of it is brittle, because a JSON
            # document that means the same thing can be written with different spacing.
            payload = path.read_bytes()
            files[served_name] = hashlib.sha256(payload).hexdigest()
            size += len(payload)

        entries.append(
            RegistryEntry(
                name=pack.name,
                version=pack.version,
                digest=pack_digest(pack),
                languages=pack.languages,
                key_id=str(signature.get("key_id", "")),
                signer=str(signature.get("signer", "")),
                files=files,
                size=size,
                counts={kind: len(items) for kind, items in pack.content.items()},
                description=str(pack.manifest.get("description", "")),
            )
        )

    document = {
        "registry_version": REGISTRY_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "base_url": base_url,
        "packs": [entry.to_dict() for entry in entries],
    }
    if skipped:
        document["skipped"] = skipped
    return document


def registry_digest(document: dict[str, Any]) -> str:
    """SHA-256 over the pack list (the signature's subject; signature excluded)."""
    payload = {
        "registry_version": document.get("registry_version"),
        "packs": document.get("packs", []),
    }
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sign_registry(document: dict[str, Any], secret_hex: str, *, signer: str = "") -> dict[str, Any]:
    """Attach a signature over the pack list. Mutates and returns *document*."""
    digest = registry_digest(document)
    mac = hmac.new(bytes.fromhex(secret_hex.strip()), digest.encode("ascii"), hashlib.sha256)
    document["signature"] = {
        "algorithm": ALGORITHM,
        "key_id": key_id(secret_hex),
        "digest": digest,
        "signature": mac.hexdigest(),
        "signed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "signer": signer,
    }
    return document


def verify_registry(
    document: dict[str, Any], secret_hex: str | None = None, policy: Policy | None = None
) -> dict[str, Any]:
    """Check the registry's own signature. Raises on tampering or an unknown key."""
    policy = policy or Policy()
    if not isinstance(document, dict):
        raise RegistryError("registry must be a JSON object")
    if document.get("registry_version") != REGISTRY_VERSION:
        raise RegistryError(
            f"registry_version {document.get('registry_version')!r} is not supported "
            f"(this client implements {REGISTRY_VERSION})"
        )
    record = document.get("signature")
    if not isinstance(record, dict):
        if policy.required:
            raise PolicyError("the registry is unsigned and signatures are required")
        return {"status": "unsigned"}

    if record.get("algorithm") != ALGORITHM:
        raise SignatureError(
            f"registry signature algorithm {record.get('algorithm')!r} is not supported"
        )
    recorded_key = str(record.get("key_id", ""))
    if policy.keyring and recorded_key not in policy.keyring:
        raise PolicyError(
            f"registry is signed by unknown key {recorded_key!r}; "
            f"keyring knows {sorted(policy.keyring)}"
        )
    digest = registry_digest(document)
    if digest != record.get("digest"):
        raise SignatureError(
            "the registry's pack list does not match its signature — the list changed "
            f"after it was signed (signed {str(record.get('digest'))[:16]}…, "
            f"now {digest[:16]}…)"
        )
    if secret_hex is None:
        return {
            "status": "digest-match",
            "key_id": recorded_key,
            "signer": record.get("signer", ""),
            "note": "registry signature not cryptographically verified (no key supplied)",
        }
    expected = hmac.new(
        bytes.fromhex(secret_hex.strip()), digest.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, str(record.get("signature", ""))):
        raise SignatureError(
            f"registry signature does not verify with key {key_id(secret_hex)!r}"
        )
    return {
        "status": "valid",
        "key_id": recorded_key,
        "signer": record.get("signer", ""),
        "signed_at": record.get("signed_at", ""),
    }


def load_registry(path: Path | str, secret_hex: str | None = None,
                  policy: Policy | None = None) -> tuple[dict[str, Any], list[RegistryEntry]]:
    """Read, verify and parse a registry document."""
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RegistryError(f"{path}: invalid JSON: {exc}") from exc
    verify_registry(document, secret_hex, policy)
    entries = [RegistryEntry.from_dict(item) for item in document.get("packs", [])]
    return document, entries


def entry_for(entries: list[RegistryEntry], name: str) -> RegistryEntry:
    """The entry named *name*, or a failure naming what is available."""
    for entry in entries:
        if entry.name == name:
            return entry
    raise RegistryError(
        f"no pack named {name!r} in the registry; available: {sorted(e.name for e in entries)}"
    )
