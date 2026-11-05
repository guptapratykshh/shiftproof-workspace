"""Initialize the selected primary database without routing MongoDB through Alembic."""

import subprocess
import sys

from .db import engine


def main():
    if engine.dialect.name == "mongodb":
        engine.ping()
        engine.bootstrap()
        print("MongoDB collections, validators and indexes are ready.")
    else:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)


if __name__ == "__main__":
    main()
