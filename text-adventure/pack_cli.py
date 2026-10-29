"""Command-line workflow for content packs: author → sign → review → accept.

    pack-cli keygen --out author.key
    pack-cli new --out drafts/my-pack --name my-pack --language zh --submitter ada
    ... edit the JSON ...
    pack-cli validate drafts/my-pack
    pack-cli sign drafts/my-pack --key author.key
    pack-cli review drafts/my-pack --keyring keys.json --signing-key author.key
    pack-cli accept drafts/my-pack --keyring keys.json --signing-key author.key --actor maintainer

Exits non-zero on any problem, so it can gate a pull request.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from puzzle_service.content import ContentPackError, default_pack_path, load_pack
from puzzle_service.submission import (
    Policy,
    SignatureError,
    SubmissionError,
    accept,
    content_digest,
    generate_key,
    key_id,
    load_keyring,
    load_submission,
    new_draft,
    pack_digest,
    review,
    sign_pack,
    verify_signature,
)

__all__ = ["main", "build_parser"]


def _packs_root() -> Path:
    return default_pack_path("zh").parent


def _policy(args: argparse.Namespace) -> Policy:
    keyring = load_keyring(args.keyring) if getattr(args, "keyring", None) else {}
    return Policy(required=bool(getattr(args, "require_signature", False)), keyring=keyring)


def _print_report(report: dict) -> None:
    print(f"pack:      {report['name']} v{report['version']}  [{', '.join(report['languages'])}]")
    print(f"submitter: {report['submitter']}   license: {report['license']}")
    if report.get("counts"):
        counts = ", ".join(f"{kind}={count}" for kind, count in sorted(report["counts"].items()))
        print(f"content:   {counts}")
    signature = report.get("signature", {})
    print(f"signature: {signature.get('status', 'none')}"
          + (f" ({signature.get('signer', '')}, {signature.get('key_id', '')})"
             if signature.get("key_id") else ""))
    if delta := report.get("delta"):
        if delta.get("new_pack"):
            print(f"delta:     {delta['summary']}")
        else:
            for kind, change in sorted(delta.get("kinds", {}).items()):
                line = (f"delta:     {kind}: {change['before']} -> {change['after']} "
                        f"(+{len(change['added'])}, -{len(change['removed'])})")
                print(line)
                for added in change["added"][:5]:
                    print(f"             + {added}")
                for removed in change["removed"][:5]:
                    print(f"             - {removed}")
    for warning in report.get("warnings", []):
        print(f"WARN       {warning}")
    for problem in report.get("problems", []):
        print(f"PROBLEM    {problem}")
    print("REVIEW OK" if report.get("ok") else "REVIEW FOUND PROBLEMS")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pack-cli", description="content pack workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    keygen = sub.add_parser("keygen", help="create a signing key")
    keygen.add_argument("--out", required=True, type=Path)
    keygen.add_argument("--label", default="", help="name recorded in the keyring")

    new = sub.add_parser("new", help="scaffold an empty pack + submission.json")
    new.add_argument("--out", required=True, type=Path)
    new.add_argument("--name", required=True)
    new.add_argument("--language", default="zh")
    new.add_argument("--submitter", default="")
    new.add_argument("--license", default="")

    validate = sub.add_parser("validate", help="validate a pack or submission")
    validate.add_argument("path", type=Path)

    digest = sub.add_parser("digest", help="print the digest a signature covers")
    digest.add_argument("path", type=Path)
    digest.add_argument("--bytes", action="store_true", help="hash file bytes instead of semantics")

    sign = sub.add_parser("sign", help="sign a pack")
    sign.add_argument("path", type=Path)
    sign.add_argument("--key", required=True, type=Path)
    sign.add_argument("--signer", default="")

    verify = sub.add_parser("verify", help="verify a pack's signature")
    verify.add_argument("path", type=Path)
    verify.add_argument("--key", type=Path, help="the signing key, for cryptographic verification")
    verify.add_argument("--keyring", type=Path)
    verify.add_argument("--require-signature", action="store_true")

    review_cmd = sub.add_parser("review", help="reviewer's report for a submission")
    review_cmd.add_argument("path", type=Path)
    review_cmd.add_argument("--target", type=Path, default=None, help="packs root to diff against")
    review_cmd.add_argument("--key", type=Path, help="signing key, for cryptographic verification")
    review_cmd.add_argument("--keyring", type=Path)
    review_cmd.add_argument("--require-signature", action="store_true")

    accept_cmd = sub.add_parser("accept", help="copy a reviewed submission into the packs root")
    accept_cmd.add_argument("path", type=Path)
    accept_cmd.add_argument("--target", type=Path, default=None)
    accept_cmd.add_argument("--key", type=Path)
    accept_cmd.add_argument("--keyring", type=Path)
    accept_cmd.add_argument("--require-signature", action="store_true")
    accept_cmd.add_argument("--actor", default="")
    accept_cmd.add_argument("--force", action="store_true", help="accept despite problems")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except (SubmissionError, SignatureError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ContentPackError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "keygen":
        secret, _ = generate_key()
        args.out.write_text(
            f"# text-adventure content signing key\n"
            f"# key id: {key_id(secret)}\n"
            f"# Keep this file private: anyone holding it can sign packs.\n"
            f"{secret}\n",
            encoding="utf-8",
        )
        print(f"wrote {args.out}  (key id {key_id(secret)})")
        if args.label:
            print(f'add to the keyring: {{"keys": {{"{key_id(secret)}": "{args.label}"}}}}')
        return 0

    if args.command == "new":
        root = new_draft(args.out, args.name, args.language, submitter=args.submitter,
                         license_name=args.license)
        print(f"created {root} (valid on creation — run `validate` to confirm)")
        return 0

    if args.command == "validate":
        pack = load_pack(args.path)
        print(
            f"OK  {pack.name} v{pack.version} "
            f"({', '.join(f'{kind}={len(items)}' for kind, items in sorted(pack.content.items()))})"
        )
        return 0

    if args.command == "digest":
        if args.bytes:
            print(f"{content_digest(args.path)}  (file bytes)")
        else:
            print(f"{pack_digest(load_pack(args.path))}  (content semantics)")
        return 0

    if args.command == "sign":
        key = _read_key(args.key)
        record = sign_pack(args.path, key, signer=args.signer)
        print(f"signed {args.path} as {record['signer']} (key {record['key_id']})")
        print(f"digest {record['digest']}")
        return 0

    if args.command == "verify":
        key = _read_key(args.key) if args.key else None
        result = verify_signature(args.path, key, _policy(args))
        status = result["status"]
        print(f"{status}: {args.path}")
        for field_name in ("key_id", "signer", "signed_at", "reason", "note"):
            if result.get(field_name):
                print(f"  {field_name}: {result[field_name]}")
        return 0 if status in ("valid", "digest-match", "unsigned") else 1

    if args.command in ("review", "accept"):
        submission = load_submission(args.path)
        target = args.target
        key = _read_key(args.key) if args.key else None
        policy = _policy(args)
        report = review(submission, target, policy=policy, key=key)
        _print_report(report)
        if args.command == "review":
            return 0 if report["ok"] else 1
        if not report["ok"] and not args.force:
            print("refusing to accept; re-run with --force only if you mean it", file=sys.stderr)
            return 1
        result = accept(
            submission,
            target if target is not None else _packs_root(),
            policy=policy,
            key=key,
            actor=args.actor,
            force=args.force,
        )
        print(f"accepted {result['accepted']} -> {result['provenance']['digest'][:16]}…")
        print(f"copied {', '.join(result['copied'])}")
        print(f"provenance recorded by {result['provenance']['accepted_by']}")
        return 0

    raise AssertionError(f"unhandled command {args.command!r}")  # pragma: no cover


def _read_key(path: Path) -> str:
    """Read a key file, ignoring ``#`` comment lines."""
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        raise SubmissionError(f"{path}: no key material found")
    return lines[0]


if __name__ == "__main__":
    raise SystemExit(main())
