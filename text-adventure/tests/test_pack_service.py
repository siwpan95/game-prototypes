"""The online pack service: registry signing, HTTP surface, and the untrusting client.

Everything here runs over a real socket (``ThreadingHTTPServer`` on port 0) rather than
against mocks, because the parts most likely to be wrong are the ones a mock replaces:
body limits, path handling, and the order of "verify" and "install".

The adversarial cases are the point:

* a tampered **bundle** must not install;
* a tampered **index** must not be trusted (otherwise a client can be pointed at a pack
  nobody published);
* an **unsigned** submission must be refused when a signature is required, because for
  third-party content the signature is the only thing that is not a claim;
* a submission must not be able to publish itself.
"""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from puzzle_service.pack_client import PackClient, PackClientError
from puzzle_service.pack_registry import (
    REGISTRY_VERSION,
    RegistryError,
    build_registry,
    entry_for,
    load_registry,
    registry_digest,
    sign_registry,
    verify_registry,
)
from puzzle_service.pack_server import (
    MAX_BODY,
    PackServiceConfig,
    RateLimiter,
    PackService,
    serve,
)
from puzzle_service.submission import key_id, new_draft, pack_digest, sign_pack
from puzzle_service.content import load_pack

AUTHOR_KEY = "0f" * 32
OTHER_KEY = "77" * 32
SERVER_KEY = "a1" * 32


@pytest.fixture
def service(tmp_path: Path) -> PackService:
    return PackService(
        PackServiceConfig(
            published=tmp_path / "published",
            quarantine=tmp_path / "quarantine",
            secret_hex=SERVER_KEY,
            signer="maintainer",
            keyring={key_id(AUTHOR_KEY): "ada"},
        )
    )


@pytest.fixture
def live(service: PackService):
    """A running server on an ephemeral port, torn down afterwards."""
    httpd = serve(
        PackServiceConfig(
            published=service.config.published,
            quarantine=service.config.quarantine,
            secret_hex=SERVER_KEY,
            signer="maintainer",
            keyring={key_id(AUTHOR_KEY): "ada"},
        ),
        "127.0.0.1",
        0,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _bundle_files(draft: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in sorted(draft.iterdir()):
        name = "bundle.json" if path.name == "manifest.json" else path.name
        out[name] = base64.b64encode(path.read_bytes()).decode("ascii")
    return out


def _post(base: str, path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        base + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def _get(base: str, path: str) -> dict:
    with urllib.request.urlopen(base + path, timeout=10) as response:
        return json.load(response)


def _client(base: str, tmp_path: Path) -> PackClient:
    return PackClient(
        base_url=base,
        install_root=tmp_path / "installed",
        registry_keyring={key_id(SERVER_KEY): "maintainer"},
        pack_keyring={key_id(SERVER_KEY): "maintainer"},
        require_signature=True,
    )


# ---------------------------------------------------------------------------
# Registry document
# ---------------------------------------------------------------------------


def test_the_registry_lists_signed_packs_with_their_metadata(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    for name in ("alpha-pack", "beta-pack"):
        sign_pack(new_draft(root / name, name, "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = build_registry(root)
    assert [entry["name"] for entry in document["packs"]] == ["alpha-pack", "beta-pack"]
    entry = document["packs"][0]
    assert entry["version"] == "0.1.0"
    assert entry["counts"] == {"riddles": 1}
    assert entry["files"], "the index must carry per-file hashes to check a download"


def test_the_registry_skips_a_directory_that_is_not_a_pack(tmp_path: Path) -> None:
    """Indexing something clients will reject turns a packaging mistake into a
    client-side failure with no maintainer-visible cause."""
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "good-pack", "good-pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    (root / "not-a-pack").mkdir()
    (root / "not-a-pack" / "readme.txt").write_text("hello", encoding="utf-8")
    document = build_registry(root)
    assert [entry["name"] for entry in document["packs"]] == ["good-pack"]
    assert document["skipped"] and "not-a-pack" in document["skipped"][0]


def test_a_signed_registry_verifies_and_reports_its_signer(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = sign_registry(build_registry(root), SERVER_KEY, signer="maintainer")
    result = verify_registry(document, SERVER_KEY)
    assert result["status"] == "valid"
    assert result["signer"] == "maintainer"


def test_adding_a_pack_to_a_signed_registry_is_detected(tmp_path: Path) -> None:
    """The list itself is what tells a client what to fetch, so it is signed too."""
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = sign_registry(build_registry(root), SERVER_KEY)
    document["packs"].append({"name": "injected", "version": "9", "digest": "deadbeef"})
    with pytest.raises(Exception, match="does not match its signature"):
        verify_registry(document, SERVER_KEY)


def test_reformatting_the_registry_does_not_invalidate_it(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = sign_registry(build_registry(root), SERVER_KEY)
    before = registry_digest(document)
    document["packs"] = [
        {key: value for key, value in sorted(entry.items())} for entry in document["packs"]
    ]
    assert registry_digest(document) == before
    assert verify_registry(document, SERVER_KEY)["status"] == "valid"


def test_an_unknown_registry_key_is_refused(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = sign_registry(build_registry(root), SERVER_KEY)
    from puzzle_service.submission import Policy, PolicyError

    with pytest.raises(PolicyError, match="unknown key"):
        verify_registry(document, SERVER_KEY, Policy(keyring={"k-someone-else": "?"}))


def test_an_unsigned_registry_is_refused_when_a_key_is_configured(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    document = build_registry(root)
    from puzzle_service.submission import Policy, PolicyError

    assert verify_registry(document)["status"] == "unsigned"
    with pytest.raises(PolicyError, match="unsigned"):
        verify_registry(document, None, Policy(required=True))


def test_a_newer_registry_version_is_refused_explicitly(tmp_path: Path) -> None:
    document = {"registry_version": REGISTRY_VERSION + 1, "packs": []}
    with pytest.raises(RegistryError, match="not supported"):
        verify_registry(document)


def test_entry_for_names_what_is_available(tmp_path: Path) -> None:
    root = tmp_path / "registry"
    sign_pack(new_draft(root / "pack", "pack", "zh", submitter="ada", license_name="CC0"), AUTHOR_KEY)
    _, entries = load_registry(
        _write(tmp_path / "registry.json", sign_registry(build_registry(root), SERVER_KEY)), SERVER_KEY
    )
    assert entry_for(entries, "pack").name == "pack"
    with pytest.raises(RegistryError, match="available"):
        entry_for(entries, "missing")


def _write(path: Path, document: dict) -> Path:
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Submitting
# ---------------------------------------------------------------------------


def test_a_submission_is_quarantined_not_published(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "community-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    record = service.submit("community-pack", {"submitter": "ada", "files": _bundle_files(draft)})
    assert record["status"] == "pending"
    assert (service.config.quarantine / "community-pack").is_dir()
    assert not (service.config.published / "community-pack").exists()
    assert service.registry_document()["packs"] == [], "a submission must not appear in the index"


def test_an_unsigned_submission_is_refused(service: PackService, tmp_path: Path) -> None:
    """For third-party content the signature is the only thing that is not a claim."""
    draft = new_draft(tmp_path / "draft", "unsigned-pack", "zh", submitter="ada", license_name="CC0")
    with pytest.raises(ValueError, match="signature refused"):
        service.submit("unsigned-pack", {"submitter": "ada", "files": _bundle_files(draft)})


def test_a_submission_signed_by_an_unknown_key_is_refused(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "stranger-pack", "zh", submitter="mallory", license_name="CC0")
    sign_pack(draft, OTHER_KEY, signer="mallory")
    with pytest.raises(ValueError, match="unknown key"):
        service.submit("stranger-pack", {"submitter": "mallory", "files": _bundle_files(draft)})


def test_a_tampered_submission_is_refused(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "tampered-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    files = _bundle_files(draft)
    riddles = json.loads(base64.b64decode(files["riddles.json"]))
    riddles["items"].append(
        {"id": "injected", "difficulty": "easy", "question": "x", "options": ["a", "b"], "answer": 0}
    )
    files["riddles.json"] = base64.b64encode(json.dumps(riddles).encode()).decode()
    with pytest.raises(ValueError, match="changed after it was signed"):
        service.submit("tampered-pack", {"submitter": "ada", "files": files})


def test_an_invalid_pack_body_is_refused(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "broken-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    files = _bundle_files(draft)
    manifest = json.loads(base64.b64decode(files["bundle.json"]))
    manifest["format_version"] = 999
    files["bundle.json"] = base64.b64encode(json.dumps(manifest).encode()).decode()
    with pytest.raises(ValueError, match="format_version"):
        service.submit("broken-pack", {"submitter": "ada", "files": files})


def test_a_name_that_is_not_a_safe_directory_name_is_refused(service: PackService) -> None:
    for bad in ("../escape", "a/b", ".", "..", "", "-leading", "x" * 80):
        with pytest.raises(ValueError, match="invalid pack name"):
            service.submit(bad, {"files": {"bundle.json": ""}})


def test_unexpected_files_are_refused(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "extra-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    files = _bundle_files(draft)
    files["payload.py"] = base64.b64encode(b"print('hi')").decode()
    with pytest.raises(ValueError, match="unexpected file"):
        service.submit("extra-pack", {"submitter": "ada", "files": files})


def test_the_same_name_cannot_be_submitted_twice(service: PackService, tmp_path: Path) -> None:
    """Overwriting could discard a submission that is already under review."""
    draft = new_draft(tmp_path / "draft", "twice-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    body = {"submitter": "ada", "files": _bundle_files(draft)}
    service.submit("twice-pack", body)
    with pytest.raises(ValueError, match="already quarantined"):
        service.submit("twice-pack", body)


# ---------------------------------------------------------------------------
# Accepting
# ---------------------------------------------------------------------------


def test_accept_publishes_and_re_signs_with_the_server_key(service: PackService, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "community-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    service.submit("community-pack", {"submitter": "ada", "files": _bundle_files(draft)})

    record = service.accept("community-pack", actor="maintainer")
    assert record["status"] == "accepted"
    published = service.config.published / "community-pack"
    assert (published / "manifest.json").is_file()
    # Re-signed by the server: the author's key signed the *draft*, the published pack
    # carries the key clients are configured to trust.
    signature = json.loads((published / "signature.json").read_text(encoding="utf-8"))
    assert signature["key_id"] == key_id(SERVER_KEY)
    assert pack_digest(load_pack(published)) == record["published_digest"]
    assert [entry["name"] for entry in service.registry_document()["packs"]] == ["community-pack"]


def test_accept_refuses_a_name_that_is_not_quarantined(service: PackService) -> None:
    with pytest.raises(ValueError, match="no quarantined submission"):
        service.accept("never-submitted")


def test_reject_records_the_reason_and_leaves_nothing_published(
    service: PackService, tmp_path: Path
) -> None:
    draft = new_draft(tmp_path / "draft", "rejected-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    service.submit("rejected-pack", {"submitter": "ada", "files": _bundle_files(draft)})
    record = service.reject("rejected-pack", actor="maintainer", reason="duplicate content")
    assert record["status"] == "rejected" and record["reason"] == "duplicate content"
    assert not (service.config.published / "rejected-pack").exists()
    assert service.status("rejected-pack")["status"] == "rejected"


def test_status_reports_unknown_for_a_pack_that_never_existed(service: PackService) -> None:
    assert service.status("ghost-pack")["status"] == "unknown"


# ---------------------------------------------------------------------------
# The client, over a real socket
# ---------------------------------------------------------------------------


def test_a_published_pack_reaches_a_client_and_installs(
    service: PackService, live: str, tmp_path: Path
) -> None:
    draft = new_draft(tmp_path / "draft", "community-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    service.submit("community-pack", {"submitter": "ada", "files": _bundle_files(draft)})
    client = _client(live, tmp_path)

    assert [entry.name for entry in client.fetch_registry()] == [], "quarantine is invisible"
    service.accept("community-pack")
    entries = client.fetch_registry()
    assert [entry.name for entry in entries] == ["community-pack"]

    result = client.install(entries[0])
    assert result.status == "installed"
    assert (result.path / "manifest.json").is_file()
    assert client.installed_digest("community-pack") == entries[0].digest
    # The installed pack is playable, which is the only thing that actually matters.
    assert load_pack(result.path).content["riddles"]


def test_installing_twice_is_a_no_op(service: PackService, live: str, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "community-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    service.submit("community-pack", {"submitter": "ada", "files": _bundle_files(draft)})
    service.accept("community-pack")
    client = _client(live, tmp_path)
    entry = client.fetch_registry()[0]
    assert client.install(entry).status == "installed"
    again = client.install(entry)
    assert again.status == "unchanged" and again.installed is False


def test_a_tampered_bundle_is_refused_before_install(
    service: PackService, live: str, tmp_path: Path
) -> None:
    """The check that matters: content must not reach the install root unverified."""
    draft = new_draft(tmp_path / "draft", "community-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    service.submit("community-pack", {"submitter": "ada", "files": _bundle_files(draft)})
    service.accept("community-pack")

    # Corrupt the published bundle the way a hostile host or a bad disk would.
    published = service.config.published / "community-pack" / "riddles.json"
    payload = json.loads(published.read_text(encoding="utf-8"))
    payload["items"].append(
        {"id": "injected", "difficulty": "easy", "question": "x", "options": ["a", "b"], "answer": 0}
    )
    published.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    client = _client(live, tmp_path)
    entry = client.fetch_registry()[0]
    with pytest.raises(PackClientError, match="does not match the index|changed after it was signed"):
        client.install(entry)
    assert not (client.install_root / "community-pack").exists(), (
        "a refused download must leave nothing installed"
    )


def test_a_client_that_does_not_trust_the_registry_key_refuses_to_look(
    service: PackService, live: str, tmp_path: Path
) -> None:
    client = PackClient(
        base_url=live,
        install_root=tmp_path / "installed",
        registry_keyring={"k-someone-else": "?"},
        pack_keyring={key_id(SERVER_KEY): "maintainer"},
    )
    with pytest.raises(PackClientError, match="index refused"):
        client.fetch_registry()


def test_a_client_that_requires_a_signature_refuses_an_unsigned_pack(
    service: PackService, live: str, tmp_path: Path
) -> None:
    """An open server is a development setting; the client decides for itself."""
    # Written into the *served* published directory, not a fresh one: a test that
    # populates a different directory than the running server reads proves nothing.
    unsigned = service.config.published / "unsigned-pack"
    unsigned.mkdir(parents=True)
    draft = new_draft(tmp_path / "draft", "unsigned-pack", "zh", submitter="ada", license_name="CC0")
    for path in draft.iterdir():
        if path.name == "signature.json":
            continue  # the point of this test
        (unsigned / path.name).write_bytes(path.read_bytes())

    client = PackClient(
        base_url=live, install_root=tmp_path / "installed", require_signature=True
    )
    entry = next(e for e in client.fetch_registry() if e.name == "unsigned-pack")
    with pytest.raises(PackClientError, match="pack refused"):
        client.install(entry)
    assert not (client.install_root / "unsigned-pack").exists()


def test_the_registry_endpoint_is_served(live: str) -> None:
    document = _get(live, "/registry.json")
    assert document["registry_version"] == REGISTRY_VERSION
    assert verify_registry(document, SERVER_KEY)["status"] == "valid"


def test_an_unknown_pack_is_a_404(live: str) -> None:
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        _get(live, "/packs/ghost-pack.json")
    assert excinfo.value.code == 404


def test_a_path_traversal_attempt_is_refused(live: str) -> None:
    for path in ("/packs/..%2F..%2Fetc%2Fpasswd.json", "/packs/....json", "/packs/a/b.json"):
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(live, path)
        assert excinfo.value.code in (400, 404)


def test_submitting_over_http_works_and_needs_no_accept(
    service: PackService, live: str, tmp_path: Path
) -> None:
    draft = new_draft(tmp_path / "draft", "http-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    record = _post(live, "/submit", {"name": "http-pack", "submitter": "ada", "files": _bundle_files(draft)})
    assert record["status"] == "pending"
    assert service.status("http-pack")["status"] == "pending"
    assert [row["name"] for row in _get(live, "/submissions")["submissions"]] == ["http-pack"]


def test_an_oversized_body_is_refused_without_reading_it_all(live: str) -> None:
    body = json.dumps({"name": "huge-pack", "files": {"bundle.json": "A" * (MAX_BODY + 1024)}}).encode()
    request = urllib.request.Request(
        live + "/submit", data=body, headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=10)
    assert excinfo.value.code == 413


def test_a_malformed_body_is_a_400(live: str) -> None:
    request = urllib.request.Request(
        live + "/submit", data=b"{not json", headers={"Content-Type": "application/json"}
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=10)
    assert excinfo.value.code == 400


def test_accept_over_http_publishes(service: PackService, live: str, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "http-accept-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    _post(live, "/submit", {"name": "http-accept-pack", "submitter": "ada", "files": _bundle_files(draft)})
    record = _post(live, "/accept/http-accept-pack", {"actor": "maintainer"})
    assert record["status"] == "accepted"
    assert [entry["name"] for entry in service.registry_document()["packs"]] == ["http-accept-pack"]


def test_a_submission_cannot_publish_itself(service: PackService, tmp_path: Path) -> None:
    """No request may cause content to go live; only `accept` does, and it is separate."""
    draft = new_draft(tmp_path / "draft", "sneaky-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    body = {"name": "sneaky-pack", "submitter": "ada", "files": _bundle_files(draft)}
    body["status"] = "accepted"  # a client-supplied field the server must ignore
    body["published"] = True
    record = service.submit("sneaky-pack", body)
    assert record["status"] == "pending"
    assert not (service.config.published / "sneaky-pack").exists()


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def test_the_rate_limiter_allows_a_burst_then_refuses() -> None:
    limiter = RateLimiter(capacity=3, refill_seconds=10.0)
    assert [limiter.allow("1.2.3.4", now=0.0) for _ in range(3)] == [True, True, True]
    assert limiter.allow("1.2.3.4", now=0.0) is False
    # Another caller is unaffected: the limit is per client.
    assert limiter.allow("5.6.7.8", now=0.0) is True
    # And it refills.
    assert limiter.allow("1.2.3.4", now=10.0) is True


def test_a_rate_limited_submission_gets_429(live: str, tmp_path: Path) -> None:
    draft = new_draft(tmp_path / "draft", "flood-pack", "zh", submitter="ada", license_name="CC0")
    sign_pack(draft, AUTHOR_KEY, signer="ada")
    files = _bundle_files(draft)
    codes = []
    for index in range(14):
        try:
            _post(live, "/submit", {"name": f"flood-{index}", "submitter": "ada", "files": files})
            codes.append(201)
        except urllib.error.HTTPError as exc:
            codes.append(exc.code)
    assert 429 in codes, f"expected a 429 in {codes}"
