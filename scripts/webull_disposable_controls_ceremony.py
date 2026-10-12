"""Explicit disposable controls ceremony, real passkey; no broker/reset interface."""

import base64
import hashlib
import json
import socket
import sys
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from uuid import uuid4

import uvicorn

from scripts.webull_signed_host_fixture import check_discovery, exclusive
from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_guardian_reference import GuardianReference
from security.webull_guardian_review_host import GuardianReviewHost
from security.webull_owner_credential_registry import (
    load_registered_guardian_config,
    parse_registry,
)
from security.webull_pinned_owner_app import create_registered_owner_app, require_standard_owner
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import ReviewEnvelope
from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_protected_config import ProtectedConfigReader
from security.windows_review_process_supervisor import supervise_review_process

ROOT = Path(r"C:\ProgramData\AgenticInvestingGuardian")
REGISTRY_PIN = "9fe4cf37ee9513eb9668dc2de0997b117abe83704ef0cc79a1c27e38b046b778"
KEY_PIN = "fc0761142d56f020eac42868d377fb12849458e90a6db5c23edc9bc6ca58e22b"
REGISTRY = ROOT / "Code" / ("AcceptedOwnerCredential-" + REGISTRY_PIN + ".json")
ACCOUNT = {"purpose": "DISPOSABLE_CONTROLS_TEST_ONLY", "account": "SYNTHETIC_NO_BROKER_ACCOUNT"}
PLAN = {
    "purpose": "DISPOSABLE_CONTROLS_TEST_ONLY",
    "operation": "PASSKEY_GUARDIAN_RETENTION_TEST",
    "reset_authorized": False,
    "execution_available": False,
    "trial_started": False,
}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def controls_only(config):
    if (
        config.envelope.action != "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY"
        or config.envelope.account_binding_sha256 != digest(ACCOUNT)
        or config.envelope.reset_review_sha256 != digest(PLAN)
    ):
        raise ValueError("Exact disposable controls context required")


def material(owner, guardian, manifest):
    raw = ProtectedConfigReader().read_registry(REGISTRY, owner_sid=owner, guardian_sid=guardian)
    key = parse_registry(
        raw,
        expected_sha256=REGISTRY_PIN,
        credential_sha256=KEY_PIN,
        owner_sid=owner,
        guardian_sid=guardian,
    )
    current, identifier = datetime.now(UTC), uuid4()
    envelope = ReviewEnvelope(
        schema_version="webull-disposable-controls-review-v1",
        action="REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY",
        review_id=uuid4(),
        account_binding_sha256=digest(ACCOUNT),
        reset_review_sha256=digest(PLAN),
        credential_sha256=KEY_PIN,
        issued_at=current,
        expires_at=current + timedelta(seconds=300),
    )
    return {
        "schema_version": "webull-guardian-host-config-v1",
        "provisioning_id": str(identifier),
        "owner_sid": owner,
        "guardian_sid": guardian,
        "installed_manifest_sha256": manifest,
        "envelope": envelope.model_dump(mode="json"),
        "public_credential_hex": bytes(key).hex(),
        "reference_directory": str(
            PureWindowsPath(str(ROOT)) / "References" / ("Review-" + str(identifier))
        ),
        "journal_path": str(
            PureWindowsPath(r"C:\ProgramData\AgenticInvestingPaper\OwnerControl")
            / ("Review-" + str(identifier))
            / "review.sqlite"
        ),
        "process_deadline_seconds": 15,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }


def main():
    mode, owner, guardian, manifest = sys.argv[1:5]
    if mode == "material":
        value = {
            "configuration": material(owner, guardian, manifest),
            "purpose": "WEBULL_DISPOSABLE_CONTROLS_TEST_ONLY",
        }
        print(base64.b64encode(json.dumps(value).encode()).decode())
        return
    path, pin, identifier = sys.argv[5:8]
    now = lambda: datetime.now(UTC)

    def guardian_config():
        config = load_registered_guardian_config(
            path,
            registry_path=REGISTRY,
            expected_registry_sha256=REGISTRY_PIN,
            expected_credential_sha256=KEY_PIN,
            owner_sid=owner,
            guardian_sid=guardian,
            expected_sha256=pin,
            expected_manifest_sha256=manifest,
            now=now(),
        )
        controls_only(config)
        return config

    if mode in {"supervisor", "host"}:
        config = guardian_config()
    elif mode == "owner":
        require_standard_owner(owner)
        raw = ProtectedConfigReader().read(path, owner_sid=owner, guardian_sid=guardian)
        config = parse_pinned_host_config(
            raw, expected_sha256=pin, expected_manifest_sha256=manifest, now=now()
        )
        controls_only(config)
    else:
        raise ValueError("Fixed ceremony mode required")
    if mode == "supervisor":
        exclusive(
            ROOT / "Logs" / f"controls-ready-{identifier}-waiting.json",
            {"probe_id": identifier, "state": "WAITING_FOR_OWNER_VERIFIED_ASSERTION"},
        )
        ready = Path(config.journal_path).parent / "controls-owner-ready.json"
        deadline = time.monotonic() + 45
        while not ready.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Owner assertion readiness timeout")
            time.sleep(0.01)
        if ready.is_symlink() or ready.is_junction() or not 1 <= ready.stat().st_size <= 4096:
            raise ValueError("Ordinary bounded readiness required")
        if json.loads(ready.read_bytes()) != {
            "probe_id": identifier,
            "envelope_sha256": config.envelope.digest(),
        }:
            raise ValueError("Readiness context mismatch")
        config = guardian_config()
        result = supervise_review_process(
            Path(sys.executable),
            ["-I", "-B", str(Path(__file__).resolve()), "host", *sys.argv[2:]],
            ROOT / "Logs",
            seconds=config.process_deadline_seconds,
        )
        exclusive(ROOT / "Receipts" / f"controls-supervisor-{identifier}.json", result)
        if result["termination"] != "CHILD_EXITED" or result["exit_code"] != 0:
            raise ValueError("Controls host failed; retain all state")
        return
    if mode == "host":
        key = parse_registry(
            ProtectedConfigReader().read_registry(REGISTRY, owner_sid=owner, guardian_sid=guardian),
            expected_sha256=REGISTRY_PIN,
            credential_sha256=KEY_PIN,
            owner_sid=owner,
            guardian_sid=guardian,
        )
        journal = ReviewJournal(config.journal_path, expected_envelope=config.envelope)
        reference = GuardianReference(config.reference_directory, journal, key)
        host = GuardianReviewHost(
            reference,
            guardian_sid=guardian,
            owner_sid=owner,
            provisioned_envelope_sha256=config.envelope.digest(),
        )

        def publish(value):
            label = "prepare" if value["action"] == "PREPARE_REVIEW_REFERENCE" else "confirm"
            ready = ROOT / "Logs" / f"controls-ready-{identifier}-{label}.json"
            partial = ready.with_suffix(".partial")
            exclusive(partial, value | {"probe_id": identifier})
            partial.rename(ready)

        result = host.run(publish)
        exclusive(
            ROOT / "Receipts" / f"controls-host-{identifier}.json",
            result | {"probe_id": identifier, "disposable_controls_test_only": True},
        )
        return
    finished = threading.Event()
    phases = iter(("PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"))

    def exchange(raw):
        phase = next(phases)
        if phase == "PREPARE_REVIEW_REFERENCE":
            # consume_guarded_review verifies the assertion before invoking us.
            ready = Path(config.journal_path).parent / "controls-owner-ready.json"
            partial = ready.with_suffix(".partial")
            exclusive(
                partial, {"probe_id": identifier, "envelope_sha256": config.envelope.digest()}
            )
            partial.rename(ready)
        label = "prepare" if phase == "PREPARE_REVIEW_REFERENCE" else "confirm"
        ready = ROOT / "Logs" / f"controls-ready-{identifier}-{label}.json"
        deadline = time.monotonic() + 4
        while not ready.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("Controls host discovery unavailable")
            time.sleep(0.01)
        pipe = check_discovery(json.loads(ready.read_bytes()), config, identifier, phase)
        return GuardianExchangeClient(name=pipe, guardian_sid=guardian).exchange(raw)

    app = create_registered_owner_app(
        path,
        registry_path=REGISTRY,
        expected_registry_sha256=REGISTRY_PIN,
        expected_credential_sha256=KEY_PIN,
        owner_sid=owner,
        guardian_sid=guardian,
        expected_sha256=pin,
        expected_manifest_sha256=manifest,
        guardian_exchange=exchange,
    )

    @app.middleware("http")
    async def successful_review(request, call_next):
        response = await call_next(request)
        if request.url.path == "/complete" and response.status_code == 200:
            finished.set()
        return response

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 8767))
    sock.listen(8)
    server = uvicorn.Server(
        uvicorn.Config(
            app, log_level="critical", access_log=False, proxy_headers=False, lifespan="off"
        )
    )
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    try:
        thread.start()
        success = finished.wait(40)
        if success:
            time.sleep(0.5)
    finally:
        server.should_exit = True
        thread.join(8)
        sock.close()
    if thread.is_alive() or not success:
        raise TimeoutError("Disposable ceremony incomplete; retained evidence must be reviewed")
    exclusive(
        Path(config.journal_path).parent / "controls-owner-result.json",
        {
            "schema_version": "disposable-controls-owner-v1",
            "probe_id": identifier,
            "standard_owner_process_verified": True,
            "real_owner_passkey_used": True,
            "disposable_controls_test_only": True,
            "http_listener_closed": True,
            "guardian_reference_confirmed": True,
            "reset_authorized": False,
            "execution_available": False,
            "trial_started": False,
        },
    )


if __name__ == "__main__":
    main()
