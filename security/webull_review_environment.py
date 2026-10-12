"""Stage a pinned embedded review environment; never installs or starts the app."""

import base64
import hashlib
import json
import zipfile
from importlib import metadata
from pathlib import Path, PurePosixPath

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOTS = ("fastapi", "uvicorn", "fido2", "pydantic", "cryptography")
ARCHIVE_SHA256 = "d297e5ff019966817ad8502465176139f2d3d840fa4ed84b13bed399a6ab1f15"
SOURCE = Path(
    r"C:\ProgramData\AgenticInvestingPaper\OwnerControl\WebullReviewSource-3f83d3a65cead1c1"
)


def dependencies():
    queue, found = list(ROOTS), {}
    environment = default_environment()
    environment["extra"] = ""
    while queue:
        name = canonicalize_name(queue.pop())
        if name in found:
            continue
        dist = metadata.distribution(name)
        found[name] = dist.version
        for text in dist.requires or []:
            requirement = Requirement(text)
            if requirement.marker is None or requirement.marker.evaluate(environment):
                installed = metadata.distribution(requirement.name)
                if installed.version not in requirement.specifier:
                    raise ValueError("Installed dependency version mismatch")
                queue.append(requirement.name)
    return dict(sorted(found.items()))


def safe_name(name):
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or any(part in ("..", ".") for part in path.parts)
        or ("\\" in name or ":" in name or path.as_posix() != name)
    ):
        raise ValueError("Unsafe package path")
    return path


def stage_environment(archive, destination):
    archive, destination = Path(archive), Path(destination)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Embedded runtime archive digest changed")
    versions = dependencies()
    payloads = {}
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            name = str(safe_name(entry.filename))
            if entry.is_dir() or name in payloads or entry.file_size > 30_000_000:
                raise ValueError("Unexpected embedded archive entry")
            payloads[name] = bundle.read(entry)
    for name in versions:
        dist = metadata.distribution(name)
        base = Path(dist.locate_file("")).resolve()
        for file in dist.files or []:
            relative = str(file).replace("\\", "/")
            if relative.startswith("../"):
                # Console entry points are not part of the embedded application.
                if relative.startswith("../../Scripts/"):
                    continue
                raise ValueError("Unexpected distribution outside package directory")
            safe_name(relative)
            if "__pycache__" in file.parts or relative.endswith(".pyc"):
                continue
            path = Path(dist.locate_file(file))
            if path.is_symlink() or not path.resolve().is_relative_to(base):
                raise ValueError("Distribution file escaped package directory")
            data = path.read_bytes()
            if file.hash is None:
                if not relative.endswith(".dist-info/RECORD"):
                    raise ValueError("Unhashed distribution file")
            elif file.hash.mode != "sha256" or (
                base64.urlsafe_b64encode(hashlib.sha256(data).digest()).decode().rstrip("=")
                != file.hash.value
            ):
                raise ValueError("Installed distribution RECORD mismatch")
            target = "packages/" + relative
            if target in payloads and payloads[target] != data:
                raise ValueError("Conflicting package payload")
            payloads[target] = data
    payloads["python314._pth"] = ("python314.zip\n.\npackages\n" + str(SOURCE) + "\n").encode()
    destination.mkdir(exist_ok=False)
    for name, data in payloads.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    manifest = {
        "schema_version": "webull-review-environment-v1",
        "scope": "EMBEDDED_REVIEW_ONLY_NO_BROKER_NO_ACTIVATION",
        "python_version": "3.14.7",
        "archive_url": "https://www.python.org/ftp/python/3.14.7/python-3.14.7-embed-amd64.zip",
        "archive_sha256": ARCHIVE_SHA256,
        "review_source": str(SOURCE),
        "packages": versions,
        "execution_available": False,
        "files": {
            name: hashlib.sha256(data).hexdigest() for name, data in sorted(payloads.items())
        },
    }
    raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (destination / "environment-release.json").write_bytes(raw)
    return {
        "bundle": str(destination),
        "manifest_sha256": hashlib.sha256(raw).hexdigest(),
        "package_count": len(versions),
        "file_count": len(payloads),
    }
