"""Compile the application's SQLAlchemy query expressions to native MongoDB pipelines.

SQLAlchemy supplies model metadata and expressions only. No SQL engine, embedded
SQL database, or collection-wide Python evaluator is used for MongoDB requests.
Unsupported expressions fail explicitly instead of returning approximate results.
"""

import re
from datetime import UTC, datetime

from sqlalchemy import inspect
from sqlalchemy.sql import operators
from sqlalchemy.sql.elements import (
    BindParameter,
    BooleanClauseList,
    False_,
    Grouping,
    Null,
    True_,
    UnaryExpression,
)
from sqlalchemy.sql.functions import Function
from sqlalchemy.sql.selectable import Join, ScalarSelect, Subquery


def literal(value):
    return {"$literal": value}


def canonical(value):
    if isinstance(value, datetime):
        value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return value.isoformat(timespec="microseconds")
    if isinstance(value, dict):
        return {key: canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [canonical(item) for item in value]
    return value


class QueryPlan:
    def __init__(self, statement):
        self.statement = statement
        self.pipeline = []
        self.paths = {}
        self.descriptions = statement.column_descriptions
        self.count = (
            len(self.descriptions) == 1
            and isinstance(self.descriptions[0]["expr"], Function)
            and self.descriptions[0]["expr"].name == "count"
        )
        sources = statement.get_final_froms()
        if len(sources) != 1:
            raise NotImplementedError("MongoDB queries require one explicit root collection")
        source = sources[0]
        if isinstance(source, Subquery):
            if not self.count:
                raise NotImplementedError("Only count subqueries are used by this application")
            inner = QueryPlan(source.element)
            self.collection, self.paths = inner.collection, inner.paths
            self.pipeline.extend(inner.pipeline)
        else:
            self.collection = self._source(source)
        for criterion in statement._where_criteria:
            expression = self.expression(criterion)
            self.pipeline.append({"$match": {"$expr": expression}})
        if statement._group_by_clauses or statement._having_criteria or statement._distinct:
            raise NotImplementedError("Unsupported MongoDB grouping or distinct query")
        if self.count:
            self.pipeline.append({"$count": "__count"})
        else:
            ordering = {}
            for column in statement._order_by_clauses:
                direction = 1
                if isinstance(column, UnaryExpression):
                    if column.modifier == operators.desc_op:
                        direction = -1
                    elif column.modifier != operators.asc_op:
                        raise NotImplementedError("Unsupported MongoDB sort modifier")
                    column = column.element
                ordering[self.field(column)] = direction
            if ordering:
                # Stable pagination when dates or display names are equal.
                ordering.setdefault("_id", 1)
                self.pipeline.append({"$sort": ordering})
        if statement._offset_clause is not None:
            amount = statement._offset_clause.value
            if amount:
                self.pipeline.append({"$skip": amount})
        if statement._limit_clause is not None:
            amount = statement._limit_clause.value
            if amount == 0:
                self.pipeline.append({"$match": {"$expr": False}})
            else:
                self.pipeline.append({"$limit": amount})

    def _source(self, source):
        if isinstance(source, Join):
            root = self._source(source.left)
            name = source.right.name
            if name in self.paths:
                raise NotImplementedError("Self joins need an explicit MongoDB alias")
            old_paths = self.paths.copy()
            # The join condition sees the parent document through a lookup variable.
            self.paths = {table: "$$parent." + prefix for table, prefix in old_paths.items()}
            self.paths[name] = "$"
            condition = self.expression(source.onclause)
            self.paths = old_paths
            self.pipeline.append(
                {
                    "$lookup": {
                        "from": name,
                        "let": {"parent": "$$ROOT"},
                        "pipeline": [{"$match": {"$expr": condition}}],
                        "as": name,
                    }
                }
            )
            self.pipeline.append(
                {"$unwind": {"path": "$" + name, "preserveNullAndEmptyArrays": source.isouter}}
            )
            self.paths[name] = name + "."
            return root
        name = source.name
        self.paths[name] = ""
        return name

    def field(self, column):
        if hasattr(column, "__clause_element__"):
            column = column.__clause_element__()
        if getattr(column, "table", None) is None:
            raise NotImplementedError(f"Unsupported MongoDB field: {type(column).__name__}")
        name = column.table.name
        if name not in self.paths:
            raise NotImplementedError("Uncorrelated collection in MongoDB expression")
        return self.paths[name] + column.name

    def expression(self, value):
        if hasattr(value, "__clause_element__"):
            value = value.__clause_element__()
        if isinstance(value, Grouping):
            return self.expression(value.element)
        if isinstance(value, BindParameter):
            return literal(canonical(value.value))
        if isinstance(value, (True_, False_)):
            return isinstance(value, True_)
        if isinstance(value, Null):
            return literal(None)
        if isinstance(value, BooleanClauseList):
            operator = "$and" if value.operator == operators.and_ else "$or"
            return {operator: [self.expression(item) for item in value.clauses]}
        if isinstance(value, UnaryExpression):
            if value.operator == operators.inv:
                return {"$not": [self.expression(value.element)]}
            if value.operator in (operators.is_true, operators.is_false):
                return {"$eq": [self.expression(value.element), value.operator == operators.is_true]}
            raise NotImplementedError("Unsupported MongoDB unary expression")
        if isinstance(value, Function):
            if value.name == "lower":
                field = self.expression(list(value.clauses)[0])
                return {"$cond": [{"$eq": [field, None]}, None, {"$toLower": field}]}
            raise NotImplementedError("Unsupported MongoDB function")
        if getattr(value, "table", None) is not None:
            path = self.field(value)
            return path if path.startswith("$") else "$" + path
        if hasattr(value, "left") and hasattr(value, "right"):
            op = value.operator
            left = self.expression(value.left)
            right_value = value.right
            if op == operators.json_getitem_op:
                key = right_value.value
                if isinstance(key, int):
                    return {"$arrayElemAt": [left, key]}
                return {"$getField": {"field": literal(key), "input": {"$ifNull": [left, {}]}}}
            if op in (operators.between_op, operators.not_between_op):
                lower, upper = [self.expression(item) for item in right_value.clauses]
                bounds = {"$and": [{"$gte": [left, lower]}, {"$lte": [left, upper]}]}
                return {
                    "$and": [
                        {"$ne": [left, None]},
                        {"$ne": [lower, None]},
                        {"$ne": [upper, None]},
                        {"$not": [bounds]} if op == operators.not_between_op else bounds,
                    ]
                }
            if op in (operators.in_op, operators.not_in_op):
                if isinstance(right_value, ScalarSelect):
                    nested = QueryPlan(right_value.element)
                    if len(nested.descriptions) != 1 or nested.count:
                        raise NotImplementedError("Membership subqueries must select one column")
                    selected = nested.expression(nested.descriptions[0]["expr"])
                    alias = "__membership_" + str(len(self.pipeline))
                    self.pipeline.append(
                        {
                            "$lookup": {
                                "from": nested.collection,
                                "let": {"candidate": left},
                                "pipeline": [
                                    *nested.pipeline,
                                    {"$match": {"$expr": {"$eq": [selected, "$$candidate"]}}},
                                    {"$limit": 1},
                                    {"$project": {"_id": 1}},
                                ],
                                "as": alias,
                            }
                        }
                    )
                    result = {"$gt": [{"$size": "$" + alias}, 0]}
                    return {"$not": [result]} if op == operators.not_in_op else result
                result = {"$in": [left, self.expression(right_value)]}
                return (
                    {"$and": [{"$ne": [left, None]}, {"$not": [result]}]}
                    if op == operators.not_in_op
                    else result
                )
            if op in (operators.like_op, operators.ilike_op, operators.not_like_op, operators.not_ilike_op):
                pattern = right_value.value
                # SQL wildcards, with backslash escaping, without regex injection.
                parts = []
                escaped = False
                for char in pattern:
                    if escaped:
                        parts.append(re.escape(char))
                        escaped = False
                    elif char == "\\":
                        escaped = True
                    else:
                        parts.append(".*" if char == "%" else "." if char == "_" else re.escape(char))
                if escaped:
                    parts.append(re.escape("\\"))
                result = {
                    "$regexMatch": {
                        "input": {"$ifNull": [left, ""]},
                        "regex": "^" + "".join(parts) + "$",
                        "options": "i" if op in (operators.ilike_op, operators.not_ilike_op) else "",
                    }
                }
                if op in (operators.not_like_op, operators.not_ilike_op):
                    result = {"$not": [result]}
                return {"$and": [{"$ne": [left, None]}, result]}
            right = self.expression(right_value)
            mapping = {
                operators.eq: "$eq",
                operators.ne: "$ne",
                operators.gt: "$gt",
                operators.ge: "$gte",
                operators.lt: "$lt",
                operators.le: "$lte",
                operators.is_: "$eq",
                operators.is_not: "$ne",
                operators.add: "$add",
                operators.sub: "$subtract",
            }
            if op not in mapping:
                raise NotImplementedError(f"Unsupported MongoDB operator: {op.__name__}")
            result = {mapping[op]: [left, right]}
            if op in (operators.eq, operators.ne, operators.gt, operators.ge, operators.lt, operators.le):
                # MongoDB has a total BSON type ordering; SQL comparisons with NULL
                # are unknown. Explicit guards retain the application's semantics.
                return {"$and": [{"$ne": [left, None]}, {"$ne": [right, None]}, result]}
            return result
        if isinstance(value, (str, int, float, bool, datetime, list, dict)) or value is None:
            return literal(canonical(value))
        raise NotImplementedError(f"Unsupported MongoDB expression: {type(value).__name__}")

    def projected(self):
        if self.count:
            return self.pipeline
        projection = {"_id": 0}
        for index, item in enumerate(self.descriptions):
            expr = item["expr"]
            mapper = inspect(expr, raiseerr=False)
            if mapper is not None and getattr(mapper, "is_mapper", False):
                prefix = self.paths[mapper.local_table.name]
                projection[f"__{index}"] = {
                    column.name: "$" + prefix + column.name for column in mapper.columns
                }
                projection[f"__{index}"].update({"_id": "$" + prefix + "_id", "_rev": "$" + prefix + "_rev"})
            else:
                projection[f"__{index}"] = self.expression(expr)
        return [*self.pipeline, {"$project": projection}]
