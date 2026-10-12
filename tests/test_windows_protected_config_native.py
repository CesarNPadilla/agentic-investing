import ctypes
import json
import subprocess
import sys
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from security.windows_protected_config import ROOT, ProtectedConfigReader, load_guardian_config

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Native Windows handles required")

PREPARE = r"""
$ErrorActionPreference='Stop'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent()
if(-not ([Security.Principal.WindowsPrincipal]::new($owner)).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Elevated engineering fixture required.'}
$guardian=Get-LocalUser AgenticGuardian
if($guardian.Enabled -or (Get-LocalUser AgenticPaperRuntime).Enabled){throw 'Disabled identities required.'}
$path='C:\ProgramData\AgenticInvestingGuardian\Code\HostConfig-IDENTIFIER.json'
$stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$b=[Text.Encoding]::UTF8.GetBytes('synthetic bounded config');$stream.Write($b,0,$b.Length);$stream.Flush($true)}finally{$stream.Dispose()}
$admin=[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
$system=[Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$acl=[Security.AccessControl.FileSecurity]::new();$acl.SetOwner($admin);$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @($owner.User,$guardian.SID,$admin,$system)){
 $rights=if($sid -eq $admin -or $sid -eq $system){'FullControl'}else{'ReadAndExecute'}
 $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,$rights,'Allow'))
}
Set-Acl -LiteralPath $path -AclObject $acl
@{path=$path;owner=$owner.User.Value;guardian=$guardian.SID.Value} | ConvertTo-Json -Compress
"""


def powershell(code):
    result = subprocess.run(
        [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            code,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode:
        pytest.fail(
            "Protected dummy fixture preparation failed; diagnostics retained in subprocess result"
        )
    return result.stdout


@pytest.fixture
def protected():
    # Retain dummy files; do not delete evidence or change existing deployment ACLs.
    return json.loads(powershell(PREPARE.replace("IDENTIFIER", uuid4().hex)))


def read(value):
    return ProtectedConfigReader().read(
        value["path"], owner_sid=value["owner"], guardian_sid=value["guardian"]
    )


def test_exact_native_protected_read(protected):
    assert read(protected) == b"synthetic bounded config"


@pytest.mark.parametrize("mutation", ["write-grant", "owner", "unprotected"])
def test_changed_protection_rejected(protected, mutation):
    path = protected["path"]
    code = "$ErrorActionPreference='Stop';$p='" + path + "';$a=Get-Acl -LiteralPath $p;"
    if mutation == "write-grant":
        code += (
            "$a.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('"
            + protected["guardian"]
            + "'),'Modify','Allow'));"
        )
    elif mutation == "owner":
        code += "$a.SetOwner([Security.Principal.WindowsIdentity]::GetCurrent().User);"
    else:
        code += "$a.SetAccessRuleProtection($false,$true);"
    powershell(code + "Set-Acl -LiteralPath $p -AclObject $a")
    with pytest.raises(ValueError):
        read(protected)


def test_hard_link_rejected(protected):
    link = str(ROOT / "Code" / ("dummy-link-" + uuid4().hex))
    powershell(
        "New-Item -ItemType HardLink -Path '"
        + link
        + "' -Target '"
        + protected["path"]
        + "' | Out-Null"
    )
    with pytest.raises(ValueError):
        read(protected)


def test_oversized_rejected(protected):
    powershell("[IO.File]::WriteAllBytes('" + protected["path"] + "',[byte[]]::new(32769))")
    with pytest.raises(ValueError):
        read(protected)


@pytest.mark.parametrize(
    "path",
    [
        r"C:\untrusted\HostConfig-a.json",
        str(ROOT / "Code" / "nested" / "HostConfig-a.json"),
        str(ROOT / "Code" / "HostConfig-a.json:stream"),
    ],
)
def test_noncanonical_location_rejected(path):
    with pytest.raises(ValueError):
        ProtectedConfigReader().read(path, owner_sid="owner", guardian_sid="guardian")


def test_unqualified_process_rejected_before_file_read():
    with pytest.raises(PermissionError):
        load_guardian_config(
            str(ROOT / "Code" / ("HostConfig-" + "0" * 32 + ".json")),
            owner_sid="synthetic",
            guardian_sid="not-current-identity",
            expected_sha256="0" * 64,
            expected_manifest_sha256="0" * 64,
            now=datetime.now(UTC),
        )


def test_held_file_denies_write_open(protected, monkeypatch):
    reader = ProtectedConfigReader()
    original = reader._check
    observed = []

    def check(handle, **kwargs):
        original(handle, **kwargs)
        if not kwargs["directory"]:
            other = reader.kernel.CreateFileW(protected["path"], 0x40000000, 7, None, 3, 0, None)
            error = ctypes.get_last_error()
            if other != ctypes.c_void_p(-1).value:
                reader.kernel.CloseHandle(other)
                pytest.fail("Write open unexpectedly accepted during held read")
            assert error == 32
            observed.append(True)

    monkeypatch.setattr(reader, "_check", check)
    assert (
        reader.read(
            protected["path"], owner_sid=protected["owner"], guardian_sid=protected["guardian"]
        )
        == b"synthetic bounded config"
    )
    assert len(observed) == 2


def test_reparse_configuration_rejected(protected):
    link = str(ROOT / "Code" / ("HostConfig-" + uuid4().hex + ".json"))
    powershell(
        "New-Item -ItemType SymbolicLink -Path '"
        + link
        + "' -Target '"
        + protected["path"]
        + "' | Out-Null"
    )
    with pytest.raises(ValueError):
        ProtectedConfigReader().read(
            link, owner_sid=protected["owner"], guardian_sid=protected["guardian"]
        )
