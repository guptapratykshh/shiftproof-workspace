"""Copy a stopped SQL application's records to an empty MongoDB database.

The source is read-only, IDs and relationships are preserved, and every collection
is verified before the target is marked ready. A matching interrupted import can
resume; different or extra destination records are never overwritten or deleted.
"""

import argparse
import hashlib
import json
from datetime import datetime

from sqlalchemy import create_engine, select

from .db import engine
from .mongo import registry
from .mongo_query import canonical


def encoded(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.isoformat() if isinstance(value, datetime) else str(value),
    )


def fingerprint(documents):
    ordered = sorted(documents, key=lambda row: str(row["_id"]))
    return hashlib.sha256(encoded(ordered).encode()).hexdigest()


def migrate(source, dry_run=False):
    if engine.dialect.name != "mongodb":
        raise ValueError("DATABASE_URL must select the intended MongoDB database")
    source_engine = create_engine(source)
    payload = {}
    try:
        with source_engine.connect() as connection:
            if source_engine.dialect.name == "sqlite":
                connection.exec_driver_sql("PRAGMA query_only=ON")
            for name, mapper in registry().items():
                records = []
                primary = mapper.primary_key[0].name
                for row in connection.execute(select(mapper.local_table)).mappings():
                    values = canonical(dict(row))
                    records.append({"_id": values[primary], "_rev": 1, **values})
                payload[name] = records
    finally:
        source_engine.dispose()
    manifest = {
        name: {"count": len(rows), "sha256": fingerprint(rows)} for name, rows in sorted(payload.items())
    }
    dataset_hash = hashlib.sha256(encoded(manifest).encode()).hexdigest()
    database = engine.database
    engine.ping()
    marker = database["_migration_runs"].find_one({"_id": "sql-import"})
    if marker and marker["source_sha256"] != dataset_hash:
        raise ValueError("Destination belongs to a different import; no data was changed")
    if not marker:
        for name in payload:
            if database[name].find_one({}, {"_id": 1}):
                raise ValueError("Destination already contains application data; no records will be replaced")
    report = {
        "database": database.name,
        "source_sha256": dataset_hash,
        "collections": manifest,
        "records": sum(len(rows) for rows in payload.values()),
    }
    if dry_run:
        return {**report, "status": "validated_source"}
    engine.bootstrap()
    database["_migration_runs"].update_one(
        {"_id": "sql-import"},
        {"$setOnInsert": {"source_sha256": dataset_hash, "state": "copying"}},
        upsert=True,
    )
    for name, rows in sorted(payload.items()):
        existing = {row["_id"]: row for row in database[name].find({})}
        expected_ids = {row["_id"] for row in rows}
        if set(existing) - expected_ids:
            raise ValueError(f"Unexpected records in {name}; import stopped without deleting them")
        pending = []
        for row in rows:
            found = existing.get(row["_id"])
            if found is not None:
                if encoded(found) != encoded(row):
                    raise ValueError(
                        f"A destination record in {name} differs; import stopped without overwriting it"
                    )
            else:
                pending.append(row)
        for start in range(0, len(pending), 500):
            database[name].insert_many(pending[start : start + 500], ordered=True)
        actual = list(database[name].find({}))
        if len(actual) != len(rows) or fingerprint(actual) != manifest[name]["sha256"]:
            raise ValueError(f"Verification failed for {name}")
    database["_migration_runs"].update_one(
        {"_id": "sql-import"},
        {"$set": {"state": "verified", "manifest": manifest, "records": report["records"]}},
    )
    return {**report, "status": "verified"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Read-only SQL backup URL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(migrate(args.source, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
