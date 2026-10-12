"""Prepare public credential test configuration or serve a bounded owner diagnostic."""

import base64
import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from uuid import uuid4

import uvicorn
from fido2.utils import websafe_decode
from fido2.webauthn import AttestedCredentialData

from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_owner_auth_diagnostic import create_diagnostic_app
from security.webull_pinned_owner_app import require_standard_owner
from security.webull_review_signature import ReviewEnvelope
from security.windows_protected_config import ProtectedConfigReader


def material(owner, guardian, manifest, enrollment, enrollment_pin):
    path = Path(enrollment)
    if path.is_symlink() or path.is_junction() or not 1 <= path.stat().st_size <= 32768:
        raise ValueError("Ordinary bounded public enrollment required")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != enrollment_pin:
        raise ValueError("Public enrollment snapshot changed")
    credential = AttestedCredentialData(websafe_decode(json.loads(raw)["credential_data"]))
    now, identifier = datetime.now(UTC), str(uuid4())
    envelope = ReviewEnvelope(
        schema_version="webull-reset-prerequisite-review-v1",
        action="REVIEW_WEBULL_RESET_PRECONDITIONS_ONLY",
        review_id=uuid4(),
        account_binding_sha256="a" * 64,
        reset_review_sha256="b" * 64,
        credential_sha256=hashlib.sha256(bytes(credential)).hexdigest(),
        issued_at=now,
        expires_at=now + timedelta(seconds=300),
    )
    return {
        "configuration": {
            "schema_version": "webull-guardian-host-config-v1",
            "provisioning_id": identifier,
            "owner_sid": owner,
            "guardian_sid": guardian,
            "installed_manifest_sha256": manifest,
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
        },
        "purpose": "OWNER_AUTH_DIAGNOSTIC_ONLY",
        "real_public_credential_only": True,
    }


def main():
    mode = sys.argv[1]
    if mode == "material":
        print(base64.b64encode(json.dumps(material(*sys.argv[2:7])).encode()).decode())
        return
    if mode not in {"serve", "bind"}:
        raise ValueError("Diagnostic mode rejected")
    binding = mode == "bind"
    name = "owner-credential-binding" if binding else "owner-auth-diagnostic"
    path, pin, manifest, owner, guardian = sys.argv[2:7]
    require_standard_owner(owner)
    raw = ProtectedConfigReader().read(path, owner_sid=owner, guardian_sid=guardian)
    config = parse_pinned_host_config(
        raw, expected_sha256=pin, expected_manifest_sha256=manifest, now=datetime.now(UTC)
    )
    directory = Path(config.journal_path).parent
    success = threading.Event()

    def retain(result):
        with (directory / (name + ".json")).open("x", encoding="utf-8") as stream:
            json.dump(result, stream)
            stream.flush()
            os.fsync(stream.fileno())
        success.set()

    app = create_diagnostic_app(
        path,
        owner_sid=owner,
        guardian_sid=guardian,
        expected_sha256=pin,
        expected_manifest_sha256=manifest,
        retain=retain,
        profile="credential_binding" if binding else "diagnostic",
        expected_credential_sha256="fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b"
        if binding
        else None,
    )
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    thread = None
    server = uvicorn.Server(
        uvicorn.Config(
            app, log_level="critical", access_log=False, proxy_headers=False, lifespan="off"
        )
    )
    try:
        listener.bind(("127.0.0.1", 8769 if binding else 8768))
        listener.listen(8)
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        if not success.wait(40):
            raise TimeoutError(
                "Owner authentication diagnostic timed out; retained context cannot approve anything"
            )
        time.sleep(0.5)  # Let the success HTTP response complete before shutdown.
    finally:
        server.should_exit = True
        if thread:
            thread.join(3)
        listener.close()
    if thread and thread.is_alive():
        raise TimeoutError("Diagnostic listener did not close")
    with (directory / (name + "-terminal.json")).open("x", encoding="utf-8") as stream:
        json.dump(
            {
                "http_listener_closed": True,
                "authentication_verified": True,
                "reset_authorized": False,
                "execution_available": False,
                "trial_started": False,
            },
            stream,
        )


if __name__ == "__main__":
    main()
