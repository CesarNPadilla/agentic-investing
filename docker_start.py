"""Container entrypoint: safely encode the local database password in its URL."""

import os

import uvicorn
from sqlalchemy import URL

if __name__ == "__main__":
    os.environ["AIL_DATABASE_URL"] = URL.create(
        "postgresql+psycopg",
        username="research",
        password=os.environ["POSTGRES_PASSWORD"],
        host="db",
        database="research",
    ).render_as_string(hide_password=False)
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000)
