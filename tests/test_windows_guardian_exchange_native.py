"""Native framing under engineering identities; guardian caller identity is mocked."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from security.windows_guardian_exchange_pipe import GuardianExchangePipe
from security.windows_guardian_request_pipe import GuardianRequestPipe
from security.windows_pipe_identity import NativePipeIdentity

CLIENT = r"""
param([string]$PipeName,[string]$Receipt)
$ErrorActionPreference='Stop'
$pipe=[IO.Pipes.NamedPipeClientStream]::new('.', $PipeName, [IO.Pipes.PipeDirection]::InOut)
try {
 $pipe.Connect(3000)
 $frame=[byte[]](0,0,0,2,123,125)
 $pipe.Write($frame,0,$frame.Length)
 function Read-Exact([int]$size) {
  $bytes=New-Object byte[] $size
  $offset=0
  while($offset -lt $size) {
   $count=$pipe.Read($bytes,$offset,$size-$offset)
   if($count -le 0){throw 'Incomplete reply'}
   $offset+=$count
  }
  return ,$bytes
 }
 $header=Read-Exact 4
 $size=([int]$header[0]*16777216)+([int]$header[1]*65536)+([int]$header[2]*256)+[int]$header[3]
 if($size -lt 1 -or $size -gt 4096){throw 'Invalid reply size'}
 $body=Read-Exact $size
 if($Receipt -eq 'valid'){$pipe.WriteByte(1)}
 elseif($Receipt -eq 'invalid'){$pipe.WriteByte(0)}
 else {Start-Sleep -Milliseconds 4000}
 [Text.Encoding]::UTF8.GetString($body)
} finally {$pipe.Dispose()}
"""


@pytest.mark.skipif(os.name != "nt", reason="Windows native pipes required")
@pytest.mark.parametrize("receipt", ["valid", "invalid", "missing"])
def test_native_reply_delivery_and_receipt_failure(monkeypatch, tmp_path, receipt):
    sid = NativePipeIdentity().read_process_identity()
    result = {"execution_available": False, "reset_authorized": False}
    # Exercise kernel framing/delivery only; do not claim cross-account authentication.
    monkeypatch.setattr(GuardianRequestPipe, "_dispatch", lambda *_: result)
    pipe = GuardianExchangePipe(guardian_sid=sid, owner_sid="S-1-5-21-100-200-300-9999")
    script = tmp_path / "client.ps1"
    script.write_text(CLIENT, encoding="utf-8")
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    process = subprocess.Popen(
        [
            str(powershell),
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            "-PipeName",
            pipe.name,
            "-Receipt",
            receipt,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        if receipt == "valid":
            assert pipe.register_one(object(), timeout_seconds=3) == result
        elif receipt == "invalid":
            with pytest.raises(ValueError, match="receipt"):
                pipe.register_one(object(), timeout_seconds=3)
        else:
            with pytest.raises(TimeoutError):
                pipe.register_one(object(), timeout_seconds=3)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        assert json.loads(stdout) == result
        assert pipe.handle is None
    finally:
        pipe.close()
        if process.poll() is None:
            process.kill()
        process.communicate(timeout=5)
