"""Submission and signing tests.

The interesting cases are the adversarial ones: a pack that changed after signing, a
signature from a key the reviewer does not trust, and a missing signature where one is
required. Each has to fail *differently* — "unsigned" is not "invalid", and a policy
that cannot tell them apart either blocks development or accepts tampering.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from puzzle_service.content import ContentPackError, load_pack
from puzzle_service.submission import (
    ALGORITHM,
    Policy,
    PolicyError,
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


@pytest.fixture
def key() -> str:
    """A deterministic key, so a failure is reproducible."""
    return "0f" * 32


@pytest.fixture
def other_key() -> str:
    return "ab" * 32


@pytest.fixture
def draft(tmp_path: Path) -> Path:
    return new_draft(tmp_path / "my-pack", "my-pack", "zh", submitter="ada", license_name="CC-BY-4.0")


def _add_riddle(root: Path, item_id: str, question: str = "一个谜面") -> None:
    path = root / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"].append(
        {"id": item_id, "difficulty": "easy", "question": question, "options": ["a", "b"], "answer": 0}
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Digest: what a signature actually covers
# ---------------------------------------------------------------------------


def test_digest_ignores_formatting(draft: Path) -> None:
    """A formatter must not invalidate a signature."""
    before = pack_digest(load_pack(draft))
    path = draft / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=8, sort_keys=True), encoding="utf-8")
    assert pack_digest(load_pack(draft)) == before


def test_digest_changes_when_an_item_is_added(draft: Path) -> None:
    before = pack_digest(load_pack(draft))
    _add_riddle(draft, "extra")
    assert pack_digest(load_pack(draft)) != before


def test_digest_changes_when_an_item_is_edited(draft: Path) -> None:
    """Editing an answer in place is tampering, not a formatting change."""
    before = pack_digest(load_pack(draft))
    path = draft / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"][0]["answer"] = 1
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    assert pack_digest(load_pack(draft)) != before


def test_digest_depends_on_item_order(draft: Path) -> None:
    """Order is observable (a seeded draw reaches a different item), so it is signed."""
    before = pack_digest(load_pack(draft))
    _add_riddle(draft, "z-item")
    _add_riddle(draft, "a-item")
    ordered = pack_digest(load_pack(draft))
    path = draft / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"].reverse()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    assert pack_digest(load_pack(draft)) != ordered
    assert before != ordered


def test_byte_digest_is_a_different_measure(draft: Path) -> None:
    """Kept separate on purpose: `--bytes` answers a different question."""
    path = draft / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    semantic = pack_digest(load_pack(draft))
    bytes_before = content_digest(draft)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=8), encoding="utf-8")
    assert content_digest(draft) != bytes_before  # bytes changed
    assert pack_digest(load_pack(draft)) == semantic  # semantics did not


def test_signature_file_is_not_part_of_the_file_digest(draft: Path) -> None:
    before = content_digest(draft)
    sign_pack(draft, "0f" * 32)
    assert content_digest(draft) == before


# ---------------------------------------------------------------------------
# Signing and verification
# ---------------------------------------------------------------------------


def test_a_signature_verifies_with_its_key(draft: Path, key: str) -> None:
    record = sign_pack(draft, key, signer="ada")
    result = verify_signature(draft, key, Policy(required=True))
    assert result["status"] == "valid"
    assert result["key_id"] == record["key_id"] == key_id(key)
    assert result["signer"] == "ada"


def test_without_the_key_verification_is_reported_as_partial(draft: Path, key: str) -> None:
    """Not 'valid': claiming verification that did not happen is the bug to avoid."""
    sign_pack(draft, key)
    result = verify_signature(draft)
    assert result["status"] == "digest-match"
    assert "not cryptographically verified" in result["note"]


def test_the_wrong_key_fails(draft: Path, key: str, other_key: str) -> None:
    sign_pack(draft, key)
    with pytest.raises(SignatureError, match="does not verify"):
        verify_signature(draft, other_key)


def test_tampering_after_signing_is_detected(draft: Path, key: str) -> None:
    sign_pack(draft, key)
    _add_riddle(draft, "injected")
    with pytest.raises(SignatureError, match="changed after it was signed"):
        verify_signature(draft, key)


def test_an_unknown_key_is_rejected_even_with_a_perfect_signature(draft: Path, key: str) -> None:
    """A signature is not trust: the key must be one the reviewer knows."""
    sign_pack(draft, key)
    policy = Policy(keyring={"k-someone-else": "not this key"})
    with pytest.raises(PolicyError, match="unknown key"):
        verify_signature(draft, key, policy)


def test_a_missing_signature_is_rejected_only_when_required(draft: Path) -> None:
    assert verify_signature(draft)["status"] == "unsigned"
    with pytest.raises(PolicyError, match="no signature.json"):
        verify_signature(draft, policy=Policy(required=True))


def test_an_unsupported_algorithm_is_refused(draft: Path, key: str) -> None:
    sign_pack(draft, key)
    path = draft / "signature.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["algorithm"] = "rot13"
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(SignatureError, match="not supported"):
        verify_signature(draft, key)
    # And the file really does name the implemented algorithm.
    assert ALGORITHM == "hmac-sha256"


def test_a_signature_with_no_key_id_is_refused(draft: Path, key: str) -> None:
    """Without a key id there is nothing to check trust against, so it is a signature
    problem — not silently 'unsigned', and not a pass."""
    sign_pack(draft, key)
    path = draft / "signature.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["key_id"]
    path.write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(SignatureError, match="does not name a key"):
        verify_signature(draft, key, Policy(keyring={"k-anything": "x"}))


def test_key_ids_differ_per_key(key: str, other_key: str) -> None:
    assert key_id(key) != key_id(other_key)
    assert key_id(key).startswith("k-")


def test_generated_keys_are_unique_and_full_length() -> None:
    first, _ = generate_key()
    second, _ = generate_key()
    assert first != second
    assert len(first) == 64  # 32 bytes hex


def test_keyring_loading_accepts_both_shapes(tmp_path: Path) -> None:
    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"keys": {"k-1": "Ada"}}), encoding="utf-8")
    bare = tmp_path / "bare.json"
    bare.write_text(json.dumps({"k-1": "Ada"}), encoding="utf-8")
    assert load_keyring(wrapped) == load_keyring(bare) == {"k-1": "Ada"}
    with pytest.raises(SubmissionError, match="expected an object"):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps([1, 2]), encoding="utf-8")
        load_keyring(bad)


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def test_review_of_a_clean_signed_submission_passes(draft: Path, key: str) -> None:
    sign_pack(draft, key, signer="ada")
    report = review(load_submission(draft), policy=Policy(required=True, keyring={key_id(key): "ada"}), key=key)
    assert report["ok"], report["problems"]
    assert report["signature"]["status"] == "valid"
    assert report["license"] == "CC-BY-4.0"
    assert report["submitter"] == "ada"


def test_review_lists_every_problem_instead_of_stopping_at_the_first(draft: Path, key: str) -> None:
    """A reviewer wants the whole list; stopping at one error wastes a round trip."""
    sign_pack(draft, key)
    _add_riddle(draft, "injected")
    body = json.loads((draft / "submission.json").read_text(encoding="utf-8"))
    body["license"] = "unspecified"
    (draft / "submission.json").write_text(json.dumps(body), encoding="utf-8")
    report = review(load_submission(draft), key=key)
    assert not report["ok"]
    assert len(report["problems"]) == 2
    assert any("license" in problem for problem in report["problems"])
    assert any("changed after it was signed" in problem for problem in report["problems"])


def test_review_flags_an_item_that_fails_validation(tmp_path: Path) -> None:
    root = new_draft(tmp_path / "bad", "bad-pack", "zh", submitter="ada", license_name="CC0")
    path = root / "riddles.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"][0]["answer"] = 7  # outside the options
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # The pack itself no longer loads, which is the loudest possible failure.
    with pytest.raises(ContentPackError, match="outside the"):
        load_submission(root)


def test_review_flags_a_missing_submitter_only_as_a_warning(tmp_path: Path) -> None:
    root = new_draft(tmp_path / "anon", "anon-pack", "zh", submitter="", license_name="CC0")
    body = json.loads((root / "submission.json").read_text(encoding="utf-8"))
    body["submitter"] = ""
    (root / "submission.json").write_text(json.dumps(body), encoding="utf-8")
    report = review(load_submission(root))
    assert report["ok"]
    assert any("does not name the submitter" in warning for warning in report["warnings"])


def test_review_warns_about_files_that_will_not_be_copied(draft: Path) -> None:
    (draft / "notes.txt").write_text("scratch", encoding="utf-8")
    report = review(load_submission(draft))
    assert any("will not be copied" in warning for warning in report["warnings"])


def test_review_reports_the_content_delta(draft: Path, tmp_path: Path) -> None:
    packs = tmp_path / "packs"
    sign_pack(draft, "0f" * 32, signer="ada")
    accept(load_submission(draft), packs, actor="maintainer")
    _add_riddle(draft, "second-riddle")
    sign_pack(draft, "0f" * 32, signer="ada")
    report = review(load_submission(draft), packs, key="0f" * 32)
    assert report["ok"], report["problems"]
    change = report["delta"]["kinds"]["riddles"]
    assert change["before"] == 1 and change["after"] == 2
    assert change["added"] == ["second-riddle"]
    assert change["removed"] == []


def test_review_of_a_new_pack_says_so(draft: Path, tmp_path: Path) -> None:
    report = review(load_submission(draft), tmp_path / "empty-packs")
    assert report["delta"]["new_pack"] is True


def test_a_pack_without_submission_json_is_not_a_submission(draft: Path) -> None:
    (draft / "submission.json").unlink()
    with pytest.raises(SubmissionError, match="no submission.json"):
        load_submission(draft)


def test_load_submission_reads_the_signature_when_present(draft: Path, key: str) -> None:
    assert load_submission(draft).signature is None
    sign_pack(draft, key)
    submission = load_submission(draft)
    assert submission.signature is not None
    assert submission.signature["key_id"] == key_id(key)


# ---------------------------------------------------------------------------
# Accept
# ---------------------------------------------------------------------------


def test_accept_copies_the_pack_and_records_provenance(draft: Path, tmp_path: Path, key: str) -> None:
    packs = tmp_path / "packs"
    sign_pack(draft, key, signer="ada")
    result = accept(load_submission(draft), packs, key=key, actor="maintainer")
    assert result["accepted"] == "my-pack"
    accepted = load_pack(packs / "my-pack")
    assert accepted.name == "my-pack"
    provenance = json.loads((packs / "provenance.json").read_text(encoding="utf-8"))
    record = provenance["packs"]["my-pack"]
    assert record["submitter"] == "ada"
    assert record["accepted_by"] == "maintainer"
    assert record["license"] == "CC-BY-4.0"
    assert record["signed_by"] == key_id(key)
    assert record["digest"] == pack_digest(accepted)


def test_accept_does_not_copy_unexpected_files(draft: Path, tmp_path: Path) -> None:
    (draft / "scratch.txt").write_text("x", encoding="utf-8")
    accept(load_submission(draft), tmp_path / "packs", actor="maintainer")
    assert not (tmp_path / "packs" / "my-pack" / "scratch.txt").exists()


def test_accept_refuses_a_tampered_submission(draft: Path, tmp_path: Path, key: str) -> None:
    sign_pack(draft, key)
    _add_riddle(draft, "injected")
    with pytest.raises(PolicyError, match="refusing to accept"):
        accept(load_submission(draft), tmp_path / "packs", key=key)


def test_accept_refuses_an_unsigned_submission_when_required(draft: Path, tmp_path: Path) -> None:
    with pytest.raises(PolicyError, match="refusing to accept"):
        accept(load_submission(draft), tmp_path / "packs", policy=Policy(required=True))


def test_review_marks_an_unsigned_pack_as_missing_required_under_a_strict_policy(
    draft: Path,
) -> None:
    """`unsigned` would read as "nothing wrong"; the status has to say what it is."""
    strict = review(load_submission(draft), policy=Policy(required=True))
    assert not strict["ok"]
    assert strict["signature"]["status"] == "missing-required"
    assert any("signatures are required" in problem for problem in strict["problems"])

    relaxed = review(load_submission(draft))
    assert relaxed["ok"]
    assert relaxed["signature"]["status"] == "unsigned"
    assert any("unsigned" in warning for warning in relaxed["warnings"])


def test_force_accepts_a_submission_with_problems_and_still_records_it(
    draft: Path, tmp_path: Path
) -> None:
    """Force is for the maintainer who has read the problems, not for hiding them."""
    result = accept(load_submission(draft), tmp_path / "packs", policy=Policy(required=True), force=True)
    assert result["provenance"]["signed_by"] == ""
    assert result["report"]["signature"]["status"] == "missing-required"
    assert not result["report"]["ok"]


def test_provenance_accumulates_across_packs(tmp_path: Path) -> None:
    packs = tmp_path / "packs"
    for name in ("first-pack", "second-pack"):
        root = new_draft(tmp_path / name, name, "zh", submitter="ada", license_name="CC0")
        accept(load_submission(root), packs, actor="maintainer")
    provenance = json.loads((packs / "provenance.json").read_text(encoding="utf-8"))
    assert sorted(provenance["packs"]) == ["first-pack", "second-pack"]


def test_a_corrupt_provenance_file_is_reported_not_overwritten(tmp_path: Path) -> None:
    """Silently replacing it would lose the record of everything accepted before."""
    packs = tmp_path / "packs"
    packs.mkdir()
    (packs / "provenance.json").write_text("{not json", encoding="utf-8")
    root = new_draft(tmp_path / "pack", "pack", "zh", submitter="ada", license_name="CC0")
    with pytest.raises(SubmissionError, match="invalid JSON"):
        accept(load_submission(root), packs, actor="maintainer")


def test_accept_is_idempotent_for_the_same_submission(draft: Path, tmp_path: Path) -> None:
    """Re-accepting the same pack must not duplicate or corrupt anything."""
    packs = tmp_path / "packs"
    first = accept(load_submission(draft), packs, actor="maintainer")
    second = accept(load_submission(draft), packs, actor="maintainer")
    assert first["provenance"]["digest"] == second["provenance"]["digest"]
    assert len(list((packs / "my-pack").glob("*.json"))) == 2  # manifest + riddles

# ---------------------------------------------------------------------------
# Runtime enforcement: the service and the protocol server, not just the CLI
# ---------------------------------------------------------------------------


def test_the_service_reports_how_far_its_content_was_verified() -> None:
    """A permissive deployment still says what it loaded."""
    from puzzle_service.service import PuzzleService

    summary = PuzzleService(language="zh").content_summary()
    assert summary["source"] == "content pack"
    assert summary["trust"] == "unsigned"


def test_the_service_refuses_to_start_on_untrusted_content(tmp_path: Path) -> None:
    """Strict mode fails at startup, not when the first player asks for a puzzle."""
    from puzzle_service.service import ContentTrustError, PuzzleService

    with pytest.raises(ContentTrustError, match="signatures are required"):
        PuzzleService(language="zh", require_signature=True)


def test_strict_mode_accepts_a_properly_signed_pack(draft: Path, monkeypatch, key: str) -> None:
    """The point of the policy: it must not just refuse everything.

    Also proves the verified pack is the one actually played from — a policy that
    verifies one directory and serves another would pass every other test here.

    Runs in a subprocess because the kind registry is process-global: it registers a
    language's kinds *once*, bound to whichever pack loaded first. In-process, an
    earlier test has already registered `zh` with the shipped pack, so this service
    would skip discovery and play the shipped content while verifying `draft` — which
    is exactly the mistake an in-process version of this test made.
    """
    sign_pack(draft, key, signer="ada")
    probe = (
        "import json, sys\n"
        f"sys.path.insert(0, r'{Path(__file__).resolve().parents[1]}')\n"
        "from puzzle_service.service import PuzzleService\n"
        f"service = PuzzleService(language='zh', require_signature=True,\n"
        f"                        keyring={{'{key_id(key)}': 'ada'}})\n"
        "view = service.new_puzzle('session', kind='riddle')['view']\n"
        "print(json.dumps({\n"
        "    'trust': service.content_summary()['trust'],\n"
        "    'questions': [n['text'] for n in view['nodes'] if n['type'] == 'text'],\n"
        "}, ensure_ascii=False))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "TEXT_ADVENTURE_CONTENT_PACK": str(draft)},
        timeout=180,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["trust"] == "digest-match"
    # The pack holds exactly one riddle, so the question has to be that one.
    assert payload["questions"] == ["填一个谜面"], payload["questions"]


def test_strict_mode_refuses_content_tampered_after_signing(
    draft: Path, monkeypatch, key: str
) -> None:
    """Tampering is caught regardless of language registration: the check runs on the
    pack itself, before any kind is chosen."""
    from puzzle_service.service import ContentTrustError, PuzzleService

    sign_pack(draft, key, signer="ada")
    _add_riddle(draft, "injected")
    monkeypatch.setenv("TEXT_ADVENTURE_CONTENT_PACK", str(draft))
    with pytest.raises(ContentTrustError, match="changed after it was signed"):
        PuzzleService(language="zh", require_signature=True, keyring={key_id(key): "ada"})


def test_the_protocol_server_refuses_to_serve_untrusted_content() -> None:
    """End to end through the real entry point: exit code, not a traceback."""
    result = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parents[1] / "python" / "rpc_server.py"),
         "--require-signature"],
        input='{"jsonrpc":"2.0","id":1,"method":"server.ping"}\n',
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    assert result.returncode == 4, f"{result.stdout}\n{result.stderr}"
    assert "refusing to serve untrusted content" in result.stderr
