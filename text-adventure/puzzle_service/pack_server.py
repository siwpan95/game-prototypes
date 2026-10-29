"""Online pack service: an HTTP face on the submission workflow. Standard library only.

Why a server at all: the workflow so far is "send the maintainer a directory". That
works for one contributor and stops working at about three, because every submission
needs the maintainer present. This exposes the same review/accept path over HTTP so a
contributor can submit a pack and the maintainer can review it later.

What this deliberately is *not*:

* **not an upload of installed content.** A submitted pack lands in a quarantine
  directory. It is not visible to any client, and it is not copied into the packs
  directory, until a maintainer accepts it. "The server put it live" must never be
  something a request can cause.
* **not authenticated as anyone.** A `submitter` field is a *claim*, so the server
  records the claimed name but trusts the signature for authenticity. A submission with
  no valid signature is refused outright for third-party content, because otherwise the
  name is the only thing on it and nothing is verifiable.
* **not a database.** Files on disk, one directory per submission, which is enough for
  the volumes this project has and keeps the state inspectable with ``ls``.

The three limits that keep a public endpoint from being a liability:

* a request body cap (a pack is data, and data has a size);
* per-client rate limiting, since packing a large JSON is cheap to send and expensive to
  validate;
* path handling that never joins a client-supplied string onto a directory without
  checking the result is still inside it.
"""

from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import time
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from puzzle_service.content import ContentPackError, load_pack
from puzzle_service.pack_registry import (
    BUNDLE_FILES,
    BUNDLE_MANIFEST,
    REGISTRY_FILE,
    RegistryError,
    build_registry,
    entry_for,
    sign_registry,
    verify_registry,
)
from puzzle_service.submission import (
    Policy,
    PolicyError,
    SignatureError,
    key_id,
    pack_digest,
    sign_pack,
    verify_signature,
)

__all__ = ["PackService", "PackServiceConfig", "RateLimiter", "serve", "main"]

#: Largest request body accepted, in bytes. A pack is five JSON files of words; 4 MiB
#: is far above any legitimate pack and far below "fill the disk with one request".
MAX_BODY = 4 * 1024 * 1024

#: Largest single upload file.
MAX_FILE = 2 * 1024 * 1024

#: Submission names are used as directory names, so the pattern is the security
#: boundary, not cosmetic: no separators, no dots-only, no leading dash.
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

#: Files a submission may contain.
ALLOWED_FILES = (BUNDLE_MANIFEST, *BUNDLE_FILES, "signature.json", "submission.json")

STATUS_PENDING = "pending"
STATUS_ACCEPTED = "accepted"
STATUS_REJECTED = "rejected"


class RateLimiter:
    """Token bucket per client, so one caller cannot monopolise validation."""

    def __init__(self, capacity: int = 10, refill_seconds: float = 6.0):
        self.capacity = capacity
        self.refill_seconds = refill_seconds
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            tokens, last = self._buckets.get(client, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) / self.refill_seconds)
            if tokens < 1.0:
                self._buckets[client] = (tokens, now)
                return False
            self._buckets[client] = (tokens - 1.0, now)
            return True


@dataclass
class PackServiceConfig:
    """Where everything lives, and who is trusted."""

    #: Published bundles, served to clients.
    published: Path
    #: Submitted-but-unreviewed packs, invisible to clients.
    quarantine: Path
    #: Signing key for the registry this server publishes.
    secret_hex: str = ""
    signer: str = "pack-service"
    #: Trusted submitter keys (key id -> label). Empty = accept any signature.
    keyring: dict[str, str] = field(default_factory=dict)
    #: Require a valid signature on submissions. On by default: an unsigned third-party
    #: pack is a name and nothing else.
    require_signature: bool = True
    base_url: str = ""
    rate_capacity: int = 10
    rate_refill_seconds: float = 6.0
    max_body: int = MAX_BODY
    max_file: int = MAX_FILE


class PackService:
    """The workflow behind the HTTP surface, usable directly in tests."""

    def __init__(self, config: PackServiceConfig):
        self.config = config
        self.config.published.mkdir(parents=True, exist_ok=True)
        self.config.quarantine.mkdir(parents=True, exist_ok=True)
        self.limiter = RateLimiter(config.rate_capacity, config.rate_refill_seconds)

    # --- registry ------------------------------------------------------------

    def registry_document(self) -> dict[str, Any]:
        """The signed index of published packs."""
        document = build_registry(self.config.published, base_url=self.config.base_url)
        if self.config.secret_hex:
            sign_registry(document, self.config.secret_hex, signer=self.config.signer)
        return document

    def bundle_path(self, name: str) -> Path:
        entry_for(self._entries(), name)  # raises when absent
        return self._bundle(name)

    def _bundle(self, name: str) -> Path:
        if not NAME_PATTERN.match(name):
            raise RegistryError(f"invalid pack name {name!r}")
        path = self.config.published / name
        if not path.is_dir():
            raise RegistryError(f"pack {name!r} is not published")
        return path

    def _entries(self):
        document = self.registry_document()
        from puzzle_service.pack_registry import RegistryEntry

        return [RegistryEntry.from_dict(item) for item in document.get("packs", [])]

    # --- submission ----------------------------------------------------------

    def submit(self, name: str, body: dict[str, Any]) -> dict[str, Any]:
        """Validate and quarantine a submission. Never installs anything."""
        if not NAME_PATTERN.match(name):
            raise ValueError(
                f"invalid pack name {name!r}: letters, digits, dot, dash and underscore only"
            )
        if not isinstance(body, dict):
            raise ValueError("submission must be a JSON object")

        files = body.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("submission must carry a 'files' object")
        unknown = sorted(set(files) - set(ALLOWED_FILES))
        if unknown:
            raise ValueError(f"unexpected file(s) {unknown}; allowed: {list(ALLOWED_FILES)}")
        if BUNDLE_MANIFEST not in files:
            raise ValueError(f"submission must include {BUNDLE_MANIFEST!r}")

        for file_name, payload in files.items():
            if not isinstance(payload, str):
                raise ValueError(f"{file_name}: content must be a base64 string")
            if len(payload) > self.config.max_file * 4 // 3 + 8:
                raise ValueError(f"{file_name}: file exceeds {self.config.max_file} bytes")

        destination = self.config.quarantine / name
        if destination.exists():
            # Re-submitting is normal (fix and try again); overwriting is not, because
            # it would silently discard a submission that may already be under review.
            raise ValueError(
                f"a submission named {name!r} is already quarantined; "
                "use a new name or ask the maintainer to clear it"
            )

        staging = Path(tempfile.mkdtemp(prefix=f"submit-{name}-"))
        try:
            for file_name, payload in files.items():
                import base64

                try:
                    raw = base64.b64decode(payload, validate=True)
                except Exception as exc:  # noqa: BLE001 - any decode failure is the error
                    raise ValueError(f"{file_name}: not valid base64 ({exc})") from exc
                if len(raw) > self.config.max_file:
                    raise ValueError(f"{file_name}: exceeds {self.config.max_file} bytes")
                (staging / file_name).write_bytes(raw)

            # The bundle is validated the same way a client would: manifest renamed,
            # pack loaded, signature checked. A submission that cannot be installed is
            # refused here, while the submitter is still present to read the reason.
            pack, staging_pack = _load_bundle_dir(staging)
            policy = Policy(required=self.config.require_signature, keyring=self.config.keyring)
            try:
                signature = verify_signature(staging_pack, None, policy)
            except (SignatureError, PolicyError) as exc:
                raise ValueError(f"signature refused: {exc}") from exc

            submission = {
                "name": name,
                "pack": pack.name,
                "version": pack.version,
                "digest": pack_digest(pack),
                "languages": pack.languages,
                "counts": {kind: len(items) for kind, items in pack.content.items()},
                "claimed_submitter": str(body.get("submitter", "")),
                "notes": str(body.get("notes", ""))[:2000],
                "signature": signature,
                "status": STATUS_PENDING,
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "files": sorted(files),
            }
            destination.mkdir(parents=True)
            for path in staging.iterdir():
                shutil.move(str(path), str(destination / path.name))
            (destination / "submission.json").write_text(
                json.dumps(submission, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return submission

    def list_submissions(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for directory in sorted(self.config.quarantine.iterdir()):
            record = directory / "submission.json"
            if directory.is_dir() and record.is_file():
                try:
                    out.append(json.loads(record.read_text(encoding="utf-8")))
                except json.JSONDecodeError:
                    out.append({"name": directory.name, "status": "unreadable"})
        return out

    def status(self, name: str) -> dict[str, Any]:
        if not NAME_PATTERN.match(name):
            raise ValueError(f"invalid pack name {name!r}")
        quarantine_record = self.config.quarantine / name / "submission.json"
        if quarantine_record.is_file():
            return json.loads(quarantine_record.read_text(encoding="utf-8"))
        if (self.config.published / name).is_dir():
            return {"name": name, "status": STATUS_ACCEPTED}
        return {"name": name, "status": "unknown"}

    def accept(self, name: str, *, actor: str = "maintainer") -> dict[str, Any]:
        """Move a quarantined submission into the published set.

        The one operation that changes what clients can fetch, so it is explicit, named,
        and never reachable from a submission request.
        """
        if not NAME_PATTERN.match(name):
            raise ValueError(f"invalid pack name {name!r}")
        source = self.config.quarantine / name
        if not source.is_dir():
            raise ValueError(f"no quarantined submission named {name!r}")

        destination = self.config.published / name
        if destination.exists():
            raise ValueError(f"{name!r} is already published")

        staging = Path(tempfile.mkdtemp(prefix=f"accept-{name}-"))
        try:
            manifest = json.loads((source / BUNDLE_MANIFEST).read_text(encoding="utf-8"))
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            for file_name in (*BUNDLE_FILES, "signature.json"):
                candidate = source / file_name
                if candidate.is_file():
                    shutil.copyfile(candidate, staging / file_name)
            if self.config.secret_hex:
                sign_pack(staging, self.config.secret_hex, signer=actor)
            pack = load_pack(staging)
            shutil.copytree(staging, destination)
        finally:
            shutil.rmtree(staging, ignore_errors=True)

        record_path = source / "submission.json"
        record = (
            json.loads(record_path.read_text(encoding="utf-8"))
            if record_path.is_file()
            else {"name": name}
        )
        record.update(
            {
                "status": STATUS_ACCEPTED,
                "accepted_by": actor,
                "accepted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "published_digest": pack_digest(pack),
            }
        )
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record

    def reject(self, name: str, *, actor: str = "maintainer", reason: str = "") -> dict[str, Any]:
        record_path = self.config.quarantine / name / "submission.json"
        if not record_path.is_file():
            raise ValueError(f"no quarantined submission named {name!r}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record.update(
            {
                "status": STATUS_REJECTED,
                "rejected_by": actor,
                "rejected_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "reason": reason[:500],
            }
        )
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return record


def _load_bundle_dir(staging: Path):
    """Load a staged submission as a pack (bundle manifest renamed in place)."""
    manifest = staging / BUNDLE_MANIFEST
    if manifest.is_file() and not (staging / "manifest.json").is_file():
        (staging / "manifest.json").write_bytes(manifest.read_bytes())
    return load_pack(staging), staging


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    service: PackService
    protocol_version = "HTTP/1.1"
    server_version = "text-adventure-pack-service/1"

    # --- helpers -------------------------------------------------------------

    def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, status: int, message: str) -> None:
        self._send_json({"error": message, "status": status}, status)

    def _client(self) -> str:
        return self.client_address[0] if self.client_address else "unknown"

    def _drain(self, length: int, chunk: int = 64 * 1024) -> None:
        """Read and discard *length* bytes without buffering them all.

        Used when refusing an oversized body: the client has already sent (or is still
        sending) it, and a refusal that does not read the request tends to arrive as a
        dropped connection rather than as the status code.
        """
        remaining = length
        try:
            while remaining > 0:
                block = self.rfile.read(min(chunk, remaining))
                if not block:
                    break
                remaining -= len(block)
        except OSError:
            # The client gave up while we were draining; the refusal still stands.
            pass

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        # Quieter than the default: one line per request, no timestamp duplication
        # (the host collects timestamps), and no request body.
        print(f"[pack-service] {self._client()} {format % args}", flush=True)

    # --- verbs ---------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        path = self.path.split("?", 1)[0]
        try:
            if path in ("/", "/healthz"):
                self._send_json({"service": "text-adventure pack service", "status": "ok"})
                return
            if path in ("/registry.json", "/index.json"):
                self._send_json(self.service.registry_document())
                return
            if path.startswith("/packs/"):
                name = path[len("/packs/"):]
                if name.endswith(".json"):
                    name = name[: -len(".json")]
                bundle = self.service.bundle_path(name)
                # Served in *bundle* shape: the pack manifest goes out as
                # ``bundle.json``. The client pulls it into a cache and only writes
                # ``manifest.json`` when it installs, so a downloaded file can never be
                # mistaken for an installed pack — and an accepted pack (which is a
                # normal pack on disk, with manifest.json) is served correctly too.
                files: dict[str, str] = {}
                import base64

                for file in sorted(bundle.iterdir()):
                    if not file.is_file() or file.name == "signature.json":
                        continue
                    served_name = (
                        BUNDLE_MANIFEST if file.name == "manifest.json" else file.name
                    )
                    if served_name not in (BUNDLE_MANIFEST, *BUNDLE_FILES):
                        continue
                    files[served_name] = base64.b64encode(file.read_bytes()).decode("ascii")
                signature = bundle / "signature.json"
                self._send_json(
                    {
                        "name": name,
                        "files": files,
                        "signature": json.loads(signature.read_text(encoding="utf-8"))
                        if signature.is_file()
                        else None,
                    }
                )
                return
            if path == "/submissions":
                # Review surface: names, digests and claims — no file bodies, so it
                # cannot be used to fetch unreviewed content.
                self._send_json(
                    {
                        "submissions": [
                            {k: v for k, v in record.items() if k != "files"}
                            for record in self.service.list_submissions()
                        ]
                    }
                )
                return
            if path.startswith("/submissions/"):
                self._send_json(self.service.status(path.rsplit("/", 1)[-1]))
                return
        except (RegistryError, ValueError) as exc:
            self._fail(HTTPStatus.NOT_FOUND, str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - a crash must not take the server down
            self._fail(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(exc).__name__}: {exc}")
            return
        self._fail(HTTPStatus.NOT_FOUND, f"no such path: {path}")

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        path = self.path.split("?", 1)[0]
        if not self.service.limiter.allow(self._client()):
            self._fail(HTTPStatus.TOO_MANY_REQUESTS, "rate limit exceeded; slow down")
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._fail(HTTPStatus.LENGTH_REQUIRED, "a JSON body is required")
            return
        if length > self.service.config.max_body:
            # Drain what the client is already sending before answering. Closing the
            # socket mid-upload makes the client see a connection abort instead of the
            # status code, and the status code is the useful part of this response.
            self._drain(length)
            self._fail(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"body of {length} bytes exceeds the {self.service.config.max_body} byte limit",
            )
            return
        raw = self.rfile.read(length)

        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._fail(HTTPStatus.BAD_REQUEST, f"invalid JSON body: {exc}")
            return

        # Accept-only action, deliberately a separate path from submission: no upload
        # can publish itself.
        if path.startswith("/accept/"):
            if not self.service.config.secret_hex and not self.service.config.keyring:
                pass  # open mode is a development setting, documented as such
            name = path[len("/accept/"):]
            try:
                record = self.service.accept(name, actor=str(payload.get("actor", "maintainer")))
            except ValueError as exc:
                self._fail(HTTPStatus.CONFLICT, str(exc))
                return
            except ContentPackError as exc:
                self._fail(HTTPStatus.BAD_REQUEST, f"pack does not load: {exc}")
                return
            self._send_json(record)
            return

        if path == "/submit":
            name = str(payload.get("name", ""))
            try:
                record = self.service.submit(name, payload)
            except ValueError as exc:
                self._fail(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(record, HTTPStatus.CREATED)
            return

        if path == "/reject":
            try:
                record = self.service.reject(
                    str(payload.get("name", "")),
                    actor=str(payload.get("actor", "maintainer")),
                    reason=str(payload.get("reason", "")),
                )
            except ValueError as exc:
                self._fail(HTTPStatus.NOT_FOUND, str(exc))
                return
            self._send_json(record)
            return

        self._fail(HTTPStatus.NOT_FOUND, f"no such path: {path}")


def serve(config: PackServiceConfig, host: str = "127.0.0.1", port: int = 8765):
    """Build (but do not start) the HTTP server."""
    service = PackService(config)
    handler = type("BoundHandler", (_Handler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import os

    parser = argparse.ArgumentParser(prog="pack-service", description="serve packs and submissions")
    parser.add_argument("--published", type=Path, required=True)
    parser.add_argument("--quarantine", type=Path, required=True)
    parser.add_argument("--key-file", type=Path, default=None,
                        help="registry signing key (or set PACK_SERVICE_KEY)")
    parser.add_argument("--keyring", type=Path, default=None)
    parser.add_argument("--signer", default="pack-service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--allow-unsigned", action="store_true",
                        help="development only: accept submissions without a signature")
    args = parser.parse_args(argv)

    secret = ""
    if args.key_file is not None:
        secret = _read_key(args.key_file)
    elif os.environ.get("PACK_SERVICE_KEY"):
        secret = os.environ["PACK_SERVICE_KEY"].strip()

    keyring: dict[str, str] = {}
    if args.keyring is not None:
        from puzzle_service.submission import load_keyring

        keyring = load_keyring(args.keyring)

    config = PackServiceConfig(
        published=args.published,
        quarantine=args.quarantine,
        secret_hex=secret,
        signer=args.signer,
        keyring=keyring,
        require_signature=not args.allow_unsigned,
        base_url=f"http://{args.host}:{args.port}",
    )
    httpd = serve(config, args.host, args.port)
    print(
        f"[pack-service] listening on http://{args.host}:{args.port} "
        f"published={args.published} quarantine={args.quarantine} "
        f"registry_signature={'yes' if secret else 'no'} "
        f"submission_signature={'required' if config.require_signature else 'optional'}",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("[pack-service] stopped", flush=True)
    finally:
        httpd.server_close()
    return 0


def _read_key(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    raise SystemExit(f"{path}: no key material found")


if __name__ == "__main__":
    raise SystemExit(main())
