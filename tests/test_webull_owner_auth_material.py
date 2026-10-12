import hashlib
import json

import pytest
from fido2.utils import websafe_encode

from scripts.webull_owner_auth_diagnostic import material
from tests.test_webull_review_signature import signed_review


def test_material_copies_public_key_without_adopting_declared_identity(tmp_path):
    _, credential, _, _, _ = signed_review()
    path = tmp_path / "public.json"
    raw = json.dumps(
        {
            "credential_data": websafe_encode(bytes(credential)),
            "declared_owner": "Untrusted declaration",
            "enrolled_at_utc": "Untrusted timestamp",
        }
    ).encode()
    path.write_bytes(raw)
    result = material(
        "S-1-5-21-1-2-3-1001",
        "S-1-5-21-1-2-3-1002",
        "a" * 64,
        path,
        hashlib.sha256(raw).hexdigest(),
    )
    assert result["purpose"] == "OWNER_AUTH_DIAGNOSTIC_ONLY"
    assert result["configuration"]["public_credential_hex"] == bytes(credential).hex()
    assert "Untrusted" not in json.dumps(result)
    assert result["configuration"]["reset_authorized"] is False
    assert "signed_receipt" not in result


def test_changed_snapshot_rejected_before_material_output(tmp_path):
    path = tmp_path / "public.json"
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="snapshot changed"):
        material("owner", "guardian", "a" * 64, path, "b" * 64)
