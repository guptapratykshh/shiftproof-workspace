"""Read a test-only verification token from the isolated browser database."""

import os
import re
import sys

from sqlalchemy import select

url = os.environ.get("SHIFTPROOF_BROWSER_DATABASE_URL", "")
os.environ["DATABASE_URL"] = url or "sqlite:////tmp/shiftproof-browser-qa/browser-tests.db"

from app.db import SessionLocal, engine
from app.models import BackgroundJob

if url and (
    engine.dialect.name != "mongodb" or not engine.database.name.startswith("shiftproof_test_browser_")
):
    raise SystemExit("Only the isolated browser database is allowed")
with SessionLocal() as db:
    jobs = db.scalars(
        select(BackgroundJob).where(BackgroundJob.kind == "email").order_by(BackgroundJob.created_at.desc())
    )
    payload = next(job.payload for job in jobs if job.payload.get("to") == sys.argv[1])
    print(re.search(r"token=([\w-]+)", payload["text"])[1])
