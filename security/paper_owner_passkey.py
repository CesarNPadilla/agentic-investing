"""Separate loopback owner enrollment/authentication; no ledger or broker authority."""

import argparse
import asyncio
import hashlib
import json
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fido2.server import Fido2Server
from fido2.utils import websafe_decode, websafe_encode
from fido2.webauthn import (
    AttestedCredentialData,
    AuthenticationResponse,
    PublicKeyCredentialRpEntity,
    PublicKeyCredentialUserEntity,
)

from security.paper_recovery_review import RecoveryReview

ORIGIN = "http://localhost:8766"


def create_app(credential_file, *, clock=time.monotonic, review_file=None):
    credential_file = Path(credential_file)
    root = Path(__file__).resolve().parents[1]
    if credential_file.resolve().is_relative_to(root):
        raise ValueError("Owner credential must be outside repository")
    if review_file is not None:
        review_file = Path(review_file)
        if review_file.resolve().is_relative_to(root):
            raise ValueError("Owner review must be outside repository")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    server = Fido2Server(
        PublicKeyCredentialRpEntity(id="localhost", name="Agentic Investing Owner"),
        verify_origin=lambda value: value == ORIGIN,
    )
    pending = {}

    def review():
        if review_file is None:
            raise ValueError("No recovery review prepared")
        result = RecoveryReview.model_validate_json(review_file.read_text(encoding="utf-8"))
        existing = credential()
        if existing is None:
            raise ValueError("Enrollment required")
        return result.validate_current(
            credential_sha256=hashlib.sha256(bytes(existing)).hexdigest()
        )

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.headers.get("host") != "localhost:8766":
            return JSONResponse({"error": "Invalid local host"}, status_code=403)
        if request.method != "GET" and request.headers.get("origin") != ORIGIN:
            return JSONResponse({"error": "Invalid origin"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        return response

    def credential():
        if not credential_file.exists():
            return None
        return AttestedCredentialData(
            websafe_decode(
                json.loads(credential_file.read_text(encoding="utf-8"))["credential_data"]
            )
        )

    @app.get("/")
    def page():
        return HTMLResponse(
            (Path(__file__).with_name("paper_owner_passkey.html")).read_text(encoding="utf-8")
        )

    @app.get("/owner.js")
    def javascript():
        from fastapi.responses import Response

        return Response(
            Path(__file__).with_name("paper_owner_passkey.js").read_text(encoding="utf-8"),
            media_type="application/javascript",
        )

    @app.get("/recovery-review")
    def review_page():
        try:
            proposal = review()
            return {"review": proposal.model_dump(mode="json"), "digest": proposal.digest()}
        except (ValueError, TypeError, OSError):
            raise HTTPException(409, "Recovery review unavailable or expired") from None

    @app.post("/begin/{mode}")
    def begin(mode, request: Request):
        if mode not in {"enroll", "verify", "review"}:
            raise HTTPException(404)
        existing = credential()
        if (mode == "enroll") == (existing is not None):
            raise HTTPException(409, "Enrollment exists or verification needs enrollment")
        if mode == "enroll":
            options, state = server.register_begin(
                PublicKeyCredentialUserEntity(
                    id=hashlib.sha256(b"cesar.nieto@outlook.com").digest(),
                    name="cesar.nieto@outlook.com",
                    display_name="CESAR NIETO PADILLA",
                ),
                user_verification="required",
                authenticator_attachment="platform",
                resident_key_requirement="preferred",
            )
        else:
            try:
                proposal = review() if mode == "review" else None
            except (ValueError, TypeError, OSError):
                raise HTTPException(409, "Recovery review unavailable or expired") from None
            if proposal and request.headers.get("x-owner-review-sha256") != proposal.digest():
                raise HTTPException(409, "Displayed recovery review differs")
            nonce = secrets.token_bytes(32)
            challenge = (
                hashlib.sha256(nonce + bytes.fromhex(proposal.digest())).digest()
                if proposal
                else None
            )
            options, state = server.authenticate_begin(
                [existing], user_verification="required", challenge=challenge
            )
        now = clock()
        for identifier in list(pending):
            if now > pending[identifier][2]:
                del pending[identifier]
        if len(pending) >= 8:
            raise HTTPException(429, "Too many pending challenges")
        token = secrets.token_urlsafe(32)
        pending[token] = (
            mode,
            state,
            now + 120,
            proposal.model_dump(mode="json") if mode == "review" else None,
            nonce.hex() if mode == "review" else None,
        )
        response = JSONResponse(dict(options))
        response.set_cookie("owner_challenge", token, httponly=True, samesite="strict", max_age=120)
        return response

    def persist_enrollment(row):
        credential_file.parent.mkdir(parents=True, exist_ok=True)
        with credential_file.open("x", encoding="utf-8") as handle:
            json.dump(row, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

    def persist_verification(row):
        folder = credential_file.parent / "owner-passkey-verifications"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / (secrets.token_hex(16) + ".json")
        with target.open("x", encoding="utf-8") as handle:
            json.dump(row, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())

    @app.post("/complete/{mode}")
    async def complete(mode, request: Request):
        record = pending.pop(request.cookies.get("owner_challenge"), None)
        if record is None or mode != record[0] or clock() > record[2]:
            raise HTTPException(403, "Missing, expired or used challenge")
        if len(await request.body()) > 65536:
            raise HTTPException(413)
        try:
            response = await request.json()
            if mode == "enroll":
                data = server.register_complete(record[1], response)
                row = {
                    "credential_data": websafe_encode(bytes(data.credential_data)),
                    "enrolled_at_utc": datetime.now(UTC).isoformat(),
                    "declared_owner": "CESAR NIETO PADILLA",
                    "identity_independently_verified": False,
                    "execution_authority": False,
                }
                await asyncio.to_thread(persist_enrollment, row)
            else:
                existing = credential()
                if existing is None:
                    raise ValueError("Missing owner credential")
                parsed = AuthenticationResponse.from_dict(response)
                server.authenticate_complete(record[1], [existing], parsed)
                proposal = None
                if mode == "review":
                    proposal = review()
                    saved = RecoveryReview.model_validate(record[3])
                    if proposal.digest() != saved.digest():
                        raise ValueError("Recovery review changed during authentication")
                await asyncio.to_thread(
                    persist_verification,
                    {
                        "schema_version": "owner-passkey-verification-v1",
                        "verified_at_utc": datetime.now(UTC).isoformat(),
                        "credential_sha256": hashlib.sha256(bytes(existing)).hexdigest(),
                        "origin": ORIGIN,
                        "user_verification_required": True,
                        "purpose": "RECOVERY_PLAN_REVIEW_ONLY"
                        if proposal
                        else "AUTHENTICATION_TEST_ONLY",
                        "review": proposal.model_dump(mode="json") if proposal else None,
                        "review_sha256": proposal.digest() if proposal else None,
                        "challenge_nonce_hex": record[4],
                        "challenge_state": record[1],
                        "assertion": response,
                        "reset_authorized": False,
                        "execution_available": False,
                    },
                )
            return {
                "user_verification_passed": True,
                "purpose": "RECOVERY_PLAN_REVIEW_ONLY"
                if mode == "review"
                else "ENROLLMENT_OR_AUTH_TEST_ONLY",
                "reset_authorized": False,
                "execution_available": False,
            }
        except (ValueError, TypeError, KeyError, OSError):
            raise HTTPException(403, "Owner verification rejected") from None

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, required=True)
    parser.add_argument("--review-file", type=Path)
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.credential_file, review_file=args.review_file),
        host="127.0.0.1",
        port=8766,
        access_log=False,
        log_level="warning",
    )


if __name__ == "__main__":
    main()
