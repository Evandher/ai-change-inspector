import json
import os
import sqlite3
from dataclasses import asdict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.analysis_models import AnalysisResponse, ModelReview
from app.audit_models import CaptureCoverage
from app.main import app
from app.models import ParseResponse
from app.review_models import ReviewCreate, ReviewError
from app.review_store import SCHEMA, ReviewRepository
from app.services import untracked_capture as capture
from app.services.diff_parser import parse_diff
from app.services.git_capture import AuthorizedRepository
from app.services.reference_validator import check_findings
from tests.test_analysis import review_body
from tests.test_parser import SIMPLE


def test_additive_migration_preserves_terminal_snapshots(tmp_path):
    db = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(db)
    connection.executescript(SCHEMA)
    identifier = str(uuid4())
    parsed = ParseResponse.model_validate(asdict(parse_diff(SIMPLE)))
    connection.execute(
        "INSERT INTO reviews VALUES (?,?,?,'mcp','unstaged',?,NULL,?,?,?,'completed',NULL,NULL)",
        (
            identifier,
            "demo",
            str(tmp_path),
            "2026-10-01T00:00:00+00:00",
            SIMPLE,
            "abc",
            parsed.model_dump_json(),
        ),
    )
    connection.commit()
    connection.close()
    store = ReviewRepository(db, "http://127.0.0.1:5173")
    old = store.get(identifier)
    assert old.diff == SIMPLE and old.status == "completed"
    assert old.agent_source == "unknown" and old.capture_coverage is None
    assert store.list(20, 0).items[0].agent_source == "unknown"
    with store.connection() as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE reviews SET agent_source='codex' WHERE review_id=?", (identifier,))


def test_sql_filters_pagination_literals_and_metadata_conflicts(tmp_path):
    store = ReviewRepository(tmp_path / "reviews.sqlite3", "http://127.0.0.1:5173")
    parsed = ParseResponse.model_validate(asdict(parse_diff(SIMPLE)))
    identifiers = []
    for source in ("muse_code", "codex", "unknown"):
        request = ReviewCreate(
            repository="demo",
            repository_root=str(tmp_path),
            scope="unstaged",
            diff=SIMPLE,
            agent_source=source,
            capture_coverage=CaptureCoverage(),
        )
        identifiers.append(store.create(request, parsed).review_id)
        assert store.get(identifiers[-1]).capture_coverage == CaptureCoverage()
        with pytest.raises(ReviewError, match="ID"):
            store.create(request.model_copy(update={"agent_source": "other"}), parsed)
    assert store.list(1, 0).total == 3
    assert store.list(1, 1).items[0].review_id != store.list(1, 0).items[0].review_id
    assert store.list(20, 0, agent_source="muse_code").items[0].review_id == identifiers[0]
    assert store.list(20, 0, q=identifiers[1][:12], repository="demo", status="pending").total == 1
    assert store.list(20, 0, repository="demo' OR 1=1--").total == 0
    assert store.list(20, 0, severity="high").total == 0
    assert store.list(20, 0, date_to="2000-01-01").total == 0
    model = ModelReview.model_validate(review_body())
    assert store.claim(identifiers[0])
    store.finish(
        identifiers[0],
        AnalysisResponse(
            model="muse-spark-1.3",
            summary=model.summary,
            parsed_diff=parsed,
            findings=check_findings(parse_diff(SIMPLE), model),
        ),
        None,
    )
    assert store.list(20, 0, severity="medium", agent_source="muse_code").total == 1
    assert store.list(20, 0, severity="critical").total == 0


def test_api_combined_filters_and_invalid_queries(tmp_path, monkeypatch):
    monkeypatch.setenv("INSPECTOR_REPOSITORIES", json.dumps({"demo": str(tmp_path)}))
    with TestClient(app, base_url="http://127.0.0.1:8000", client=("127.0.0.1", 50000)) as api:
        result = api.post(
            "/api/reviews",
            headers={"X-Inspector-Request": "1"},
            json={
                "repository": "demo",
                "repository_root": str(tmp_path),
                "scope": "staged",
                "diff": SIMPLE,
                "agent_source": "muse_code",
                "capture_coverage": {},
            },
        )
        assert result.status_code == 201
        identifier = result.json()["review_id"]
        assert (
            api.get(
                "/api/reviews",
                params={
                    "q": identifier[:8],
                    "agent_source": "muse_code",
                    "repository": "demo",
                    "status": "pending",
                },
            ).json()["total"]
            == 1
        )
        for params in (
            {"status": "invalid"},
            {"severity": "invalid"},
            {"agent_source": "fake"},
            {"date_from": "2026-12-31", "date_to": "2026-01-01"},
            {"q": "%"},
        ):
            assert api.get("/api/reviews", params=params).status_code == 422
        assert api.get("/api/reviews", params={"agent_source": "codex"}).json()["total"] == 0


def install_candidates(monkeypatch, names):
    def run(root, args, limit):
        assert args == ["ls-files", "--others", "--exclude-standard", "-z"]
        assert limit <= 65536
        return 0, b"".join(name.encode() + b"\0" for name in names)

    monkeypatch.setattr(capture, "_run_git", run)


def test_untracked_safe_reads_and_exclusions_never_leak_names(tmp_path, monkeypatch):
    (tmp_path / "new.py").write_bytes(b'print("hello")\r\nprint("world")')
    (tmp_path / ".env").write_text("MODEL_API_KEY=private-value")
    (tmp_path / "blob.txt").write_bytes(b"\0binary")
    (tmp_path / "large.py").write_bytes(b"x" * (capture.MAX_FILE_BYTES + 1))
    (tmp_path / "secret.py").write_text('password="a-very-private-password"')
    (tmp_path / "bad.txt").write_bytes(b"\xff")
    (tmp_path / "image.png").write_bytes(b"private image")
    names = [
        "new.py",
        ".env",
        "blob.txt",
        "large.py",
        "secret.py",
        "bad.txt",
        "image.png",
        "../escape.py",
    ]
    install_candidates(monkeypatch, names)
    text, coverage = capture.capture_untracked(AuthorizedRepository("demo", tmp_path.resolve()), "")
    assert coverage.included_untracked == ["new.py"]
    assert coverage.untracked_seen == len(names)
    assert sum(coverage.exclusions.values()) == len(names) - 1
    assert coverage.exclusions["sensitive"] == 2
    assert "private" not in text and ".env" not in coverage.model_dump_json()
    parsed = parse_diff(text)
    assert parsed.files[0].new_path == "new.py"
    assert parsed.files[0].hunks[0].lines[-1].no_newline
    assert (tmp_path / "new.py").read_bytes().endswith(b'print("world")')


def test_untracked_link_and_changed_file_fail_closed(tmp_path, monkeypatch):
    outside = tmp_path.parent / f"{uuid4()}.txt"
    outside.write_text("outside private content")
    try:
        try:
            (tmp_path / "link.py").symlink_to(outside)
        except OSError:
            # Hard links also must not be read.
            os.link(outside, tmp_path / "link.py")
        install_candidates(monkeypatch, ["link.py", "race.py"])
        original = capture.safe_read

        def safe_read(root, relative):
            if relative == "race.py":
                raise OSError("changed")
            return original(root, relative)

        monkeypatch.setattr(capture, "safe_read", safe_read)
        text, coverage = capture.capture_untracked(
            AuthorizedRepository("demo", tmp_path.resolve()), ""
        )
        assert text == "" and coverage.included_untracked == []
        assert coverage.exclusions["unsafe"] == 2
    finally:
        outside.unlink()


def test_untracked_bounds_and_duplicate_paths(tmp_path, monkeypatch):
    (tmp_path / "new.py").write_text("ok\n")
    install_candidates(monkeypatch, ["new.py"])
    text, coverage = capture.capture_untracked(AuthorizedRepository("demo", tmp_path.resolve()), "")
    same, coverage = capture.capture_untracked(
        AuthorizedRepository("demo", tmp_path.resolve()), text
    )
    assert same == text and coverage.exclusions == {"policy": 1}
    monkeypatch.setattr(capture, "MAX_DIFF_BYTES", 1)
    text, coverage = capture.capture_untracked(AuthorizedRepository("demo", tmp_path.resolve()), "")
    assert text == "" and coverage.exclusions == {"budget": 1}


def test_untracked_parent_reparse_and_open_writer_are_rejected(tmp_path):
    path = tmp_path / "test.py"
    path.write_bytes(b"safe\n")
    assert capture.safe_read(tmp_path.resolve(), "test.py") == b"safe\n"
    if os.name == "nt":
        with path.open("wb") as writer:
            writer.write(b"changing")
            writer.flush()
            with pytest.raises(OSError):
                capture.safe_read(tmp_path.resolve(), "test.py")


def test_capture_propagates_metadata_through_mcp_without_provider(tmp_path, monkeypatch):
    from app import mcp_server

    root = tmp_path.resolve()
    (root / "new.py").write_bytes(b"print(1)\n")
    repository = AuthorizedRepository("demo", root)
    install_candidates(monkeypatch, ["new.py"])
    monkeypatch.setattr(mcp_server, "capture_changes", lambda *_: "")
    store = ReviewRepository(root / ".local" / "temporary.sqlite3", "http://127.0.0.1:5173")

    def submit(
        repo, scope, text, url, parent=None, *, agent_source="unknown", capture_coverage=None
    ):
        assert repo == repository and parent is None
        request = ReviewCreate(
            repository=repo.name,
            repository_root=str(repo.root),
            scope=scope,
            diff=text,
            agent_source=agent_source,
            capture_coverage=capture_coverage,
        )
        return store.create(request, ParseResponse.model_validate(asdict(parse_diff(text))))

    monkeypatch.setattr(mcp_server, "submit_review", submit)
    default = mcp_server.inspect_repository({"demo": repository}, "demo", "unstaged")
    assert default.status == "no_changes" and store.list(20, 0).total == 0
    result = mcp_server.inspect_repository(
        {"demo": repository}, "demo", "staged", include_untracked=True, agent_source="muse_code"
    )
    assert result.status == "pending" and result.registration_confirmed
    assert result.untracked_policy == "requested"
    stored = store.get(result.review_id)
    assert stored.agent_source == "muse_code"
    assert stored.capture_coverage.included_untracked == ["new.py"]


def test_windows_parent_junction_is_not_followed(tmp_path):
    if os.name != "nt":
        pytest.skip("Windows junction control")
    import subprocess

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.py").write_text("private content")
    junction = root / "linked"
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(outside)],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        pytest.skip("Junction creation unavailable")
    try:
        with pytest.raises(OSError):
            capture.safe_read(root.resolve(), "linked/file.py")
    finally:
        junction.rmdir()


@pytest.mark.parametrize("scope", ["staged", "unstaged"])
def test_real_git_untracked_capture_does_not_create_index(tmp_path, scope):
    import subprocess

    from app.services.git_capture import capture_changes

    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_bytes(b"ignored.md\n")
    (root / "new.py").write_bytes(b"print(1)\r\n")
    (root / "ignored.md").write_text("not captured")
    (root / ".env").write_text("private credentials")
    repository = AuthorizedRepository("demo", root.resolve())
    assert not (root / ".git" / "index").exists()
    tracked = capture_changes(repository, scope)
    text, coverage = capture.capture_untracked(repository, tracked)
    assert coverage.included_untracked == ["new.py"]
    assert coverage.untracked_seen == 3
    assert coverage.exclusions == {"sensitive": 1, "policy": 1}
    assert "ignored.md" not in text and "private credentials" not in text
    assert not (root / ".git" / "index").exists()
    assert (root / "new.py").read_bytes() == b"print(1)\r\n"
