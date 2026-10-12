import hashlib
import json

import pytest

from security.webull_owner_auth_diagnostic import BINDING_ORIGIN
from security.webull_owner_credential_registry import parse_registry, verify_binding
from tests.test_webull_owner_auth_diagnostic import assertion, prepare


def proof(tmp_path, monkeypatch):
    client, raw, _, credential, key, retained, *_ = prepare(
        tmp_path, monkeypatch, profile="credential_binding"
    )
    options = client.post("/begin").json()
    assert (
        client.post(
            "/complete", json=assertion(options, credential, key, origin=BINDING_ORIGIN)
        ).status_code
        == 200
    )
    config = json.loads(raw[0])
    args = {
        "configuration_sha256": hashlib.sha256(raw[0]).hexdigest(),
        "manifest_sha256": config["installed_manifest_sha256"],
        "credential_sha256": hashlib.sha256(bytes(credential)).hexdigest(),
        "owner_sid": config["owner_sid"],
        "guardian_sid": config["guardian_sid"],
    }
    return retained[0], raw[0], args


def test_signed_binding_proof(tmp_path, monkeypatch):
    result, config, args = proof(tmp_path, monkeypatch)
    assert verify_binding(result, config, **args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "OWNER_AUTH_DIAGNOSTIC_ONLY"),
        ("credential_binding_authorized", 1),
        ("reset_authorized", 0),
        ("credential_sha256", "0" * 64),
        ("nonce_hex", "00" * 32),
    ],
)
def test_changed_binding_rejected(tmp_path, monkeypatch, field, value):
    result, config, args = proof(tmp_path, monkeypatch)
    result[field] = value
    with pytest.raises(ValueError):
        verify_binding(result, config, **args)


def test_registry_requires_external_pin_and_exact_scope(tmp_path, monkeypatch):
    result, config, args = proof(tmp_path, monkeypatch)
    value = {
        "schema_version": "accepted-owner-credential-v1",
        "configuration_hex": config.hex(),
        "configuration_sha256": args.pop("configuration_sha256"),
        "manifest_sha256": args.pop("manifest_sha256"),
        "binding_result": result,
        "wrapper_sha256": "a" * 64,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
    raw = json.dumps(value).encode()
    pin = hashlib.sha256(raw).hexdigest()
    assert parse_registry(raw, expected_sha256=pin, **args)
    with pytest.raises(ValueError, match="digest"):
        parse_registry(raw + b" ", expected_sha256=pin, **args)
    value["trial_started"] = True
    raw = json.dumps(value).encode()
    with pytest.raises(ValueError, match="activation"):
        parse_registry(raw, expected_sha256=hashlib.sha256(raw).hexdigest(), **args)


def test_registered_app_rechecks_record_before_challenge(tmp_path, monkeypatch):
    from datetime import datetime

    from fastapi.testclient import TestClient

    from security import webull_pinned_owner_app as pinned

    result, config, args = proof(tmp_path, monkeypatch)
    value = {
        "schema_version": "accepted-owner-credential-v1",
        "configuration_hex": config.hex(),
        "configuration_sha256": args["configuration_sha256"],
        "manifest_sha256": args["manifest_sha256"],
        "binding_result": result,
        "wrapper_sha256": "a" * 64,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
    registry = [json.dumps(value).encode()]
    monkeypatch.setattr(
        pinned.ProtectedConfigReader, "read_registry", lambda *_a, **_k: registry[0], raising=False
    )
    actions = []
    app = pinned.create_registered_owner_app(
        "protected",
        registry_path="registry",
        expected_registry_sha256=hashlib.sha256(registry[0]).hexdigest(),
        expected_credential_sha256=args["credential_sha256"],
        owner_sid=args["owner_sid"],
        guardian_sid=args["guardian_sid"],
        expected_sha256=args["configuration_sha256"],
        expected_manifest_sha256=args["manifest_sha256"],
        guardian_exchange=actions.append,
        now=lambda: datetime.fromisoformat(result["observed_at_utc"]),
    )
    client = TestClient(app, base_url="http://localhost:8767")
    assert client.get("/review").status_code == 200
    registry[0] += b" "
    assert client.get("/review").status_code == 409
    assert actions == []


@pytest.mark.parametrize("changed", [False, True])
def test_guardian_config_must_use_accepted_key(tmp_path, monkeypatch, changed):
    from types import SimpleNamespace

    from security import windows_protected_config as native
    from security.webull_owner_credential_registry import load_registered_guardian_config

    result, config, args = proof(tmp_path, monkeypatch)
    record = {
        "schema_version": "accepted-owner-credential-v1",
        "configuration_hex": config.hex(),
        "configuration_sha256": args["configuration_sha256"],
        "manifest_sha256": args["manifest_sha256"],
        "binding_result": result,
        "wrapper_sha256": "a" * 64,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
    raw = json.dumps(record).encode()
    context = SimpleNamespace(
        public_credential_hex=("00" if changed else json.loads(config)["public_credential_hex"])
    )
    monkeypatch.setattr(native, "load_guardian_config", lambda *_a, **_k: context)
    monkeypatch.setattr(native.ProtectedConfigReader, "read_registry", lambda *_a, **_k: raw)
    kwargs = {
        "registry_path": "registry",
        "expected_registry_sha256": hashlib.sha256(raw).hexdigest(),
        "expected_credential_sha256": args["credential_sha256"],
        "owner_sid": args["owner_sid"],
        "guardian_sid": args["guardian_sid"],
    }
    if changed:
        with pytest.raises(ValueError, match="differs"):
            load_registered_guardian_config("protected", **kwargs)
    else:
        assert load_registered_guardian_config("protected", **kwargs) is context
