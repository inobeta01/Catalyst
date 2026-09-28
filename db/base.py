import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()

# Prefer a fully‑formed DATABASE_URL (Neon provides this).
# Fall back to the legacy DB_* components for local development.
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
else:
    user = os.getenv("DB_USER")
    pw = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    name = os.getenv("DB_NAME")
    if not all([user, pw, host, name]):
        raise RuntimeError(
            "Missing required DB_* environment variables. "
            "Set DATABASE_URL or DB_USER, DB_PASSWORD, DB_HOST, DB_NAME."
        )
    DATABASE_URL = (
        f"postgresql+psycopg2://{quote_plus(user)}:{quote_plus(pw)}@{host}/{name}"
    )

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
