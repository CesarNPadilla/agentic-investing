"""Staged, separate local owner review UI; never a reset or broker endpoint."""

import argparse
import hashlib
import json
import secrets
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fido2.server import Fido2Server
from fido2.utils import websafe_decode
from fido2.webauthn import AttestedCredentialData, PublicKeyCredentialRpEntity

from security.webull_guarded_review import consume_guarded_review
from security.webull_review_journal import ReviewJournal
from security.webull_review_signature import (
    ORIGIN,
    ReviewEnvelope,
    review_challenge,
    review_purpose,
)


def create_app(
    credential_file,
    envelope_file,
    journal_file,
    *,
    now=None,
    clock=time.monotonic,
    guardian_exchange=None,
    context_loader=None,
):
    if context_loader is None:
        paths = [Path(value).resolve() for value in (credential_file, envelope_file, journal_file)]
        root = Path(__file__).resolve().parents[1]
        if any(path.is_relative_to(root) for path in paths) or len(set(paths)) != 3:
            raise ValueError("Three distinct private paths outside repository required")
        credential_file, envelope_file, journal_file = paths
    elif not callable(context_loader):
        raise ValueError("Callable protected context loader required")
    now = now or (lambda: datetime.now(UTC))
    server = Fido2Server(
        PublicKeyCredentialRpEntity(id="localhost", name="Agentic Investing Webull Owner"),
        verify_origin=lambda value: value == ORIGIN,
    )
    pending, lock = {}, threading.Lock()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def context():
        if context_loader is not None:
            return context_loader()
        envelope = ReviewEnvelope.model_validate_json(envelope_file.read_text(encoding="utf-8"))
        credential = AttestedCredentialData(
            websafe_decode(
                json.loads(credential_file.read_text(encoding="utf-8"))["credential_data"]
            )
        )
        current = now()
        if (
            not envelope.issued_at <= current < envelope.expires_at
            or hashlib.sha256(bytes(credential)).hexdigest() != envelope.credential_sha256
        ):
            raise ValueError("Changed credential or expired review")
        journal = ReviewJournal(journal_file, expected_envelope=envelope)
        if journal.verify(credential)["retained_review_count"]:
            raise ValueError("Review already consumed")
        return envelope, credential, journal

    @app.middleware("http")
    async def local_only(request, call_next):
        if request.headers.get("host") != "localhost:8767" or (
            request.method != "GET" and request.headers.get("origin") != ORIGIN
        ):
            return JSONResponse({"error": "Local host/origin rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'none'"
        )
        return response

    @app.get("/")
    def page():
        text = Path(__file__).with_suffix(".html").read_text(encoding="utf-8")
        try:
            envelope, _, _ = context()
            if envelope.action == "REVIEW_DISPOSABLE_CONTROLS_TEST_ONLY":
                text = text.replace(
                    "Webull prerequisite review only", "Disposable controls-test review only"
                )
                start = text.index("<p>This signature")
                end = text.index("</p>", start) + 4
                text = (
                    text[:start]
                    + (
                        "<p>SYNTHETIC ACCOUNT AND PLAN. This tests your passkey and guardian retention only. "
                        "There is no real brokerage account or reset plan in this review. "
                        "Signing does not approve a reset, trading or trial activation.</p>"
                    )
                    + text[end:]
                )
                text = text.replace("Sign this review with", "Sign this disposable test with")
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            raise HTTPException(409, "Review page context unavailable") from None
        return HTMLResponse(text)

    @app.get("/owner.js")
    def javascript():
        return Response(
            Path(__file__).with_suffix(".js").read_text(encoding="utf-8"),
            media_type="application/javascript",
        )

    @app.get("/review")
    def review():
        try:
            envelope, _, _ = context()
            return {
                "envelope": envelope.model_dump(mode="json"),
                "digest": envelope.digest(),
                "reset_authorized": False,
                "execution_available": False,
            }
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            raise HTTPException(409, "Private review context unavailable or already used") from None

    @app.post("/begin")
    def begin(request: Request):
        if not callable(guardian_exchange):
            raise HTTPException(503, "Guardian integration unavailable")
        try:
            envelope, credential, _ = context()
            if request.headers.get("x-owner-review-sha256") != envelope.digest():
                raise ValueError("Displayed review changed")
            nonce = secrets.token_bytes(32)
            options, state = server.authenticate_begin(
                [credential],
                user_verification="required",
                challenge=review_challenge(envelope, nonce),
            )
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            raise HTTPException(409, "Review context rejected") from None
        with lock:
            tick = clock()
            for token in list(pending):
                if tick >= pending[token][0]:
                    del pending[token]
            if len(pending) >= 8:
                raise HTTPException(429, "Pending challenge limit")
            token = secrets.token_urlsafe(32)
            pending[token] = (tick + 120, envelope, nonce, state)
        response = JSONResponse(dict(options))
        response.set_cookie(
            "webull_owner_challenge", token, httponly=True, samesite="strict", max_age=120
        )
        return response

    @app.post("/complete")
    async def complete(request: Request):
        with lock:
            saved = pending.pop(request.cookies.get("webull_owner_challenge"), None)
        if saved is None or clock() >= saved[0]:
            raise HTTPException(403, "Missing, expired or used challenge")
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > 65536:
                raise HTTPException(413, "Assertion too large")
        try:
            envelope, credential, journal = context()
            if envelope.digest() != saved[1].digest():
                raise ValueError("In-flight review changed")
            receipt = {
                "purpose": review_purpose(envelope),
                "envelope": envelope.model_dump(mode="json"),
                "envelope_sha256": envelope.digest(),
                "challenge_nonce_hex": saved[2].hex(),
                "challenge_state": saved[3],
                "assertion": json.loads(raw),
                "reset_authorized": False,
                "execution_available": False,
            }
            result = consume_guarded_review(
                receipt, credential, journal, exchange=guardian_exchange, now=now
            )
        except (ValueError, TypeError, KeyError, OSError, sqlite3.Error):
            raise HTTPException(403, "Review signature or retention rejected") from None
        return result

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", required=True, type=Path)
    parser.add_argument("--envelope-file", required=True, type=Path)
    parser.add_argument("--journal-file", required=True, type=Path)
    args = parser.parse_args()
    uvicorn.run(
        create_app(args.credential_file, args.envelope_file, args.journal_file),
        host="127.0.0.1",
        port=8767,
        access_log=False,
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
