"""BSON backups using a snapshot session or quiesced app; restore only to an empty database."""

import argparse
import hashlib
import json
import re
import tarfile
import tempfile
from pathlib import Path

from bson import BSON, decode_file_iter, json_util
from pymongo import IndexModel

from .db import engine


def checksum(stream):
    digest = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def backup(database, destination, session=None):
    # Without a snapshot session the caller must stop every database writer.
    manifest = {"format": 1, "database": database.name, "collections": {}}
    with Path(destination).open("xb") as output:
        Path(destination).chmod(0o600)
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name in sorted(database.list_collection_names()):
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                    raise ValueError("Unexpected collection name")
                collection = database[name]
                with tempfile.TemporaryFile() as data:
                    count = 0
                    for document in collection.find({}, session=session).sort("_id", 1):
                        data.write(BSON.encode(document))
                        count += 1
                    size = data.tell()
                    data.seek(0)
                    digest = checksum(data)
                    data.seek(0)
                    member = tarfile.TarInfo(name + ".bson")
                    member.size, member.mode = size, 0o600
                    archive.addfile(member, data)
                manifest["collections"][name] = {
                    "count": count,
                    "sha256": digest,
                    "options": collection.options(),
                    "indexes": list(collection.list_indexes()),
                }
            with tempfile.TemporaryFile() as metadata:
                metadata.write(json_util.dumps(manifest).encode())
                member = tarfile.TarInfo("manifest.json")
                member.size, member.mode = metadata.tell(), 0o600
                metadata.seek(0)
                archive.addfile(member, metadata)
    return {
        "collections": len(manifest["collections"]),
        "records": sum(v["count"] for v in manifest["collections"].values()),
    }


def restore(database, source):
    if database.list_collection_names():
        raise ValueError("Restore refused: target database must be empty")
    with tarfile.open(source, "r:gz") as archive:
        manifest = json_util.loads(archive.extractfile("manifest.json").read())
        if manifest.get("format") != 1:
            raise ValueError("Unsupported backup format")
        # Validate every stream before changing the destination. Never extract paths.
        for name, metadata in manifest["collections"].items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ValueError("Invalid backup collection name")
            member = name + ".bson"
            if checksum(archive.extractfile(member)) != metadata["sha256"]:
                raise ValueError("Backup checksum does not match")
            if sum(1 for _ in decode_file_iter(archive.extractfile(member))) != metadata["count"]:
                raise ValueError("Backup record count does not match")
        for name, metadata in manifest["collections"].items():
            collection = database.create_collection(name, **metadata["options"])
            batch = []
            for document in decode_file_iter(archive.extractfile(name + ".bson")):
                batch.append(document)
                if len(batch) == 500:
                    collection.insert_many(batch)
                    batch = []
            if batch:
                collection.insert_many(batch)
            indexes = []
            for index in metadata["indexes"]:
                if index["name"] == "_id_":
                    continue
                options = {key: value for key, value in index.items() if key not in {"v", "key", "ns"}}
                indexes.append(IndexModel(list(index["key"].items()), **options))
            if indexes:
                collection.create_indexes(indexes)
            with tempfile.TemporaryFile() as restored:
                for document in collection.find({}).sort("_id", 1):
                    restored.write(BSON.encode(document))
                restored.seek(0)
                if checksum(restored) != metadata["sha256"]:
                    raise ValueError("Restored records do not match the backup")
    return {"status": "verified", "collections": len(manifest["collections"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path")
    args = parser.parse_args()
    if engine.dialect.name != "mongodb":
        raise SystemExit("DATABASE_URL must select MongoDB")
    result = (backup if args.action == "backup" else restore)(engine.database, args.path)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
