import json
from pathlib import Path
from shutil import copyfile

import pytest
from pydantic import ValidationError

from risk.readiness_v11 import REQUIRED, ReadinessReport, build_current_readiness

ROOT = Path(__file__).resolve().parents[1]


def copy_current_package(target):
    report = build_current_readiness(ROOT)
    files = {ref["path"] for ref in report.source_references}
    current = json.loads((ROOT/"docs/examples/risk-policy-v11g/implementation-status.json").read_text(encoding="utf-8"))
    files.update(ref["path"] for ref in current["source_references"])
    for name in files:
        destination = target/name
        destination.parent.mkdir(parents=True, exist_ok=True)
        copyfile(ROOT/name, destination)


def test_current_gate_inventory_never_promotes_synthetic_work():
    report = build_current_readiness(ROOT)
    assert len(report.items) == len(REQUIRED) == 17
    assert report.configured_research_cap_usd == "1000"
    assert not report.paper_start_ready and not report.live_ready and not report.execution_available
    assert not report.v11_complete and not report.funding_confirmed
    assert report.forward_paper_sessions == 0


@pytest.mark.parametrize("change", ["missing", "duplicate", "claimed_pass"])
def test_inventory_cannot_omit_duplicate_or_promote_requirement(change):
    data = build_current_readiness(ROOT).model_dump()
    if change == "missing": data["items"] = data["items"][:-1]
    elif change == "duplicate": data["items"] = (*data["items"], data["items"][0])
    else: data["items"][0]["status"] = "QUALIFIED"
    with pytest.raises(ValidationError):
        ReadinessReport.model_validate(data)


@pytest.mark.parametrize("field", ["funding_confirmed", "v11_complete", "paper_start_ready", "live_ready", "execution_available"])
def test_no_boolean_override_can_release_gate(field):
    data = build_current_readiness(ROOT).model_dump() | {field: True}
    with pytest.raises(ValidationError):
        ReadinessReport.model_validate(data)


def test_digest_mismatch_blocks_report(tmp_path):
    copy_current_package(tmp_path)
    target = tmp_path/"risk/postgres_synthetic_v11.py"
    target.write_text(target.read_text(encoding="utf-8")+"\n# changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        build_current_readiness(tmp_path)


def test_execution_flag_change_requires_review(tmp_path):
    copy_current_package(tmp_path)
    target = tmp_path/"conf/investment-policy-v03.json"
    data = json.loads(target.read_text(encoding="utf-8")); data["production_trading"] = True
    target.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        build_current_readiness(tmp_path)
