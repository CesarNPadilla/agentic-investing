import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from security.webull_review_release import FILES, MANIFEST, build_release, verify_release

ROOT = Path(__file__).resolve().parents[1]


def setup(tmp_path):
    result = build_release(ROOT, tmp_path / "bundle")
    return Path(result["source_bundle"]), result["manifest_sha256"]


def test_pinned_source_release_excludes_credentials_and_refuses_overwrite(tmp_path):
    path, digest = setup(tmp_path)
    record = verify_release(path, digest)
    assert set(record["files"]) == set(FILES)
    assert record["execution_available"] is False
    with pytest.raises(FileExistsError):
        build_release(ROOT, path)


@pytest.mark.parametrize(
    "change", ["source", "extra", "missing", "wrong_digest", "scope", "path_escape"]
)
def test_altered_bundle_is_rejected_by_python_and_owner_validation(tmp_path, change):
    path, digest = setup(tmp_path)
    if change == "source":
        (path / FILES[0]).write_text("changed")
    elif change == "extra":
        (path / "unexpected.env").write_text("dummy only")
    elif change == "missing":
        (path / FILES[0]).unlink()
    elif change == "wrong_digest":
        digest = "0" * 64
    else:
        file = path / MANIFEST
        record = json.loads(file.read_text())
        if change == "scope":
            record["execution_available"] = True
        else:
            record["files"]["../outside.py"] = "a" * 64
        file.write_text(json.dumps(record))
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        verify_release(path, digest)
    result = run_installer(path, digest)
    assert result.returncode != 0


def run_installer(path, digest):
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(ROOT / "scripts/install_webull_review_source.ps1"),
            "-SourceBundle",
            str(path),
            "-ExpectedManifestSha256",
            digest,
            "-ValidateOnly",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def test_actual_owner_validator_accepts_exact_release_without_installing(tmp_path):
    path, digest = setup(tmp_path)
    result = run_installer(path, digest)
    assert result.returncode == 0, result.stderr
    assert "No installation performed" in result.stdout
    assert verify_release(path, digest)["execution_available"] is False


def test_legacy_installed_inventory_remains_supported_without_rewriting(tmp_path):
    path, _ = setup(tmp_path)
    (path / "security/webull_guarded_review.py").unlink()
    file = path / MANIFEST
    record = json.loads(file.read_text())
    record["schema_version"] = "webull-review-source-release-v1"
    del record["files"]["security/webull_guarded_review.py"]
    file.write_text(json.dumps(record))
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    assert verify_release(path, digest)["schema_version"] == "webull-review-source-release-v1"
    assert run_installer(path, digest).returncode == 0


def test_version_two_cannot_omit_guarded_review_dependency(tmp_path):
    path, _ = setup(tmp_path)
    (path / "security/webull_guarded_review.py").unlink()
    file = path / MANIFEST
    record = json.loads(file.read_text())
    del record["files"]["security/webull_guarded_review.py"]
    file.write_text(json.dumps(record))
    digest = hashlib.sha256(file.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="inventory"):
        verify_release(path, digest)
    assert run_installer(path, digest).returncode != 0


def test_staging_inside_checkout_is_refused_before_creation():
    with pytest.raises(ValueError, match="outside"):
        build_release(ROOT, ROOT / "forbidden-release-staging")
