import copy
import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fido2.webauthn import AttestedCredentialData

from scripts import webull_signed_host_fixture as fixture
from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_review_signature import verify_review_signature


def setup():
    material = fixture.synthetic_material("S-1-5-21-1-2-3-1001", "S-1-5-21-1-2-3-1002", "a" * 64)
    raw = json.dumps(material["configuration"]).encode()
    config = parse_pinned_host_config(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        expected_manifest_sha256="a" * 64,
        now=datetime.now(UTC),
    )
    return material, config


def test_generated_signature_is_valid_but_has_no_real_owner_or_reset_authority():
    material, config = setup()
    assert set(material) == {"configuration", "signed_receipt", "synthetic_key_only"}
    result = verify_review_signature(
        material["signed_receipt"],
        AttestedCredentialData(bytes.fromhex(config.public_credential_hex)),
        expected_envelope=config.envelope,
        now=datetime.now(UTC),
    )
    assert result["review_signature_verified"]
    assert not result["approval_consumed"] and not result["reset_authorized"]
    assert not result["execution_available"] and not result["trial_started"]


def discovery(config):
    return {
        "schema_version": "webull-review-host-ready-v1",
        "pipe_name": "AgenticRequest-" + "a" * 32,
        "action": "PREPARE_REVIEW_REFERENCE",
        "envelope_sha256": config.envelope.digest(),
        "probe_id": "b" * 32,
    }


def test_exact_discovery_binding():
    _, config = setup()
    assert (
        fixture.check_discovery(discovery(config), config, "b" * 32, "PREPARE_REVIEW_REFERENCE")
        == "AgenticRequest-" + "a" * 32
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("probe_id", "c" * 32),
        ("action", "CONFIRM_REVIEW_CONSUMPTION"),
        ("envelope_sha256", "0" * 64),
        ("pipe_name", r"\\remote\pipe\bad"),
        ("pipe_name", None),
        ("extra", False),
        ("schema_version", "wrong"),
    ],
)
def test_stale_or_changed_discovery_rejected(field, value):
    _, config = setup()
    changed = copy.deepcopy(discovery(config))
    changed[field] = value
    with pytest.raises(ValueError):
        fixture.check_discovery(changed, config, "b" * 32, "PREPARE_REVIEW_REFERENCE")


def test_owner_mode_rejects_foreign_identity_before_config_or_journal_access(monkeypatch):
    monkeypatch.setattr(
        fixture.sys,
        "argv",
        [
            "fixture",
            "owner",
            "expected-owner",
            "guardian",
            "a" * 64,
            "absent",
            "0" * 64,
            "b" * 32,
            "absent",
        ],
    )
    monkeypatch.setattr(
        fixture,
        "NativePipeIdentity",
        lambda: SimpleNamespace(read_process_identity=lambda: "foreign"),
    )
    with pytest.raises(PermissionError):
        fixture.main()
