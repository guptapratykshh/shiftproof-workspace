"""Isolated browser-test API. This never starts against the user's application database."""

import os
from pathlib import Path
import subprocess
import sys

if os.environ.get("SHIFTPROOF_BROWSER_TEST") != "1":
    raise SystemExit("This entry point is only for the isolated browser test suite")

root = Path("/tmp/shiftproof-browser-qa")
root.mkdir(mode=0o700, exist_ok=True)
database = root / "browser-tests.db"
for path in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
    path.unlink(missing_ok=True)
os.environ.update(
    DATABASE_URL=f"sqlite:///{database}",
    APP_ENV="test",
    FRONTEND_URL="http://127.0.0.1:5175",
    ALLOWED_ORIGINS='["http://127.0.0.1:5175"]',
    MAIL_MODE="file",
    STORAGE_DIRECTORY=str(root / "evidence"),
    GNANI_API_KEY="",
    GEMINI_API_KEY="",
)
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
import uvicorn

uvicorn.run("app.main:app", host="127.0.0.1", port=8001, access_log=False)
