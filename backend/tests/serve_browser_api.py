"""Isolated browser-test API. This never starts against the user's application database."""

import os
from pathlib import Path
import subprocess
import sys

if os.environ.get("SHIFTPROOF_BROWSER_TEST") != "1":
    raise SystemExit("This entry point is only for the isolated browser test suite")

port = int(os.environ.get("SHIFTPROOF_BROWSER_PORT", "8001"))
frontend_port = int(os.environ.get("SHIFTPROOF_BROWSER_FRONTEND_PORT", "5175"))
root = Path(os.environ.get("SHIFTPROOF_BROWSER_ROOT", "/tmp/shiftproof-browser-qa"))
root.mkdir(mode=0o700, exist_ok=True)
database = root / "browser-tests.db"
mongo_url = os.environ.get("SHIFTPROOF_BROWSER_DATABASE_URL", "")
for path in (database, Path(str(database) + "-wal"), Path(str(database) + "-shm")):
    path.unlink(missing_ok=True)
os.environ.update(
    DATABASE_URL=mongo_url or f"sqlite:///{database}",
    APP_ENV="test",
    FRONTEND_URL=f"http://127.0.0.1:{frontend_port}",
    ALLOWED_ORIGINS=f'["http://127.0.0.1:{frontend_port}"]',
    MAIL_MODE="file",
    COOKIE_SECURE="false",
    STORAGE_DIRECTORY=str(root / "evidence"),
    GNANI_API_KEY="",
    GEMINI_API_KEY="",
)
from app.db import engine

if mongo_url:
    if engine.dialect.name != "mongodb" or not engine.database.name.startswith("shiftproof_test_browser_"):
        raise SystemExit("Browser tests require a dedicated shiftproof_test_browser_ database")
    if engine.database.list_collection_names():
        raise SystemExit("Browser test database must be empty")
subprocess.run([sys.executable, "-m", "app.bootstrap"], check=True)
import uvicorn

try:
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, access_log=False)
finally:
    if mongo_url:
        engine.client.drop_database(engine.database.name)
