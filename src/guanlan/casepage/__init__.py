"""Portable, deterministic configuration for a single real case page."""
import copy
import math
import re


def block(block_id, kind, field=None):
    return {"id": block_id, "kind": kind, "field": field, "plane": "xz", "offset": 0.5,
            "camera": "plane" if kind == "slice" else "isometric", "palette": "viridis",
            "range": None}


def default_document(case_id):
    return {"schema_version": 2, "case_id": case_id,
            "blocks": [block("geometry", "geometry"), block("mesh", "mesh"),
                       block("velocity", "slice", "U")]}


def exact(value, names, context):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError(context + ": unexpected or missing properties")


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_document(document, fields=None):
    exact(document, "schema_version case_id blocks", "document")
    if type(document["schema_version"]) is not int or document["schema_version"] != 2:
        raise ValueError("case document requires schema_version 2")
    if not isinstance(document["case_id"], str) or not re.fullmatch(r"[a-z0-9-]{1,64}", document["case_id"]):
        raise ValueError("invalid case_id")
    blocks = document["blocks"]
    if not isinstance(blocks, list) or not 2 <= len(blocks) <= 8:
        raise ValueError("a page needs geometry, mesh, and at most six result blocks")
    seen = set()
    for index, item in enumerate(blocks):
        exact(item, "id kind field plane offset camera palette range", "block")
        identifier = item["id"]
        if not isinstance(identifier, str) or not re.fullmatch(r"[a-z0-9-]{1,40}", identifier) or identifier in seen:
            raise ValueError("block IDs must be unique simple identifiers")
        seen.add(identifier)
        expected = ("geometry", "mesh")[index] if index < 2 else "slice"
        if item["kind"] != expected:
            raise ValueError("first blocks must be geometry and mesh; remaining blocks must be slices")
        if item["plane"] not in ("xy", "xz", "yz") or item["camera"] not in ("plane", "isometric", "xy", "xz", "yz"):
            raise ValueError("unsupported plane or camera")
        if not finite(item["offset"]) or not 0.001 <= item["offset"] <= 0.999:
            raise ValueError("plane offset must be inside the domain, between 0.001 and 0.999")
        if item["palette"] not in ("viridis", "coolwarm"):
            raise ValueError("unsupported palette")
        if expected == "slice":
            if not isinstance(item["field"], str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", item["field"]):
                raise ValueError("slice needs a valid field name")
            if fields is not None and item["field"] not in fields:
                raise ValueError("field is not in the case catalog")
        elif item["field"] is not None:
            raise ValueError("geometry and mesh do not take a field")
        limits = item["range"]
        if limits is not None and (not isinstance(limits, list) or len(limits) != 2 or
                                   not all(finite(n) for n in limits) or limits[0] >= limits[1]):
            raise ValueError("range must be null (automatic) or two increasing finite values")
    return copy.deepcopy(document)
