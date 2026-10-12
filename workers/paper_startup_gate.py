"""Bounded child bootstrap gate, before credentials, ledger or network access."""

import time
from pathlib import Path


def await_startup_gate(path, token, *, root, timeout=5):
    path = Path(path).resolve()
    if path.is_relative_to(Path(root).resolve()) or not token or not 0 < timeout <= 5:
        raise ValueError("Invalid private startup gate")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = path.read_text(encoding="ascii")
        except FileNotFoundError:
            time.sleep(0.02)
            continue
        if value != token:
            raise ValueError("Startup gate does not match")
        return
    raise TimeoutError("Parent did not release startup gate")
