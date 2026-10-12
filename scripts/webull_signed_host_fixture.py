"""Disposable signed review fixture: synthetic key, real process/transport boundaries.

Not an owner-app or service entry point. No broker, reset or trading interface.
"""

import base64
import ctypes
import hashlib
import http.cookiejar
import json
import os
import re
import socket
import sys
import threading
import time
import urllib.request
from ctypes import wintypes
from datetime import UTC, datetime, timedelta
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from uuid import uuid4

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2.cose import ES256
from fido2.utils import websafe_encode
from fido2.webauthn import AttestedCredentialData, AuthenticatorData

from security.webull_guarded_review import consume_guarded_review
from security.webull_guardian_host_config import (
    parse_pinned_host_config,
    validate_configured_reference,
)
from security.webull_guardian_reference import GuardianReference
from security.webull_guardian_review_host import GuardianReviewHost
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import ORIGIN, ReviewEnvelope, review_challenge
from security.windows_guardian_exchange_client import GuardianExchangeClient
from security.windows_pipe_identity import NativePipeIdentity
from security.windows_protected_config import ProtectedConfigReader, load_guardian_config
from security.windows_review_process_supervisor import supervise_review_process

ROOT = Path(r"C:\ProgramData\AgenticInvestingGuardian")
FLAGS = {"reset_authorized": False, "execution_available": False, "trial_started": False}


def synthetic_material(owner, guardian, manifest):
    key = ec.generate_private_key(ec.SECP256R1())
    credential = AttestedCredentialData.create(
        bytes(16), b"synthetic-signed-host-only", ES256.from_cryptography_key(key.public_key())
    )
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
    nonce = os.urandom(32)
    challenge = websafe_encode(review_challenge(envelope, nonce))
    client_data = json.dumps(
        {"type": "webauthn.get", "challenge": challenge, "origin": ORIGIN}
    ).encode()
    authenticator = AuthenticatorData.create(hashlib.sha256(b"localhost").digest(), 5, 1)
    signature = key.sign(
        bytes(authenticator) + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256())
    )
    receipt = {
        "purpose": "WEBULL_RESET_PREREQUISITE_REVIEW_ONLY",
        "envelope": envelope.model_dump(mode="json"),
        "envelope_sha256": envelope.digest(),
        "challenge_nonce_hex": nonce.hex(),
        "challenge_state": {"challenge": challenge, "user_verification": "required"},
        "assertion": {
            "id": websafe_encode(credential.credential_id),
            "rawId": websafe_encode(credential.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": websafe_encode(client_data),
                "authenticatorData": websafe_encode(bytes(authenticator)),
                "signature": websafe_encode(signature),
                "userHandle": None,
            },
        },
        "reset_authorized": False,
        "execution_available": False,
    }
    config = {
        "schema_version": "webull-guardian-host-config-v1",
        "provisioning_id": identifier,
        "guardian_sid": guardian,
        "owner_sid": owner,
        "installed_manifest_sha256": manifest,
        "envelope": envelope.model_dump(mode="json"),
        "public_credential_hex": bytes(credential).hex(),
        "reference_directory": str(
            PureWindowsPath(str(ROOT)) / "References" / ("Review-" + identifier)
        ),
        "journal_path": str(
            PureWindowsPath(r"C:\ProgramData\AgenticInvestingPaper\OwnerControl")
            / ("Review-" + identifier)
            / "review.sqlite"
        ),
        "process_deadline_seconds": 15,
        **FLAGS,
    }
    return {"configuration": config, "signed_receipt": receipt, "synthetic_key_only": True}


def exclusive(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())


def check_discovery(value, config, identifier, phase):
    if (
        type(value) is not dict
        or set(value) != {"schema_version", "pipe_name", "action", "envelope_sha256", "probe_id"}
        or value["schema_version"] != "webull-review-host-ready-v1"
        or value["probe_id"] != identifier
        or value["action"] != phase
        or value["envelope_sha256"] != config.envelope.digest()
        or not isinstance(value["pipe_name"], str)
        or not re.fullmatch(r"AgenticRequest-[0-9a-f]{32}", value["pipe_name"])
    ):
        raise ValueError("Stale or mismatched synthetic host discovery")
    return value["pipe_name"]


def synthetic_http_review(app, signed, envelope, *, before_complete=lambda: None):
    """Fixture-only controlled challenge for a pre-generated assertion.

    This is never a real passkey ceremony or an application deployment entry point.
    The production application retains its normal random challenge generator.
    """
    import uvicorn

    from security import webull_owner_review_app as ui

    nonce = bytes.fromhex(signed["challenge_nonce_hex"])
    if len(nonce) != 32:
        raise ValueError("Synthetic challenge nonce required")
    original = ui.secrets
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    thread = None
    try:
        # Bind our own socket before sending any HTTP; never use an existing listener.
        listener.bind(("127.0.0.1", 8767))
        listener.listen(8)
        ui.secrets = SimpleNamespace(
            token_bytes=lambda length: nonce if length == 32 else original.token_bytes(length),
            token_urlsafe=original.token_urlsafe,
        )
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                host="127.0.0.1",
                port=8767,
                access_log=False,
                proxy_headers=False,
                log_level="critical",
                lifespan="off",
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = time.monotonic() + 3
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise TimeoutError("Synthetic owner HTTP startup failed")
            time.sleep(0.01)
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
        )

        def request(path, value=None, headers=None):
            data = None if value is None else json.dumps(value).encode()
            req = urllib.request.Request(
                ORIGIN + path,
                data=data,
                headers={"Origin": ORIGIN, "Content-Type": "application/json", **(headers or {})},
            )
            with opener.open(req, timeout=5) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError("Bounded owner HTTP response required")
                return json.loads(raw)

        if request("/review")["digest"] != envelope.digest():
            raise ValueError("Displayed synthetic context mismatch")
        options = request("/begin", {}, {"X-Owner-Review-Sha256": envelope.digest()})
        if options["publicKey"]["challenge"] != signed["challenge_state"]["challenge"]:
            raise ValueError("Frozen synthetic challenge mismatch")
        before_complete()
        result = request("/complete", signed["assertion"])
        if result.get("guardian_reference_confirmed") is not True:
            raise ValueError("Synthetic HTTP guardian confirmation missing")
        return result | {"synthetic_http_roundtrip_verified": True}
    finally:
        if server:
            server.should_exit = True
        if thread:
            thread.join(3)
        listener.close()
        ui.secrets = original
        if thread and thread.is_alive():
            raise TimeoutError("Synthetic owner HTTP did not close")


def main():
    mode, owner, guardian, manifest = sys.argv[1:5]
    if mode == "material":
        print(
            base64.b64encode(
                json.dumps(synthetic_material(owner, guardian, manifest)).encode()
            ).decode()
        )
        return
    path, pin, identifier, receipt_path = sys.argv[5:9]
    if not re.fullmatch(r"[0-9a-f]{32}", identifier):
        raise ValueError("Fixture identifier required")
    now = lambda: datetime.now(UTC)
    if mode in {"host", "supervisor", "supervisor_http"}:
        config = load_guardian_config(
            path,
            owner_sid=owner,
            guardian_sid=guardian,
            expected_sha256=pin,
            expected_manifest_sha256=manifest,
            now=now(),
        )
    elif mode in {"owner", "owner_http"}:
        api = NativePipeIdentity()
        if api.read_process_identity() != owner:
            raise PermissionError("Configured owner process required")
        token, elevation, used = wintypes.HANDLE(), wintypes.DWORD(), wintypes.DWORD()
        if not api.security.OpenProcessToken(
            api.kernel.GetCurrentProcess(), 8, ctypes.byref(token)
        ):
            raise OSError("Owner token unavailable")
        try:
            if (
                not api.security.GetTokenInformation(
                    token, 20, ctypes.byref(elevation), 4, ctypes.byref(used)
                )
                or elevation.value
            ):
                raise PermissionError("Standard owner process required")
        finally:
            api.kernel.CloseHandle(token)
        raw = ProtectedConfigReader().read(path, owner_sid=owner, guardian_sid=guardian)
        config = parse_pinned_host_config(
            raw, expected_sha256=pin, expected_manifest_sha256=manifest, now=now()
        )
        if config.owner_sid != owner or config.guardian_sid != guardian:
            raise ValueError("Configured roles mismatch")
    else:
        raise ValueError("Fixture mode rejected")
    if mode in {"supervisor", "supervisor_http"}:
        if mode == "supervisor_http":
            waiting = ROOT / "Logs" / f"signed-host-ready-{identifier}-waiting.json"
            exclusive(waiting, {"probe_id": identifier, "state": "WAITING_FOR_SYNTHETIC_HTTP"})
            ready = Path(config.journal_path).parent / "http-owner-ready.json"
            deadline = time.monotonic() + 10
            while not ready.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Synthetic owner HTTP readiness unavailable")
                time.sleep(0.01)
            if ready.is_symlink() or ready.is_junction() or not 1 <= ready.stat().st_size <= 4096:
                raise ValueError("Ordinary bounded HTTP readiness required")
            value = json.loads(ready.read_text(encoding="utf-8"))
            if value != {
                "schema_version": "synthetic-owner-http-ready-v1",
                "probe_id": identifier,
                "envelope_sha256": config.envelope.digest(),
            }:
                raise ValueError("Synthetic HTTP readiness context mismatch")
            # Freshness is checked again after the bounded, pre-host startup wait.
            config = load_guardian_config(
                path,
                owner_sid=owner,
                guardian_sid=guardian,
                expected_sha256=pin,
                expected_manifest_sha256=manifest,
                now=now(),
            )
        result = supervise_review_process(
            Path(sys.executable),
            ["-I", "-B", str(Path(__file__).resolve()), "host", *sys.argv[2:]],
            ROOT / "Logs",
            seconds=config.process_deadline_seconds,
        )
        if result["termination"] != "CHILD_EXITED" or result["exit_code"] != 0:
            raise ValueError("Synthetic signed host failed; retained evidence requires review")
        exclusive(ROOT / "Receipts" / f"signed-host-supervisor-{identifier}.json", result)
        return
    journal = ReviewJournal(config.journal_path, expected_envelope=config.envelope)
    credential = AttestedCredentialData(bytes.fromhex(config.public_credential_hex))
    if mode == "host":
        reference = GuardianReference(config.reference_directory, journal, credential)
        validate_configured_reference(config, reference)
        host = GuardianReviewHost(
            reference,
            guardian_sid=guardian,
            owner_sid=owner,
            provisioned_envelope_sha256=config.envelope.digest(),
        )

        def publish(message):
            phase = "prepare" if message["action"] == "PREPARE_REVIEW_REFERENCE" else "confirm"
            ready = ROOT / "Logs" / f"signed-host-ready-{identifier}-{phase}.json"
            partial = ready.with_suffix(".partial")
            exclusive(partial, message | {"probe_id": identifier})
            # On Windows rename rejects an existing target; closed bytes become visible atomically.
            partial.rename(ready)

        result = host.run(publish)
        exclusive(
            ROOT / "Receipts" / f"signed-host-result-{identifier}.json",
            result | {"probe_id": identifier, "synthetic_key_only": True},
        )
    else:
        signed = json.loads(Path(receipt_path).read_text(encoding="utf-8"))
        phases = iter(("PREPARE_REVIEW_REFERENCE", "CONFIRM_REVIEW_CONSUMPTION"))

        def exchange(raw):
            phase = next(phases)
            label = "prepare" if phase == "PREPARE_REVIEW_REFERENCE" else "confirm"
            ready = ROOT / "Logs" / f"signed-host-ready-{identifier}-{label}.json"
            deadline = time.monotonic() + 4
            while not ready.exists():
                if time.monotonic() >= deadline:
                    raise TimeoutError("Synthetic host discovery unavailable")
                time.sleep(0.01)
            value = json.loads(ready.read_text(encoding="utf-8"))
            pipe = check_discovery(value, config, identifier, phase)
            return GuardianExchangeClient(name=pipe, guardian_sid=guardian).exchange(raw)

        if mode == "owner_http":
            from security.webull_pinned_owner_app import create_pinned_owner_app

            app = create_pinned_owner_app(
                path,
                owner_sid=owner,
                guardian_sid=guardian,
                expected_sha256=pin,
                expected_manifest_sha256=manifest,
                guardian_exchange=exchange,
                now=now,
            )

            def ready_for_guardian():
                ready = Path(config.journal_path).parent / "http-owner-ready.json"
                partial = ready.with_suffix(".partial")
                exclusive(
                    partial,
                    {
                        "schema_version": "synthetic-owner-http-ready-v1",
                        "probe_id": identifier,
                        "envelope_sha256": config.envelope.digest(),
                    },
                )
                partial.rename(ready)

            result = synthetic_http_review(
                app, signed, config.envelope, before_complete=ready_for_guardian
            )
            result["http_listener_closed"] = True
            result["real_owner_passkey_used"] = False
        else:
            result = consume_guarded_review(signed, credential, journal, exchange=exchange, now=now)
        exclusive(
            Path(config.journal_path).parent / "signed-owner-result.json",
            result | {"standard_owner_process_verified": True, "synthetic_key_only": True},
        )


if __name__ == "__main__":
    main()
