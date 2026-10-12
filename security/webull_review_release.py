"""Build and verify a pinned review-only source package; no deployment or activation."""

import argparse
import hashlib
import json
from pathlib import Path

LEGACY_FILES = (
    "security/webull_review_signature.py",
    "security/webull_review_journal.py",
    "security/webull_review_checkpoint.py",
    "security/webull_owner_review_app.py",
    "security/webull_owner_review_app.html",
    "security/webull_owner_review_app.js",
)
FILES = (*LEGACY_FILES, "security/webull_guarded_review.py")
MANIFEST = "review-release.json"


def _regular(path):
    # Reject symlinks and Windows reparse points, including ancestors within the bundle.
    if (
        path.is_symlink()
        or path.is_junction()
        or (getattr(path.stat(), "st_file_attributes", 0) & 0x400)
    ):
        raise ValueError("Reparse point forbidden in release")


def verify_release(directory, expected_manifest_sha256):
    root = Path(directory).absolute()
    _regular(root)
    raw = (root / MANIFEST).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_manifest_sha256:
        raise ValueError("Release manifest digest mismatch")
    manifest = json.loads(raw)
    expected_files = {
        "webull-review-source-release-v1": LEGACY_FILES,
        "webull-review-source-release-v2": FILES,
    }.get(manifest.get("schema_version"))
    if set(manifest) != {"schema_version", "scope", "execution_available", "files"} or (
        expected_files is None
        or manifest["scope"] != "REVIEW_ONLY_SOURCE_NO_EXECUTABLE_ENVIRONMENT"
        or manifest["execution_available"] is not False
        or set(manifest["files"]) != set(expected_files)
    ):
        raise ValueError("Release scope or inventory mismatch")
    actual = set()
    for path in root.rglob("*"):
        _regular(path)
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != {MANIFEST, *expected_files}:
        raise ValueError("Unexpected or missing release files")
    for name, digest in manifest["files"].items():
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise ValueError("Release source digest mismatch")
    return manifest


def build_release(source_root, destination):
    source_root, destination = Path(source_root).resolve(), Path(destination).absolute()
    if destination.is_relative_to(source_root):
        raise ValueError("Staging must be outside source checkout")
    payloads = {}
    for name in FILES:
        path = source_root / name
        _regular(path.parent)
        _regular(path)
        payloads[name] = path.read_bytes()
    manifest = {
        "schema_version": "webull-review-source-release-v2",
        "scope": "REVIEW_ONLY_SOURCE_NO_EXECUTABLE_ENVIRONMENT",
        "execution_available": False,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()},
    }
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    destination.mkdir(parents=False, exist_ok=False)
    (destination / "security").mkdir()
    for name, data in payloads.items():
        with (destination / name).open("xb") as stream:
            stream.write(data)
    with (destination / MANIFEST).open("xb") as stream:
        stream.write(raw)
    digest = hashlib.sha256(raw).hexdigest()
    verify_release(destination, digest)
    return {
        "source_bundle": str(destination),
        "manifest_sha256": digest,
        "files_verified": len(FILES),
        "protected_deployment_performed": False,
        "execution_available": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build_release(Path(__file__).resolve().parents[1], args.destination)))


if __name__ == "__main__":
    main()
