"""Exercise the wrapper's actual source extractor without credentials or accounts."""

import base64
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "source, expected",
    [
        ("CHILD = r'''print('fixture')\n'''\n", "print('fixture')\n"),
        ('CHILD = r"""print(\'fixture\')\n"""\n', "print('fixture')\n"),
        ("CHILD = 'fixture'\nraise RuntimeError('must not execute')\n", "fixture"),
        ("CHILD = str('fixture')\n", None),
        ("CHILD = 'first'\nCHILD = 'second'\n", None),
        ("OTHER = 'fixture'\n", None),
    ],
)
def test_wrapper_extractor_accepts_literals_and_never_executes_driver(tmp_path, source, expected):
    driver = tmp_path / "driver.py"
    driver.write_text(source, encoding="utf-8")
    code = r"""
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile((Join-Path $PWD 'scripts/test_webull_guardian_failure_paths.ps1'),[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Wrapper parse failed'}
$node=$ast.Find({param($n) $n -is [Management.Automation.Language.AssignmentStatementAst] -and $n.Left.Extent.Text -ceq '$extractChildSource'},$true)
if(-not $node){throw 'Extractor literal missing'}
$extract=$node.Right.Expression.Value
& 'C:\ProgramData\AgenticInvestingGuardian\Code\GuardianRelease-2cb10942c251ffec\python.exe' -I -B -c $extract $env:AGENTIC_EXTRACTOR_FIXTURE
if($LASTEXITCODE -ne 0){exit 1}
"""
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
        cwd=Path(__file__).resolve().parents[1],
        env=dict(os.environ, AGENTIC_EXTRACTOR_FIXTURE=str(driver)),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if expected is None:
        assert completed.returncode != 0
    else:
        assert completed.returncode == 0, completed.stderr
        assert base64.b64decode(completed.stdout.strip()).decode("utf-8") == expected
