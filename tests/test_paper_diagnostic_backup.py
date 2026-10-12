import json
import sqlite3

import pytest

from risk.paper_state import PaperState
from security.paper_diagnostic_backup import create_diagnostic_backup


def setup(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    source = tmp_path / "state.sqlite"
    state = PaperState.initialize(source, account_binding="a" * 64)
    state.latch("SOURCE_GATE_PENDING")
    with state.transaction() as data:
        data["paper_readonly_service_sessions"] = {"interrupted": {"status": "RUNNING"}}
    return repo, source, state


def test_snapshot_preserves_failure_records_and_source_bytes(tmp_path):
    repo, source, state = setup(tmp_path)
    before = source.read_bytes()
    target = tmp_path / "backup.sqlite"
    report = create_diagnostic_backup(source, target, repository_root=repo)
    assert source.read_bytes() == before
    assert PaperState(target).read() == state.read()
    assert report["latched"] is True
    assert report["restore_authorized"] is False
    assert report["execution_available"] is False
    assert "a" * 64 not in json.dumps(report)


def test_existing_destination_is_never_overwritten(tmp_path):
    repo, source, _ = setup(tmp_path)
    target = tmp_path / "backup.sqlite"
    target.write_bytes(b"retain this")
    with pytest.raises(FileExistsError):
        create_diagnostic_backup(source, target, repository_root=repo)
    assert target.read_bytes() == b"retain this"


@pytest.mark.parametrize("private_source", [True, False])
def test_repository_paths_rejected(tmp_path, private_source):
    repo, source, _ = setup(tmp_path)
    target = repo / "backup.sqlite" if private_source else tmp_path / "backup.sqlite"
    if not private_source:
        source = repo / "state.sqlite"
        PaperState.initialize(source, account_binding="a" * 64)
    with pytest.raises(ValueError):
        create_diagnostic_backup(source, target, repository_root=repo)
    assert not target.exists()


def test_corrupt_source_is_not_backed_up(tmp_path):
    repo, source, _ = setup(tmp_path)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE state SET digest='corrupt'")
    target = tmp_path / "backup.sqlite"
    with pytest.raises(ValueError):
        create_diagnostic_backup(source, target, repository_root=repo)
    assert not target.exists()
