from pathlib import Path

import pytest

from app.inspection_models import InspectionError
from app.services.diff_parser import parse_diff
from app.services.egress_guard import check_egress
from tests.test_parser import SIMPLE


@pytest.mark.parametrize(
    "name",
    [
        ".env",
        ".env.example",
        "config/.env.production",
        ".aws/credentials",
        ".ssh/id_rsa",
        "server.key",
        "cert.pem",
        "credentials.json",
        "secrets.yaml",
        "Tokens.json",
        ".npmrc",
        "../outside.txt",
        "/absolute.txt",
        "C:/outside.txt",
        "folder\\outside.txt",
    ],
)
def test_sensitive_or_escaping_paths_are_blocked(tmp_path, name):
    text = SIMPLE.replace("a.txt", name)
    with pytest.raises(InspectionError) as exc:
        check_egress(tmp_path, text, parse_diff(text))
    assert exc.value.blocked
    assert exc.value.code in {"sensitive_path", "unsafe_diff_path"}
    assert "new" not in str(exc.value)


@pytest.mark.parametrize(
    "value",
    [
        "-----BEGIN RSA PRIVATE KEY-----",
        "AKIA" + "A" * 16,
        "ghp_" + "a" * 30,
        "xoxb-" + "a" * 20,
        "Bearer " + "token" * 5,
        'password = "example-sensitive-value"',
        'MODEL_API_KEY="example-sensitive-value"',
        "https://user:password@example.test/a",
    ],
)
def test_secret_patterns_in_old_and_new_lines_are_blocked(tmp_path, value):
    for prefix in ("-old", "+new"):
        text = SIMPLE.replace(prefix, prefix[0] + value)
        with pytest.raises(InspectionError) as exc:
            check_egress(tmp_path, text, parse_diff(text))
        assert exc.value.code == "possible_secret"
        assert value not in str(exc.value)


def test_actual_provider_key_is_never_sent(tmp_path, monkeypatch):
    key = "opaque-local-test-key"
    monkeypatch.setenv("MODEL_API_KEY", key)
    text = SIMPLE.replace("+new", "+" + key)
    with pytest.raises(InspectionError) as exc:
        check_egress(tmp_path, text, parse_diff(text))
    assert exc.value.code == "possible_secret"


def test_normal_diff_and_deleted_paths_are_allowed(tmp_path):
    check_egress(tmp_path, SIMPLE, parse_diff(SIMPLE))
    text = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"
    check_egress(tmp_path, text, parse_diff(text))


def test_symlinks_and_links_to_outside_are_blocked(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(
        Path, "is_symlink", lambda path: path == tmp_path / "a.txt" or original(path)
    )
    with pytest.raises(InspectionError) as exc:
        check_egress(tmp_path, SIMPLE, parse_diff(SIMPLE))
    assert exc.value.code == "unsafe_diff_path"
