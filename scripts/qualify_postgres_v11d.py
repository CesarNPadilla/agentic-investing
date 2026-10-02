"""Run synthetic qualification in a newly created disposable PostgreSQL container."""
import os
import secrets
import subprocess
import sys
import time
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo


def main():
    name = "agentic-v11d-test-" + uuid4().hex[:12]
    env = os.environ.copy()
    env["POSTGRES_PASSWORD"] = secrets.token_urlsafe(32)
    container = None
    try:
        result = subprocess.run(["docker", "run", "-d", "--name", name,
                                 "-e", "POSTGRES_PASSWORD", "-e", "POSTGRES_DB=synthetic_v11d",
                                 "-p", "127.0.0.1::5432", "postgres:17"],
                                env=env, capture_output=True, text=True, check=True)
        container = result.stdout.strip()
        port = subprocess.check_output(["docker", "port", container, "5432/tcp"], text=True).strip().split(":")[-1]
        dsn = make_conninfo(host="127.0.0.1", port=port, dbname="synthetic_v11d",
                            user="postgres", password=env["POSTGRES_PASSWORD"], connect_timeout=2)
        for _ in range(30):
            try:
                with psycopg.connect(dsn) as db:
                    version = db.execute("SHOW server_version").fetchone()[0]
                break
            except psycopg.Error:
                time.sleep(1)
        else:
            print("Isolated PostgreSQL did not become ready.")
            return 1
        print("Isolated PostgreSQL version:", version, flush=True)
        env["AIL_V11D_SYNTHETIC_TEST_DSN"] = dsn
        return subprocess.run([sys.executable, "-m", "pytest", "tests/test_postgres_synthetic_v11.py",
                               "tests/test_evidence_v11.py", "tests/test_reservations_v11.py", "tests/test_sleeve_store_v11.py",
                               "tests/test_sleeve_v11.py", "tests/test_investment_policy.py",
                               "tests/test_policy_v01.py", "tests/test_policy_v02.py",
                               "tests/test_risk_diagnostics_v09.py", "tests/test_controlled_experiments_v08.py", "-q"],
                              env=env, check=False).returncode
    except (subprocess.SubprocessError, ValueError):
        print("Isolated PostgreSQL qualification could not run.")
        return 1
    finally:
        if container:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True, check=False)


if __name__ == "__main__":
    raise SystemExit(main())
