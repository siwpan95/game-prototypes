"""Client for the online pack service: fetch, verify, install. Standard library only.

The order of operations is the whole point, and it is not the obvious one:

    fetch index → verify the index signature → pick a pack → download →
    verify the pack's own signature → **then** install

Verifying after installing, or installing on the strength of the index alone, means the
window between those steps is a window in which unverified content is on disk where the
game will load it. So a download is written to a temporary directory, checked there, and
moved into place only once it has passed — and the move is a directory rename, so a crash
leaves either the old pack or the new one, never half of either.

Two policies, both explicit rather than implied:

* the **index** decides what is on offer, so an unsigned index is refused when a key is
  configured (insecure-by-silence is how a client ends up trusting whatever it is told);
* the **pack** must verify against a keyring when one is configured, so "signed" cannot
  mean "signed by anyone".
"""

from __future__ import annotations

import base64
import json
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from puzzle_service.content import ContentPackError, load_pack
from puzzle_service.pack_registry import (
    BUNDLE_FILES,
    BUNDLE_MANIFEST,
    RegistryEntry,
    RegistryError,
    entry_for,
    verify_registry,
)
from puzzle_service.submission import (
    Policy,
    PolicyError,
    SignatureError,
    verify_signature,
)

__all__ = [
    "PackClientError",
    "InstallResult",
    "PackClient",
    "default_install_root",
]

#: Largest registry document accepted, so a malicious server cannot exhaust memory.
MAX_INDEX_BYTES = 512 * 1024

#: Largest bundle accepted.
MAX_BUNDLE_BYTES = 4 * 1024 * 1024

#: Network timeout for every request. A pack service that hangs must not hang the game.
TIMEOUT = 15.0


class PackClientError(Exception):
    """Fetching, verifying or installing a pack failed."""


def default_install_root() -> Path:
    """Where downloaded packs are installed: next to the shipped ones."""
    return Path(__file__).resolve().parents[1] / "content" / "packs"


@dataclass
class InstallResult:
    """What an install did."""

    name: str
    version: str
    digest: str
    installed: bool
    path: Path
    status: str  # installed | unchanged | refused
    reason: str = ""
    already_present: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "digest": self.digest,
            "installed": self.installed,
            "path": str(self.path),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class PackClient:
    """Talks to a pack service, without trusting it."""

    base_url: str
    install_root: Path = field(default_factory=default_install_root)
    #: Trusted registry keys (key id -> label). Empty = accept an unsigned index.
    registry_keyring: dict[str, str] = field(default_factory=dict)
    #: Trusted pack-signing keys. Empty = any signature that matches its own content.
    pack_keyring: dict[str, str] = field(default_factory=dict)
    #: Require a signature on downloaded packs. On: a download is remote input.
    require_signature: bool = True
    timeout: float = TIMEOUT
    #: Injectable for tests, so the client can be exercised without a socket.
    opener: Any = None

    # --- fetching ------------------------------------------------------------

    def _get(self, url: str, limit: int) -> bytes:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        opener = self.opener or urllib.request.urlopen
        try:
            with opener(request, timeout=self.timeout) as response:
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > limit:
                    raise PackClientError(
                        f"{url}: server declares {declared} bytes, limit is {limit}"
                    )
                payload = response.read(limit + 1)
        except urllib.error.HTTPError as exc:
            raise PackClientError(f"{url}: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise PackClientError(f"{url}: {exc.reason}") from exc
        if len(payload) > limit:
            # Read one byte past the limit on purpose: a truncated read looks like
            # "success" and a truncated pack is worse than a refused one.
            raise PackClientError(f"{url}: response exceeds {limit} bytes")
        return payload

    def fetch_registry(self) -> list[RegistryEntry]:
        """Fetch and verify the index. Raises rather than returning a suspect list."""
        raw = self._get(f"{self.base_url.rstrip('/')}/registry.json", MAX_INDEX_BYTES)
        try:
            document = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PackClientError(f"index is not valid JSON: {exc}") from exc
        policy = Policy(required=bool(self.registry_keyring), keyring=self.registry_keyring)
        try:
            verify_registry(document, None, policy)
        except (SignatureError, PolicyError, RegistryError) as exc:
            raise PackClientError(f"index refused: {exc}") from exc
        return [RegistryEntry.from_dict(item) for item in document.get("packs", [])]

    def fetch_bundle(self, entry: RegistryEntry) -> tuple[Path, dict[str, Any]]:
        """Download a pack into a temporary directory, verified but not installed."""
        url = f"{self.base_url.rstrip('/')}/packs/{entry.name}.json"
        raw = self._get(url, MAX_BUNDLE_BYTES)
        try:
            bundle = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise PackClientError(f"{entry.name}: bundle is not valid JSON: {exc}") from exc
        files = bundle.get("files")
        if not isinstance(files, dict) or BUNDLE_MANIFEST not in files:
            raise PackClientError(f"{entry.name}: bundle has no {BUNDLE_MANIFEST!r}")

        staging = Path(tempfile.mkdtemp(prefix=f"pack-{entry.name}-"))
        try:
            for file_name, payload in files.items():
                if file_name not in (BUNDLE_MANIFEST, *BUNDLE_FILES, "signature.json"):
                    raise PackClientError(f"{entry.name}: unexpected file {file_name!r}")
                if not isinstance(payload, str):
                    raise PackClientError(f"{entry.name}: {file_name} is not a string")
                try:
                    decoded = base64.b64decode(payload, validate=True)
                except Exception as exc:  # noqa: BLE001
                    raise PackClientError(f"{entry.name}: {file_name} is not valid base64") from exc
                (staging / file_name).write_bytes(decoded)

            signature = bundle.get("signature")
            if isinstance(signature, dict):
                (staging / "signature.json").write_text(
                    json.dumps(signature, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            # Checks that must pass *before* anything reaches the install root.
            self._verify_download(entry, staging, signature)
            return staging, bundle
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _verify_download(
        self, entry: RegistryEntry, staging: Path, signature: dict[str, Any] | None
    ) -> None:
        # The bundle manifest is the pack manifest under another name.
        (staging / "manifest.json").write_bytes((staging / BUNDLE_MANIFEST).read_bytes())

        if entry.files:
            import hashlib

            for file_name, expected in entry.files.items():
                local = staging / file_name
                if not local.is_file():
                    raise PackClientError(f"{entry.name}: index lists {file_name!r}, bundle lacks it")
                actual = hashlib.sha256(local.read_bytes()).hexdigest()
                if actual != expected:
                    raise PackClientError(
                        f"{entry.name}: {file_name} does not match the index "
                        f"({expected[:16]}… expected, {actual[:16]}… received)"
                    )

        policy = Policy(required=self.require_signature, keyring=self.pack_keyring)
        try:
            result = verify_signature(staging, None, policy)
        except (SignatureError, PolicyError) as exc:
            raise PackClientError(f"{entry.name}: pack refused: {exc}") from exc

        if entry.digest and result.get("status") != "unsigned":
            from puzzle_service.submission import pack_digest

            actual_digest = pack_digest(load_pack(staging))
            if actual_digest != entry.digest:
                raise PackClientError(
                    f"{entry.name}: content digest differs from the index "
                    f"({entry.digest[:16]}… expected, {actual_digest[:16]}… received)"
                )
        # Remove the staging manifest again: what gets installed is the bundle shape,
        # and the install step is what writes manifest.json.
        (staging / "manifest.json").unlink(missing_ok=True)

    # --- installing ----------------------------------------------------------

    def install(self, entry: RegistryEntry) -> InstallResult:
        """Download and install one pack. Returns what happened, or raises."""
        destination = self.install_root / entry.name
        existing = self.installed_digest(entry.name)
        if existing and existing == entry.digest:
            return InstallResult(
                name=entry.name, version=entry.version, digest=entry.digest,
                installed=False, path=destination, status="unchanged",
                already_present=existing,
            )

        staging, _ = self.fetch_bundle(entry)
        try:
            (staging / "manifest.json").write_bytes((staging / BUNDLE_MANIFEST).read_bytes())
            install_dir = staging / "pack"
            install_dir.mkdir()
            for file_name in ("manifest.json", *BUNDLE_FILES, "signature.json"):
                source = staging / file_name
                if source.is_file():
                    shutil.copyfile(source, install_dir / file_name)

            # Final gate: the thing about to be installed must load and validate.
            pack = load_pack(install_dir)
            from puzzle_service.submission import pack_digest

            digest = pack_digest(pack)
            if entry.digest and digest != entry.digest:
                raise PackClientError(
                    f"{entry.name}: refusing to install: staged content digest "
                    f"{digest[:16]}… differs from the index {entry.digest[:16]}…"
                )

            self.install_root.mkdir(parents=True, exist_ok=True)
            backup: Path | None = None
            if destination.exists():
                backup = destination.with_name(f"{destination.name}.old-{int(time.time())}")
                destination.rename(backup)
            try:
                install_dir.rename(destination)
            except OSError:
                if backup is not None and not destination.exists():
                    backup.rename(destination)  # put the old pack back
                raise
            if backup is not None:
                shutil.rmtree(backup, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        return InstallResult(
            name=entry.name, version=entry.version, digest=digest,
            installed=True, path=destination, status="installed",
        )

    def installed_digest(self, name: str) -> str:
        """Digest of the installed pack, or ``""`` when it is not installed."""
        path = self.install_root / name
        if not (path / "manifest.json").is_file():
            return ""
        try:
            from puzzle_service.submission import pack_digest

            return pack_digest(load_pack(path))
        except ContentPackError:
            return ""

    def update_all(self) -> list[InstallResult]:
        """Install every pack the index offers that is missing or out of date."""
        results: list[InstallResult] = []
        for entry in self.fetch_registry():
            results.append(self.install(entry))
        return results

    def available(self) -> list[dict[str, Any]]:
        """The index as plain rows, for a client to display."""
        return [
            {
                "name": entry.name,
                "version": entry.version,
                "languages": entry.languages,
                "counts": entry.counts,
                "size": entry.size,
                "signer": entry.signer,
                "description": entry.description,
                "installed": bool(self.installed_digest(entry.name)),
                "current": self.installed_digest(entry.name) == entry.digest,
            }
            for entry in self.fetch_registry()
        ]
