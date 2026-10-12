"""Reject changed base environment and prevent staged package replacement."""

import hashlib
import json
from pathlib import Path

import pytest

from security import webull_guardian_release as release


def environment(tmp_path, monkeypatch):
    base = tmp_path / "base"
    base.mkdir()
    (base / "python314._pth").write_bytes(b"old-path\n")
    raw = json.dumps(
        {"files": {"python314._pth": hashlib.sha256(b"old-path\n").hexdigest()}}
    ).encode()
    (base / "environment-release.json").write_bytes(raw)
    monkeypatch.setattr(release, "ENVIRONMENT_MANIFEST_SHA256", hashlib.sha256(raw).hexdigest())
    return base


def test_manifest_binds_fixed_paths_and_all_guardian_sources(tmp_path, monkeypatch):
    base = environment(tmp_path, monkeypatch)
    destination = tmp_path / "staged"
    digest = release.stage_guardian(Path.cwd(), base, destination)
    raw = (destination / "guardian-release.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == digest
    manifest = json.loads(raw)
    assert set(manifest["files"]) == {"python314._pth", *("app/" + p for p in release.FILES)}
    assert (destination / "python314._pth").read_bytes() == b"python314.zip\n.\npackages\napp\n"
    assert not manifest["execution_available"]


@pytest.mark.parametrize("name", ["environment-release.json", "python314._pth"])
def test_base_drift_does_not_create_destination(tmp_path, monkeypatch, name):
    base = environment(tmp_path, monkeypatch)
    (base / name).write_bytes(b"changed")
    destination = tmp_path / "staged"
    with pytest.raises(ValueError, match="changed"):
        release.stage_guardian(Path.cwd(), base, destination)
    assert not destination.exists()


def test_existing_destination_is_not_replaced(tmp_path, monkeypatch):
    base = environment(tmp_path, monkeypatch)
    destination = tmp_path / "staged"
    destination.mkdir()
    with pytest.raises(FileExistsError):
        release.stage_guardian(Path.cwd(), base, destination)
    assert list(destination.iterdir()) == []


def test_staging_inside_checkout_rejected_before_read(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        release.stage_guardian(tmp_path, tmp_path / "base", tmp_path / "staged")
