"""Native MongoDB persistence for the application's mapped records.

Models and query expressions are shared with the legacy SQL importer; persistence
uses PyMongo transactions, indexes and aggregation, never a hidden SQL database.
"""

import time
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import certifi
from bson.codec_options import CodecOptions
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, OperationFailure, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, UniqueConstraint, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm.exc import StaleDataError
from sqlalchemy.sql.dml import Delete, Update
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.sql.selectable import Select

from .mongo_query import QueryPlan, canonical


def translated(error):
    if isinstance(error, DuplicateKeyError) or getattr(error, "code", None) == 121:
        return IntegrityError(None, None, ValueError("A database constraint was violated"))
    if isinstance(error, OperationFailure) and (
        error.has_error_label("TransientTransactionError") or error.code in (112, 251)
    ):
        return StaleDataError("The record changed concurrently. Refresh and try again.")
    return OperationalError(None, None, RuntimeError("MongoDB is unavailable"))


def registry():
    from . import models  # noqa: F401
    from .db import Base

    return {mapper.local_table.name: mapper for mapper in Base.registry.mappers}


def decoded(column, value):
    kind = column.type
    if value is not None and (
        isinstance(kind, DateTime) or isinstance(getattr(kind, "impl", None), DateTime)
    ):
        return datetime.fromisoformat(value) if isinstance(value, str) else value
    return deepcopy(value)


class MongoEngine:
    dialect = SimpleNamespace(name="mongodb")

    def __init__(self, url):
        self.client = MongoClient(
            url,
            appname="shiftproof",
            tlsCAFile=certifi.where() if url.startswith("mongodb+srv:") else None,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=10000,
            tz_aware=True,
            uuidRepresentation="standard",
        )
        self.database = self.client.get_default_database(
            codec_options=CodecOptions(tz_aware=True, tzinfo=UTC)
        )
        if self.database.name in {"admin", "config", "local"}:
            raise ValueError("Use a dedicated application database")

    def dispose(self):
        self.client.close()

    def ping(self):
        self.client.admin.command("ping")

    def bootstrap(self):
        existing = set(self.database.list_collection_names())
        for name, mapper in registry().items():
            properties = {"_id": {"bsonType": "string"}, "_rev": {"bsonType": ["int", "long"], "minimum": 1}}
            required = ["_id", "_rev"]
            for column in mapper.columns:
                kind = column.type
                if isinstance(kind, Boolean):
                    types = ["bool"]
                elif isinstance(kind, Integer):
                    types = ["int", "long"]
                elif isinstance(kind, Float):
                    types = ["double", "int", "long"]
                elif isinstance(kind, String):
                    types = ["string"]
                elif isinstance(kind, DateTime) or isinstance(getattr(kind, "impl", None), DateTime):
                    types = ["string"]
                elif isinstance(kind, JSON):
                    types = ["object", "array", "string", "bool", "int", "long", "double", "null"]
                else:
                    raise NotImplementedError(f"MongoDB schema type: {type(kind).__name__}")
                if column.nullable:
                    types = list(set(types + ["null"]))
                else:
                    required.append(column.name)
                properties[column.name] = {"bsonType": types}
            validator = {
                "$jsonSchema": {"bsonType": "object", "required": required, "properties": properties}
            }
            if name not in existing:
                self.database.create_collection(
                    name, validator=validator, validationLevel="strict", validationAction="error"
                )
            else:
                self.database.command(
                    "collMod", name, validator=validator, validationLevel="strict", validationAction="error"
                )
            table = mapper.local_table
            unique = {
                tuple(c.name for c in constraint.columns)
                for constraint in table.constraints
                if isinstance(constraint, UniqueConstraint)
            }
            unique |= {(c.name,) for c in table.columns if c.unique or c.primary_key}
            for columns in sorted(unique):
                options = {"name": "uq_" + "_".join(columns), "unique": True}
                # Match SQL uniqueness: null optional emails/employee IDs may repeat.
                nullable = [name for name in columns if table.c[name].nullable]
                if nullable:
                    options["partialFilterExpression"] = {
                        "$and": [{name: {"$type": "string"}} for name in nullable]
                    }
                self.database[name].create_index([(name, 1) for name in columns], **options)
            for column in table.columns:
                if column.index and (column.name,) not in unique:
                    self.database[name].create_index([(column.name, 1)], name="ix_" + column.name)
        self.database["_session_activity"].create_index(
            "expires_at", expireAfterSeconds=0, name="expire_session_activity"
        )
        self.database["background_jobs"].create_index(
            [("status", 1), ("available_at", 1)], name="ix_job_claim"
        )


class Result:
    def __init__(self, rows=(), rowcount=0):
        self.rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self.rows)

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar(self):
        row = self.first()
        return row[0] if row is not None else None

    def scalar_one(self):
        if len(self.rows) != 1:
            raise ValueError("Expected exactly one result")
        return self.rows[0][0]

    def scalars(self):
        return ScalarResult(row[0] for row in self.rows)


class ScalarResult(Result):
    def scalar(self):
        return self.first()

    def one(self):
        if len(self.rows) != 1:
            raise ValueError("Expected exactly one result")
        return self.rows[0]


class MongoSession:
    def __init__(self, engine):
        self.bind = engine
        self.database = engine.database
        self.client_session = engine.client.start_session()
        self.objects = {}
        self.originals = {}
        self.revisions = {}
        self.pending = {}
        self.deleted = set()
        self.touched = set()
        self.flushing = False
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def transaction(self):
        if not self.client_session.in_transaction:
            self.client_session.start_transaction(
                read_concern=ReadConcern("snapshot"), write_concern=WriteConcern("majority")
            )
        return self.client_session

    def call(self, fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except PyMongoError as error:
            raise translated(error) from None

    @staticmethod
    def key(record):
        mapper = inspect(type(record))
        return mapper.local_table.name, getattr(record, mapper.primary_key[0].name)

    @staticmethod
    def values(record):
        return {c.name: deepcopy(getattr(record, c.name)) for c in inspect(type(record)).columns}

    def add(self, record):
        mapper = inspect(type(record))
        for column in mapper.columns:
            if getattr(record, column.name) is None and column.default is not None:
                default = column.default.arg
                setattr(record, column.name, default(None) if callable(default) else deepcopy(default))
        key = self.key(record)
        if key[1] is None:
            raise ValueError("MongoDB records require a primary key")
        if key not in self.objects:
            self.objects[key] = record
            self.originals[key] = None
            self.pending[key] = record

    def add_all(self, records):
        for record in records:
            self.add(record)

    def hydrate(self, model, document):
        if document is None:
            return None
        mapper = inspect(model)
        key = (mapper.local_table.name, document[mapper.primary_key[0].name])
        if key in self.objects:
            return self.objects[key]
        record = model(
            **{column.name: decoded(column, document.get(column.name)) for column in mapper.columns}
        )
        if key[0] == "device_sessions":
            activity = self.call(self.database["_session_activity"].find_one, {"_id": key[1]})
            if activity and activity["last_seen"] > record.last_seen:
                record.last_seen = activity["last_seen"]
        self.objects[key] = record
        self.originals[key] = self.values(record)
        self.revisions[key] = document["_rev"]
        return record

    def get(self, model, identity):
        if identity is None:
            return None
        key = (inspect(model).local_table.name, identity)
        if key in self.deleted:
            return None
        if key in self.objects:
            return self.objects[key]
        self.flush()
        document = self.call(self.database[key[0]].find_one, {"_id": identity}, session=self.transaction())
        return self.hydrate(model, document)

    def refresh(self, record, attribute_names=None):
        key = self.key(record)
        document = self.call(self.database[key[0]].find_one, {"_id": key[1]}, session=self.transaction())
        if document is None:
            raise StaleDataError("The record was removed")
        names = attribute_names or [column.name for column in inspect(type(record)).columns]
        for name in names:
            setattr(record, name, decoded(inspect(type(record)).columns[name], document.get(name)))
        self.originals[key] = self.values(record)
        self.revisions[key] = document["_rev"]

    def delete(self, record):
        self.deleted.add(self.key(record))

    def _references(self, record, changed):
        mapper = inspect(type(record))
        for column in mapper.columns:
            if column.name not in changed or not column.foreign_keys:
                continue
            value = getattr(record, column.name)
            if value is None:
                continue
            for reference in column.foreign_keys:
                parent = reference.column.table.name
                key = (parent, value)
                if key in self.pending or key in self.touched:
                    continue
                # Touch parents in the same transaction so deleting a referenced
                # record cannot race a child insert under snapshot isolation.
                result = self.call(
                    self.database[parent].update_one,
                    {"_id": value},
                    {"$inc": {"_references": 1}},
                    session=self.transaction(),
                )
                if not result.matched_count:
                    raise IntegrityError(None, None, ValueError("A referenced record does not exist"))
                self.touched.add(key)

    def flush(self):
        if self.flushing:
            return
        self.flushing = True
        try:
            from .db import now
            from .models.immutability import IMMUTABLE_MODELS

            # Insert parents before children where possible. Cyclic references are
            # checked against the complete pending set in this atomic transaction.
            for key, record in list(self.pending.items()):
                values = self.values(record)
                self._references(record, values)
                self.call(
                    self.database[key[0]].insert_one,
                    canonical({"_id": key[1], "_rev": 1, **values}),
                    session=self.transaction(),
                )
                for name, value in values.items():
                    setattr(record, name, deepcopy(value))
                self.originals[key], self.revisions[key] = deepcopy(values), 1
            self.pending.clear()
            for key, record in list(self.objects.items()):
                if key in self.deleted:
                    if isinstance(record, IMMUTABLE_MODELS):
                        raise ValueError(
                            "Historical records are immutable. Append a new version or event instead."
                        )
                    for name, mapper in registry().items():
                        for column in mapper.columns:
                            if any(fk.column.table.name == key[0] for fk in column.foreign_keys):
                                found = self.call(
                                    self.database[name].find_one,
                                    {
                                        column.name: key[1],
                                        "_id": {
                                            "$nin": [
                                                identity for table, identity in self.deleted if table == name
                                            ]
                                        },
                                    },
                                    {"_id": 1},
                                    session=self.transaction(),
                                )
                                if found:
                                    raise IntegrityError(
                                        None, None, ValueError("The record is still referenced")
                                    )
                    result = self.call(
                        self.database[key[0]].delete_one,
                        {"_id": key[1], "_rev": self.revisions[key]},
                        session=self.transaction(),
                    )
                    if result.deleted_count != 1:
                        raise StaleDataError("The record changed concurrently")
                    continue
                before = self.originals[key]
                values = self.values(record)
                changes = {name: value for name, value in values.items() if value != before[name]}
                if not changes:
                    continue
                if isinstance(record, IMMUTABLE_MODELS):
                    raise ValueError(
                        "Historical records are immutable. Append a new version or event instead."
                    )
                mapper = inspect(type(record))
                if mapper.version_id_col is not None:
                    name = mapper.version_id_col.name
                    changes[name] = before[name] + 1
                if "updated_at" in values:
                    changes["updated_at"] = now()
                self._references(record, changes)
                result = self.call(
                    self.database[key[0]].update_one,
                    {"_id": key[1], "_rev": self.revisions[key]},
                    {"$set": canonical(changes), "$inc": {"_rev": 1}},
                    session=self.transaction(),
                )
                if result.matched_count != 1:
                    raise StaleDataError("The record changed concurrently")
                for name, value in changes.items():
                    setattr(record, name, deepcopy(value))
                self.originals[key] = self.values(record)
                self.revisions[key] += 1
            for key in self.deleted:
                self.objects.pop(key, None)
                self.originals.pop(key, None)
                self.revisions.pop(key, None)
            self.deleted.clear()
        finally:
            self.flushing = False

    def execute(self, statement):
        if isinstance(statement, TextClause):
            if statement.text.strip().upper() != "SELECT 1":
                raise NotImplementedError("Raw SQL is not available on MongoDB")
            self.call(self.bind.ping)
            return Result([(1,)])
        self.flush()
        if isinstance(statement, Select):
            plan = QueryPlan(statement)
            documents = self.call(
                lambda: list(
                    self.database[plan.collection].aggregate(plan.projected(), session=self.transaction())
                )
            )
            if plan.count:
                return Result([(documents[0]["__count"] if documents else 0,)])
            rows = []
            for document in documents:
                row = []
                for index, item in enumerate(plan.descriptions):
                    mapper = inspect(item["expr"], raiseerr=False)
                    value = document.get(f"__{index}")
                    row.append(
                        self.hydrate(mapper.class_, value)
                        if mapper is not None and getattr(mapper, "is_mapper", False)
                        else value
                    )
                rows.append(tuple(row))
            # MongoDB write intents take the place of SELECT FOR UPDATE locks.
            if statement._for_update_arg is not None:
                for row in rows:
                    for record in row:
                        if hasattr(record, "_sa_instance_state"):
                            name, identity = self.key(record)
                            self.call(
                                self.database[name].update_one,
                                {"_id": identity},
                                {"$inc": {"_lock": 1}},
                                session=self.transaction(),
                            )
            return Result(rows)
        if isinstance(statement, (Update, Delete)):
            mapper = registry()[statement.table.name]
            query = select(mapper.class_).where(*statement._where_criteria)
            records = list(self.scalars(query))
            if isinstance(statement, Delete):
                for record in records:
                    self.delete(record)
            else:
                plan = QueryPlan(query)
                for record in records:
                    document = self.values(record)
                    values = {}
                    # Updates are evaluated by MongoDB, including arithmetic and
                    # conditional predicates, in the current atomic transaction.
                    for name, expression in statement._values.items():
                        name = name if isinstance(name, str) else name.name
                        values[name] = plan.expression(expression)
                    from .models.immutability import IMMUTABLE_MODELS

                    if isinstance(record, IMMUTABLE_MODELS):
                        raise ValueError("Historical records are immutable")
                    key = self.key(record)
                    updated = self.call(
                        self.database[key[0]].find_one_and_update,
                        {"_id": key[1], "_rev": self.revisions[key]},
                        [{"$set": {**values, "_rev": {"$add": ["$_rev", 1]}}}],
                        return_document=ReturnDocument.AFTER,
                        session=self.transaction(),
                    )
                    if updated is None:
                        raise StaleDataError("The record changed concurrently")
                    for column in mapper.columns:
                        setattr(record, column.name, decoded(column, updated[column.name]))
                    self.originals[key] = self.values(record)
                    self.revisions[key] = updated["_rev"]
                    self._references(record, values)
            self.flush()
            return Result(rowcount=len(records))
        raise NotImplementedError(f"Unsupported MongoDB operation: {type(statement).__name__}")

    def scalar(self, statement):
        return self.execute(statement).scalar()

    def scalars(self, statement):
        return self.execute(statement).scalars()

    def commit(self):
        self.flush()
        if self.client_session.in_transaction:
            deadline = time.monotonic() + 15
            while True:
                try:
                    self.client_session.commit_transaction()
                    break
                except PyMongoError as error:
                    if (
                        error.has_error_label("UnknownTransactionCommitResult")
                        and time.monotonic() < deadline
                    ):
                        continue
                    raise translated(error) from None
        self.touched.clear()

    def rollback(self):
        if self.client_session.in_transaction:
            self.client_session.abort_transaction()
        for key, record in list(self.objects.items()):
            before = self.originals.get(key)
            if before is None:
                self.objects.pop(key, None)
            else:
                for name, value in before.items():
                    setattr(record, name, deepcopy(value))
        self.pending.clear()
        self.deleted.clear()
        self.touched.clear()
        # Previously flushed changes were also rolled back. Refresh loaded rows
        # lazily in the next transaction instead of retaining a speculative view.
        for key, record in list(self.objects.items()):
            document = self.database[key[0]].find_one({"_id": key[1]})
            if document is None:
                self.objects.pop(key, None)
                self.originals.pop(key, None)
                self.revisions.pop(key, None)
            else:
                for column in inspect(type(record)).columns:
                    setattr(record, column.name, decoded(column, document[column.name]))
                self.originals[key] = self.values(record)
                self.revisions[key] = document["_rev"]

    @contextmanager
    def independent(self):
        """Explicit transaction boundary for one idempotent scheduled task.

        MongoDB does not have SQL savepoints. A recurring task and its next-run
        timestamp are committed together; earlier scheduler work stays committed.
        """
        self.commit()
        try:
            yield self
            self.commit()
        except Exception:
            self.rollback()
            raise

    def touch_session(self, record, timestamp):
        key = self.key(record)
        # Activity is independent from authorization state: concurrent browser
        # reads must not conflict with revoking or changing the session itself.
        self.call(
            self.database["_session_activity"].update_one,
            {"_id": key[1]},
            {"$max": {"last_seen": timestamp}, "$set": {"expires_at": record.expires_at}},
            upsert=True,
        )
        record.last_seen = timestamp
        self.originals[key]["last_seen"] = record.last_seen

    def throttle(self, key, limit):
        self.commit()
        timestamp = datetime.now(UTC)
        collection = self.database["auth_throttles"]
        try:
            value = collection.find_one_and_update(
                {
                    "_id": key,
                    "$or": [
                        {"reset_at": {"$lte": canonical(timestamp)}},
                        {"attempts": {"$lt": limit}},
                        {"attempts": {"$exists": False}},
                    ],
                },
                canonical(
                    [
                        {
                            "$set": {
                                "key": key,
                                "_rev": {"$add": [{"$ifNull": ["$_rev", 0]}, 1]},
                                "attempts": {
                                    "$cond": [
                                        {"$lte": [{"$ifNull": ["$reset_at", timestamp]}, timestamp]},
                                        1,
                                        {"$add": ["$attempts", 1]},
                                    ]
                                },
                                "reset_at": {
                                    "$cond": [
                                        {"$lte": [{"$ifNull": ["$reset_at", timestamp]}, timestamp]},
                                        timestamp + timedelta(minutes=15),
                                        "$reset_at",
                                    ]
                                },
                            }
                        }
                    ]
                ),
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            return value["attempts"]
        except DuplicateKeyError:
            return None
        except PyMongoError as error:
            raise translated(error) from None

    def close(self):
        if not self.closed:
            if self.client_session.in_transaction:
                self.client_session.abort_transaction()
            self.client_session.end_session()
            self.closed = True


class MongoSessionFactory:
    def __init__(self, engine):
        self.engine = engine

    def __call__(self):
        return MongoSession(self.engine)

    @contextmanager
    def begin(self):
        with self() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
