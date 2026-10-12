"""Explicit Windows child environment; no ambient environment or launch authority."""

import ntpath
import re


def _local_path(value):
    if (
        not isinstance(value, str)
        or not re.match(r"^[A-Za-z]:[\\/]", value)
        or any(c in value for c in "\x00\r\n;%")
        or ":" in value[2:]
        or ".." in value.replace("/", "\\").split("\\")
    ):
        raise ValueError("Trusted absolute local Windows path required")
    return ntpath.normpath(value)


def build_runtime_environment(*, windows_root, runtime_profile, runtime_temp):
    """Controller-selected paths only; validation is not OS identity/ACL proof.

    Return a complete replacement environment, never a dictionary to merge into
    the parent environment. Caller must also choose a protected executable and
    work directory, disable handle inheritance and enforce the runtime identity.
    """
    windows_root = _local_path(windows_root)
    runtime_profile = _local_path(runtime_profile)
    runtime_temp = _local_path(runtime_temp)
    if (
        ntpath.dirname(windows_root) == windows_root
        or ntpath.dirname(runtime_profile) == runtime_profile
        or ntpath.commonpath([runtime_profile, runtime_temp]).casefold()
        != runtime_profile.casefold()
        or runtime_temp.casefold() == runtime_profile.casefold()
    ):
        raise ValueError("Dedicated profile and contained temporary directory required")
    system32 = ntpath.join(windows_root, "System32")
    return {
        "SystemRoot": windows_root,
        "WINDIR": windows_root,
        "COMSPEC": ntpath.join(system32, "cmd.exe"),
        "PATHEXT": ".COM;.EXE;.BAT;.CMD",
        "PSMODULEPATH": ntpath.join(system32, "WindowsPowerShell", "v1.0", "Modules"),
        "PATH": ";".join(
            [system32, windows_root, ntpath.join(system32, "WindowsPowerShell", "v1.0")]
        ),
        "USERPROFILE": runtime_profile,
        "APPDATA": ntpath.join(runtime_profile, "AppData", "Roaming"),
        "LOCALAPPDATA": ntpath.join(runtime_profile, "AppData", "Local"),
        "TEMP": runtime_temp,
        "TMP": runtime_temp,
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
    }
