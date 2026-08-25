"""Initialize the PostgreSQL DB using Alembic migrations.

This replaces the previous raw‑SQL `schema.sql` approach. The function now
invokes Alembic to apply any pending migrations, ensuring the database schema
matches the ORM models defined in `db/models.py`.
"""

import os
import subprocess

def init_db():
    """Run Alembic migrations against the configured database.

    The database URL is taken from the same environment variables used by
    ``alembic/env.py`` (`DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`).
    ``alembic upgrade head`` is executed via ``subprocess.run`` so that the
    command respects the project's virtual‑env and exits with an exception on
    failure.
    """

    # Ensure the required environment variables are present; Alembic will raise
    # a clear error if any are missing.
    required_vars = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME"]
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(
            f"Missing required DB env vars for Alembic migration: {', '.join(missing)}"
        )

    # Run ``alembic upgrade head`` in the project's root. ``check=True`` makes
    # the call raise a CalledProcessError on non‑zero exit status.
    subprocess.run(["alembic", "upgrade", "head"], check=True)
