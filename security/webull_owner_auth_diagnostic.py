"""Real owner authentication diagnostic only; no review journal or guardian calls."""

import hashlib
import json
import secrets
import threading
import time
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fido2.server import Fido2Server
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity

from security.webull_guardian_host_config import parse_pinned_host_config
from security.webull_pinned_owner_app import require_standard_owner
from security.windows_protected_config import ProtectedConfigReader

ORIGIN = "http://localhost:8768"
DOMAIN = b"WEBULL_OWNER_AUTH_DIAGNOSTIC_ONLY_V1\0"
BINDING_ORIGIN = "http://localhost:8769"
BINDING_DOMAIN = b"WEBULL_OWNER_REVIEW_CREDENTIAL_BINDING_ONLY_V1\0"
PAGE = """<!doctype html><html><head><meta charset="utf-8">
<title>Owner passkey diagnostic</title><script src="/owner.js" defer></script></head>
<body><h1>Test your enrolled passkey</h1>
<p>Authentication test only. This does not approve a review or reset, enable orders,
or start a trial. This page has no guardian or broker interface.</p>
<p id="fingerprint"></p><button id="test" disabled>Test with Windows Hello / passkey</button>
<p id="result" role="status"></p></body></html>"""
JS = """"use strict";
const decode=v=>Uint8Array.from(atob(v.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0));
const encode=v=>btoa(String.fromCharCode(...new Uint8Array(v))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
async function body(r){if(!r.ok)throw Error('Diagnostic expired or rejected. No approval granted.');return r.json();}
const button=document.getElementById('test'),result=document.getElementById('result');
fetch('/status').then(body).then(v=>{document.getElementById('fingerprint').textContent='Public credential SHA-256: '+v.credential_sha256;button.disabled=false;}).catch(e=>result.textContent=e.message);
button.onclick=async()=>{button.disabled=true;try{
const options=await body(await fetch('/begin',{method:'POST'}));
options.publicKey.challenge=decode(options.publicKey.challenge);
options.publicKey.allowCredentials.forEach(v=>v.id=decode(v.id));
const c=await navigator.credentials.get(options);
await body(await fetch('/complete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:c.id,rawId:encode(c.rawId),type:c.type,response:{clientDataJSON:encode(c.response.clientDataJSON),authenticatorData:encode(c.response.authenticatorData),signature:encode(c.response.signature),userHandle:c.response.userHandle?encode(c.response.userHandle):null}})}));
result.textContent='Passkey authentication verified. No review, reset or trading approved.';
}catch(e){result.textContent=e.message;}};
"""


def create_diagnostic_app(
    configuration_path,
    *,
    owner_sid,
    guardian_sid,
    expected_sha256,
    expected_manifest_sha256,
    retain,
    now=None,
    clock=time.monotonic,
    profile="diagnostic",
    expected_credential_sha256=None,
):
    if profile not in {"diagnostic", "credential_binding"}:
        raise ValueError("Fixed owner ceremony profile required")
    binding = profile == "credential_binding"
    if binding and (
        type(expected_credential_sha256) is not str
        or len(expected_credential_sha256) != 64
        or any(c not in "0123456789abcdef" for c in expected_credential_sha256)
    ):
        raise ValueError("Externally pinned binding candidate required")
    origin = BINDING_ORIGIN if binding else ORIGIN
    domain = BINDING_DOMAIN if binding else DOMAIN
    purpose = "OWNER_REVIEW_CREDENTIAL_BINDING_ONLY" if binding else "OWNER_AUTH_DIAGNOSTIC_ONLY"
    now = now or (lambda: datetime.now(UTC))
    server = Fido2Server(
        PublicKeyCredentialRpEntity(id="localhost", name="Owner diagnostic"),
        verify_origin=lambda value: value == origin,
    )
    pending, lock = {}, threading.Lock()
    completed = [False]

    def context():
        require_standard_owner(owner_sid)
        raw = ProtectedConfigReader().read(
            configuration_path, owner_sid=owner_sid, guardian_sid=guardian_sid
        )
        config = parse_pinned_host_config(
            raw,
            expected_sha256=expected_sha256,
            expected_manifest_sha256=expected_manifest_sha256,
            now=now(),
        )
        if config.owner_sid != owner_sid or config.guardian_sid != guardian_sid:
            raise ValueError("Diagnostic role binding mismatch")
        credential = AttestedCredentialData(bytes.fromhex(config.public_credential_hex))
        if binding and hashlib.sha256(bytes(credential)).hexdigest() != expected_credential_sha256:
            raise ValueError("Binding candidate changed")
        return credential

    context()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.headers.get("host") != origin.removeprefix("http://") or (
            request.method != "GET" and request.headers.get("origin") != origin
        ):
            return JSONResponse({"error": "Local origin rejected"}, status_code=403)
        response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            }
        )
        return response

    @app.get("/")
    def page():
        if binding:
            return HTMLResponse(
                PAGE.replace("Owner passkey diagnostic", "Owner credential binding")
                .replace("Test your enrolled passkey", "Bind your passkey for Webull owner reviews")
                .replace(
                    "Authentication test only. This does not approve a review or reset, enable orders,\nor start a trial. This page has no guardian or broker interface.",
                    "Authorize this displayed public credential for future Webull owner review signing. "
                    "This does not sign a review, approve a reset, enable orders or start a trial. "
                    "This page has no guardian or broker interface.",
                )
                .replace(
                    "Test with Windows Hello / passkey",
                    "Bind this credential with Windows Hello / passkey",
                )
            )
        return HTMLResponse(PAGE)

    @app.get("/owner.js")
    def javascript():
        script = (
            JS.replace(
                "Passkey authentication verified. No review, reset or trading approved.",
                "Credential binding signed. No review, reset or trading approved.",
            )
            if binding
            else JS
        )
        return Response(script, media_type="application/javascript")

    @app.get("/status")
    def status():
        try:
            credential = context()
            return {
                "credential_sha256": hashlib.sha256(bytes(credential)).hexdigest(),
                "purpose": purpose,
                "reset_authorized": False,
            }
        except (ValueError, OSError):
            raise HTTPException(409, "Diagnostic unavailable") from None

    @app.post("/begin")
    def begin():
        try:
            credential = context()
            nonce = secrets.token_bytes(32)
            challenge = hashlib.sha256(domain + nonce + bytes.fromhex(expected_sha256)).digest()
            options, state = server.authenticate_begin(
                [credential], user_verification="required", challenge=challenge
            )
        except (ValueError, OSError):
            raise HTTPException(409, "Diagnostic context rejected") from None
        with lock:
            for token in list(pending):
                if clock() >= pending[token][0]:
                    del pending[token]
            if completed[0] or pending:
                raise HTTPException(409, "Diagnostic already used or pending")
            token = secrets.token_urlsafe(32)
            pending[token] = (clock() + 30, state, nonce)
        response = JSONResponse(dict(options))
        response.set_cookie(
            "owner_auth_diagnostic", token, httponly=True, samesite="strict", max_age=30
        )
        return response

    @app.post("/complete")
    async def complete(request: Request):
        with lock:
            saved = pending.pop(request.cookies.get("owner_auth_diagnostic"), None)
            if saved is None or clock() >= saved[0] or completed[0]:
                raise HTTPException(403, "Missing, expired or consumed diagnostic")
            completed[0] = True  # Attempt is single-use even if verification/retention fails.
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 65536:
                raise HTTPException(413, "Diagnostic assertion too large")
        try:
            credential = context()
            assertion = json.loads(raw)
            server.authenticate_complete(saved[1], [credential], assertion)
            result = {
                "schema_version": "owner-credential-binding-v1"
                if binding
                else "owner-auth-diagnostic-v1",
                "purpose": purpose,
                "observed_at_utc": now().isoformat(),
                "configuration_sha256": expected_sha256,
                "credential_sha256": hashlib.sha256(bytes(credential)).hexdigest(),
                "challenge_state": saved[1],
                "nonce_hex": saved[2].hex(),
                "assertion": assertion,
                "authentication_verified": True,
                "credential_binding_authorized": binding,
                "standard_owner_process_verified": True,
                "review_signature_issued": False,
                "guardian_called": False,
                "reset_authorized": False,
                "execution_available": False,
                "trial_started": False,
            }
            retain(result)
        except (ValueError, TypeError, KeyError, OSError):
            raise HTTPException(403, "Authentication or retention rejected") from None
        return {
            "authentication_verified": True,
            "credential_binding_authorized": binding,
            "reset_authorized": False,
            "execution_available": False,
        }

    return app
