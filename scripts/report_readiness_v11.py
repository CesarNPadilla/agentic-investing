"""Print the current nonexecuting readiness audit; no services or data changed."""
from pathlib import Path

from risk.readiness_v11 import build_current_readiness

if __name__ == "__main__":
    print(build_current_readiness(Path(__file__).resolve().parents[1]).model_dump_json(indent=2))
