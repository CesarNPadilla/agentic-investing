"""Verify Webull sandbox API access without displaying account data or placing orders."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from integrations.brokers.webull_sandbox import (
    WebullSandboxAccess,
    WebullSandboxCredentials,
    WebullSandboxError,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        credentials = WebullSandboxCredentials(_env_file=arguments.env_file)
        result = WebullSandboxAccess(
            credentials.app_key.get_secret_value(),
            credentials.app_secret.get_secret_value(),
        ).verify_access()
    except (OSError, ValidationError):
        parser.exit(2, "Sandbox env file missing or missing required credential variables.\n")
    except WebullSandboxError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Webull {result['environment']} connection verified; account details withheld.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())