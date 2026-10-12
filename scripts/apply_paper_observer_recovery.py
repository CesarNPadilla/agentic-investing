"""Apply signed read-only observer acknowledgement; cannot clear risk latches."""

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values
from fido2.utils import websafe_decode
from fido2.webauthn import AttestedCredentialData

from integrations.brokers.alpaca_paper_read import AlpacaPaperAccountReader
from risk.paper_state import PaperState
from security.paper_observer_recovery import apply_readonly_recovery


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("env-file", "ledger-file", "receipt-file", "owner-credential-file"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        if any(path.resolve().is_relative_to(root) for path in vars(args).values()):
            raise ValueError("All inputs must remain outside repository")
        values = dotenv_values(args.env_file)
        credential = AttestedCredentialData(
            websafe_decode(
                json.loads(args.owner_credential_file.read_text(encoding="utf-8"))[
                    "credential_data"
                ]
            )
        )
        receipt = json.loads(args.receipt_file.read_text(encoding="utf-8"))
        snapshot = AlpacaPaperAccountReader(
            values["AIL_ALPACA_API_KEY"], values["AIL_ALPACA_API_SECRET"]
        ).observe()
        report = apply_readonly_recovery(
            PaperState(args.ledger_file), receipt, credential, snapshot
        )
        print(json.dumps(report))
        return 0
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        print(
            json.dumps({"blockers": ["READ_ONLY_RECOVERY_REJECTED"], "execution_available": False})
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
