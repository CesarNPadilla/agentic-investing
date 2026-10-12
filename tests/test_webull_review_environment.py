import pytest

from security.webull_review_environment import dependencies, safe_name, stage_environment


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:/escape", "a\\b", "a//b", ""])
def test_unsafe_payload_paths_rejected(path):
    with pytest.raises(ValueError):
        safe_name(path)


def test_dependency_set_is_satisfied_and_excludes_broker_sdk():
    found = dependencies()
    assert {"fastapi", "uvicorn", "fido2", "pydantic", "cryptography"} <= set(found)
    assert not any("webull" in name or "alpaca" in name for name in found)


def test_wrong_archive_does_not_create_destination(tmp_path):
    archive = tmp_path / "wrong.zip"
    archive.write_bytes(b"invalid")
    destination = tmp_path / "environment"
    with pytest.raises(ValueError, match="digest"):
        stage_environment(archive, destination)
    assert not destination.exists()
