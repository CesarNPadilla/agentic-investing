"""Standard-owner app construction probe; no HTTP listener, passkey or exchange."""

import hashlib
import json
import sys
from pathlib import Path

from security.webull_pinned_owner_app import create_pinned_owner_app


def main():
    _, path, pin, manifest, owner, guardian, result_path = sys.argv

    def unavailable(_):
        raise PermissionError("No transport in construction probe")

    app = create_pinned_owner_app(
        path,
        owner_sid=owner,
        guardian_sid=guardian,
        expected_sha256=pin,
        expected_manifest_sha256=manifest,
        guardian_exchange=unavailable,
    )
    # Direct read-only route invocation, not a listening server or challenge.
    review = next(route.endpoint for route in app.routes if route.path == "/review")()
    if review["reset_authorized"] is not False or review["execution_available"] is not False:
        raise ValueError("Review scope changed")
    result = {
        "schema_version": "pinned-owner-app-construction-v1",
        "configuration_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "manifest_sha256": manifest,
        "envelope_sha256": review["digest"],
        "standard_owner_process_verified": True,
        "protected_context_loaded": True,
        "http_listener_started": False,
        "challenge_issued": False,
        "passkey_used": False,
        "guardian_exchange_called": False,
        "reset_authorized": False,
        "execution_available": False,
        "trial_started": False,
    }
    with Path(result_path).open("x", encoding="utf-8") as stream:
        json.dump(result, stream)


if __name__ == "__main__":
    main()
