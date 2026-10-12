import base64
import json
import subprocess
import time
from uuid import uuid4

import pytest

from security.webull_request_journal import RequestJournal
from security.windows_local_request_pipe import LocalRequestPipe
from security.windows_pipe_identity import NativePipeIdentity


def make_pipe():
    owner = NativePipeIdentity().read_process_identity()
    return LocalRequestPipe(owner_sid=owner, runtime_sid="S-1-5-21-100-200-300-9999")


def test_actual_pipe_owner_and_runtime_permissions_are_restricted():
    pipe = make_pipe()
    try:
        assert pipe._security_text(5) == (
            f"O:{pipe.owner_sid}D:P(A;;FA;;;{pipe.owner_sid})"
            f"(A;;0x100083;;;{pipe.runtime_sid})"
        )
    finally:
        pipe.close()


def test_permission_readback_mismatch_closes_pipe(monkeypatch):
    original = LocalRequestPipe._security_text
    closed = []
    original_close = LocalRequestPipe.close

    def changed(pipe, info):
        return "D:(A;;GA;;;WD)" if info == 5 else original(pipe, info)

    def close(pipe):
        original_close(pipe)
        closed.append(pipe.handle)

    monkeypatch.setattr(LocalRequestPipe, "_security_text", changed)
    monkeypatch.setattr(LocalRequestPipe, "close", close)
    with pytest.raises(OSError, match="protected permissions"):
        make_pipe()
    assert closed == [None]


def test_first_instance_rejects_existing_pipe_name(monkeypatch):
    import security.windows_local_request_pipe as transport

    fixed_id = uuid4()
    monkeypatch.setattr(transport, "uuid4", lambda: fixed_id)
    original = make_pipe()
    try:
        with pytest.raises(OSError, match="creation failed"):
            make_pipe()
        assert original.handle is not None
    finally:
        original.close()
    replacement = make_pipe()
    replacement.close()


def payload():
    return json.dumps(
        {
            "schema_version": "webull-control-request-v1",
            "action": "REQUEST_RESET_REVIEW",
            "account_binding_sha256": "a" * 64,
            "expected_state_sha256": "b" * 64,
            "request_id": str(uuid4()),
        }
    ).encode()


def launch_client(pipe, frame, *, fragment=False):
    encoded = base64.b64encode(frame).decode()
    write = "$client.Write($data,0,$data.Length);$client.Flush();"
    if fragment:
        write = "for($offset=0;$offset -lt $data.Length;$offset+=17){$count=[Math]::Min(17,$data.Length-$offset);$client.Write($data,$offset,$count);$client.Flush();Start-Sleep -Milliseconds 1};"
    code = (
        "$ErrorActionPreference='Stop';"
        "$rights=[IO.Pipes.PipeAccessRights]::ReadData -bor [IO.Pipes.PipeAccessRights]::WriteData -bor [IO.Pipes.PipeAccessRights]::ReadAttributes -bor [IO.Pipes.PipeAccessRights]::Synchronize;"
        "$client=[IO.Pipes.NamedPipeClientStream]::new('.', '"
        + pipe.name
        + "', $rights,[IO.Pipes.PipeOptions]::None,[Security.Principal.TokenImpersonationLevel]::Identification,[IO.HandleInheritability]::None);"
        "try{$client.Connect(3000);$data=[Convert]::FromBase64String('"
        + encoded
        + "');"
        + write
        + "Start-Sleep -Seconds 2}finally{$client.Dispose()}"
    )
    return subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def stop(process):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=5)


def test_fragmented_frame_identity_and_journal_registration(tmp_path):
    pipe = make_pipe()
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    body = payload()
    process = launch_client(pipe, len(body).to_bytes(4, "big") + body, fragment=True)
    try:
        receipt = pipe.register_one(journal)
        assert receipt["request_registered"] and receipt["observed_caller_role"] == "OWNER"
        assert not receipt["controller_admitted"] and not receipt["reset_performed"]
        assert not receipt["execution_available"] and not receipt["trial_started"]
        assert journal.verify()["retained_requests"] == 1
        assert pipe.handle is None
    finally:
        stop(process)
        pipe.close()


@pytest.mark.parametrize("length", [0, 4097])
def test_oversized_or_empty_frame_never_reaches_journal(tmp_path, length):
    pipe = make_pipe()
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    process = launch_client(pipe, length.to_bytes(4, "big"))
    try:
        with pytest.raises(ValueError, match="size"):
            pipe.register_one(journal)
        assert journal.verify()["retained_requests"] == 0
        assert pipe.handle is None
    finally:
        stop(process)
        pipe.close()


def test_missing_client_deadline_cancels_connect_and_closes_handle(tmp_path):
    pipe = make_pipe()
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        pipe.register_one(None, timeout_seconds=0.05)
    assert time.monotonic() - started < 2
    assert pipe.handle is None


def test_partial_body_deadline_has_no_registration(tmp_path):
    pipe = make_pipe()
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    process = launch_client(pipe, (100).to_bytes(4, "big") + b"{")
    try:
        with pytest.raises((TimeoutError, OSError)):
            pipe.register_one(journal, timeout_seconds=0.7)
        assert journal.verify()["retained_requests"] == 0
        assert pipe.handle is None
    finally:
        stop(process)
        pipe.close()


def test_invalid_json_never_registers_after_native_identity_check(tmp_path):
    pipe = make_pipe()
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    body = b'{"action":"CLEAR_LATCH"}'
    process = launch_client(pipe, len(body).to_bytes(4, "big") + body)
    try:
        with pytest.raises(ValueError, match="Untrusted"):
            pipe.register_one(journal)
        assert journal.verify()["retained_requests"] == 0
    finally:
        stop(process)
        pipe.close()


def test_native_transport_replay_across_new_connections(tmp_path):
    journal = RequestJournal.initialize(
        tmp_path / "journal.sqlite", "a" * 64, state_digest="b" * 64
    )
    body = payload()
    for duplicate in (False, True):
        pipe = make_pipe()
        process = launch_client(pipe, len(body).to_bytes(4, "big") + body)
        try:
            if duplicate:
                with pytest.raises(ValueError, match="replay"):
                    pipe.register_one(journal)
            else:
                assert pipe.register_one(journal)["request_registered"]
        finally:
            stop(process)
            pipe.close()
    assert journal.verify()["retained_requests"] == 1
