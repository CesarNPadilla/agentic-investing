"""Pin a separate guardian environment/source copy; never deploy or activate it."""

import hashlib
import json
from pathlib import Path

from security.webull_review_release import _regular

ENVIRONMENT_MANIFEST_SHA256 = "f2eb1b3b90ce7a79346ab72189ced4f59eda14ac9c89ddccda2139cc74cbd33b"
LEGACY_FILES = (
    "security/webull_review_signature.py",
    "security/webull_review_journal.py",
    "security/webull_guardian_reference.py",
    "security/webull_guardian_bridge.py",
    "security/windows_guardian_request_pipe.py",
    "security/windows_local_request_pipe.py",
    "security/windows_pipe_identity.py",
    "security/webull_pipe_registration.py",
    "scripts/probe_webull_guardian_pipe.py",
)
FILES = (
    *LEGACY_FILES,
    "security/windows_guardian_exchange_pipe.py",
    "security/webull_guardian_recovery_inspection.py",
    "security/webull_guardian_review_host.py",
    "security/windows_review_process_supervisor.py",
    "workers/windows_child_job.py",
    "security/webull_guardian_host_config.py",
    "security/windows_protected_config.py",
    "security/windows_guardian_exchange_client.py",
    "security/webull_guarded_review.py",
    "scripts/webull_signed_host_fixture.py",
    "security/webull_owner_review_app.py",
    "security/webull_owner_review_app.html",
    "security/webull_owner_review_app.js",
    "security/webull_pinned_owner_app.py",
    "scripts/probe_webull_pinned_owner_app.py",
    "security/webull_owner_credential_registry.py",
    "security/webull_owner_auth_diagnostic.py",
    "scripts/webull_owner_auth_diagnostic.py",
    "scripts/webull_disposable_controls_ceremony.py",
)


def stage_guardian(source, environment, destination):
    source, environment, destination = map(Path, (source, environment, destination))
    if destination.resolve().is_relative_to(source.resolve()):
        raise ValueError("Guardian staging must be outside checkout")
    _regular(environment)
    raw = (environment / "environment-release.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != ENVIRONMENT_MANIFEST_SHA256:
        raise ValueError("Pinned review environment changed")
    inventory = json.loads(raw)
    payloads = {}
    for name, digest in inventory["files"].items():
        path = environment / name
        _regular(path)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError("Pinned environment payload changed")
        payloads[name] = data
    payloads["python314._pth"] = b"python314.zip\n.\npackages\napp\n"
    for name in FILES:
        path = source / name
        _regular(path)
        payloads["app/" + name] = path.read_bytes()
    manifest = {
        "schema_version": "webull-guardian-release-v11",
        "scope": "GUARDIAN_REVIEW_AND_SYNTHETIC_PIPE_ONLY_NO_SERVICE_NO_BROKER",
        "base_environment_manifest_sha256": ENVIRONMENT_MANIFEST_SHA256,
        "execution_available": False,
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())
        },
    }
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    destination.mkdir(exist_ok=False)
    for name, data in payloads.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    (destination / "guardian-release.json").write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()
