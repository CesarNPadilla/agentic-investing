import copy
import hashlib
import json
from datetime import timedelta
from pathlib import PureWindowsPath
from types import SimpleNamespace
from uuid import uuid4

import pytest

from security.webull_guardian_host_config import (
    parse_pinned_host_config,
    validate_configured_reference,
)
from tests.test_webull_review_signature import signed_review


def material():
    _, credential, envelope, now, _ = signed_review()
    identifier = str(uuid4())
    value = {
        "schema_version": "webull-guardian-host-config-v1",
        "provisioning_id": identifier,
        "guardian_sid": "S-1-5-21-1-2-3-1001",
        "owner_sid": "S-1-5-21-1-2-3-1002",
        "installed_manifest_sha256": "a" * 64,
        "envelope": envelope.model_dump(mode="json"),
        "public_credential_hex": bytes(credential).hex(),
        "reference_directory": str(
            PureWindowsPath(r"C:\ProgramData\AgenticInvestingGuardian\References")
            / ("Review-" + identifier)
        ),
        "journal_path": str(
            PureWindowsPath(r"C:\ProgramData\AgenticInvestingPaper\OwnerControl")
            / ("Review-" + identifier)
            / "review.sqlite"
        ),
        "process_deadline_seconds": 15,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
    return value, credential, now


def parse(value, now):
    raw = json.dumps(value).encode()
    return parse_pinned_host_config(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        expected_manifest_sha256="a" * 64,
        now=now,
    )


def test_configuration_matches_without_qualifying_os_or_granting_authority():
    value, credential, now = material()
    config = parse(value, now)
    reference = SimpleNamespace(
        directory=PureWindowsPath(config.reference_directory),
        journal=SimpleNamespace(
            path=PureWindowsPath(config.journal_path), expected_envelope=config.envelope
        ),
        credential=credential,
    )
    result = validate_configured_reference(config, reference)
    assert result["configuration_material_matches"]
    assert not any(v for k, v in result.items() if k != "configuration_material_matches")
    reference.directory = PureWindowsPath(r"C:\untrusted")
    with pytest.raises(ValueError):
        validate_configured_reference(config, reference)


@pytest.mark.parametrize(
    "field,value",
    [
        ("reset_authorized", True),
        ("execution_available", True),
        ("trial_started", True),
        ("process_deadline_seconds", 45),
        ("process_deadline_seconds", 15.0),
        ("reset_authorized", 0),
        ("guardian_sid", "S-1-5-21-1-2-3-1002"),
        ("guardian_sid", "S-1-5-21-1-2-3-9999999999"),
        ("extra", False),
        ("reference_directory", r"C:\untrusted"),
        ("journal_path", r"\\server\share\review.sqlite"),
        ("public_credential_hex", "00"),
        ("installed_manifest_sha256", "b" * 64),
    ],
)
def test_changed_material_is_rejected(field, value):
    config, _, now = material()
    config[field] = value
    with pytest.raises((ValueError, IndexError)):
        parse(config, now)


@pytest.mark.parametrize("offset", [-1, 300])
def test_future_or_expired_config_rejected(offset):
    value, _, now = material()
    with pytest.raises(ValueError):
        parse(value, now + timedelta(seconds=offset))


@pytest.mark.parametrize(
    "raw",
    [b'{"x":1,"x":2}', b'{"nested":{"x":1,"x":2}}', b'{"x":NaN}', b"\xff", b"x" * 32769],
    ids=["duplicate", "nested-duplicate", "nonfinite", "invalid-utf8", "oversized"],
)
def test_ambiguous_or_unbounded_input_rejected(raw):
    with pytest.raises(ValueError):
        parse_pinned_host_config(
            raw,
            expected_sha256=hashlib.sha256(raw).hexdigest(),
            expected_manifest_sha256="a" * 64,
            now=material()[2],
        )


def test_external_digest_mismatch_and_wrong_reference_context():
    value, credential, now = material()
    raw = json.dumps(value).encode()
    with pytest.raises(ValueError):
        parse_pinned_host_config(
            raw, expected_sha256="0" * 64, expected_manifest_sha256="a" * 64, now=now
        )
    config = parse(value, now)
    _, _, wrong_envelope, _, _ = signed_review()
    reference = SimpleNamespace(
        directory=PureWindowsPath(config.reference_directory),
        journal=SimpleNamespace(
            path=PureWindowsPath(config.journal_path), expected_envelope=wrong_envelope
        ),
        credential=credential,
    )
    with pytest.raises(ValueError):
        validate_configured_reference(config, reference)
    changed = copy.deepcopy(value)
    changed["envelope"]["credential_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        parse(changed, now)
