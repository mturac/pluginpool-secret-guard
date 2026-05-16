import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "guard.py"


def run_guard(tmp_path, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )


def write_secret_file(tmp_path, secret):
    path = tmp_path / "fixture.txt"
    path.write_text(f"token={secret}\n", encoding="utf-8")
    return path


def test_positive_fixture_for_each_named_pattern(tmp_path):
    secrets = {
        "AWS Access Key": "AKIAAAAAAAAAAAAAAAAA",
        "GitHub PAT": "ghp_" + "A" * 36,
        "Slack token": "xoxb-" + "A" * 12,
        "Stripe": "sk_test_" + "A" * 24,
        "Google API": "AIza" + "A" * 35,
        "JWT": "eyJ" + "A" * 8 + ".eyJ" + "B" * 8 + "." + "C" * 8,
        "Private key": "-----BEGIN PRIVATE KEY-----",
    }
    for expected, secret in secrets.items():
        path = write_secret_file(tmp_path, secret)
        result = run_guard(tmp_path, "--files", str(path))
        data = json.loads(result.stdout)
        assert result.returncode == 1
        assert any(item["pattern"] == expected for item in data)
        assert secret not in result.stdout


def test_entropy_fallback(tmp_path):
    secret = "abcdEFGHijklMNOPqrstUVWXyz0123456789+/="
    path = write_secret_file(tmp_path, secret)
    result = run_guard(tmp_path, "--files", str(path))
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert data[0]["pattern"] == "Generic high-entropy"
    assert secret not in result.stdout


def test_allowlist_suppression(tmp_path):
    secret = "AKIAAAAAAAAAAAAAAAAA"
    path = write_secret_file(tmp_path, secret)
    allowlist = tmp_path / ".allow"
    allowlist.write_text("AKIAAAAA\n", encoding="utf-8")
    result = run_guard(tmp_path, "--files", str(path), "--allowlist", str(allowlist))
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_redaction_contains_only_rule_and_first_four(tmp_path):
    secret = "sk_live_" + "B" * 24
    path = write_secret_file(tmp_path, secret)
    result = run_guard(tmp_path, "--files", str(path))
    item = json.loads(result.stdout)[0]
    assert item["snippet_redacted"] == "Stripe: sk_l\u2026"
    assert secret not in result.stdout


def test_exit_code_zero_on_clean_file(tmp_path):
    path = tmp_path / "clean.txt"
    path.write_text("name=value\n", encoding="utf-8")
    result = run_guard(tmp_path, "--files", str(path))
    assert result.returncode == 0
    assert json.loads(result.stdout) == []


def test_files_mode_reports_file_and_line(tmp_path):
    path = tmp_path / "fixture.txt"
    path.write_text("clean\nxoxp-AAAAAAAAAAAA\n", encoding="utf-8")
    result = run_guard(tmp_path, "--files", str(path))
    item = json.loads(result.stdout)[0]
    assert item["file"] == str(path)
    assert item["line"] == 2
    assert item["pattern"] == "Slack token"


def test_markdown_format_redacted(tmp_path):
    secret = "gho_" + "C" * 36
    path = write_secret_file(tmp_path, secret)
    result = run_guard(tmp_path, "--files", str(path), "--format", "md")
    assert result.returncode == 1
    assert "# secret-guard report" in result.stdout
    assert "GitHub PAT: gho_\u2026" in result.stdout
    assert secret not in result.stdout


def test_staged_diff_added_lines_default(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    path = tmp_path / "staged.txt"
    path.write_text("token=AKIAAAAAAAAAAAAAAAAA\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.txt"], cwd=tmp_path, check=True, capture_output=True, text=True)
    result = run_guard(tmp_path)
    data = json.loads(result.stdout)
    assert result.returncode == 1
    assert data[0]["file"] == "staged.txt"
    assert data[0]["line"] == 1


def test_help_works():
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], text=True, capture_output=True)
    assert result.returncode == 0
    assert "Scan staged diffs" in result.stdout


def test_files_mode_does_not_crash_on_non_utf8(tmp_path):
    """secret-guard --files must not raise UnicodeDecodeError on binary or latin-1 files."""
    import json
    import subprocess
    import sys
    from pathlib import Path
    script = Path(__file__).resolve().parent.parent / "scripts" / "guard.py"
    bin_path = tmp_path / "blob.bin"
    bin_path.write_bytes(b"\x00\x01\x02\xff\xfeAKIA" + b"A" * 16 + b"\n")  # binary with embedded "key"
    latin = tmp_path / "latin.txt"
    latin.write_bytes("naïve résumé\n".encode("latin-1"))
    r = subprocess.run(
        [sys.executable, str(script), "--files", str(bin_path), str(latin), "--format", "json"],
        capture_output=True, text=True,
    )
    assert r.returncode in (0, 1), f"unexpected crash: stderr={r.stderr}"
    json.loads(r.stdout)  # output is valid JSON
