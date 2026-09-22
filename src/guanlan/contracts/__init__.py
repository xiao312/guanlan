"""Strict validation for version 1's deliberately small fixture contract."""

import hashlib
import json
import math
import re


def keys(value, expected, location):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"{location}: expected exactly {', '.join(expected)}")


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def vector(value):
    return isinstance(value, list) and len(value) == 3 and all(map(number, value))


def validate_recipe(recipe):
    keys(recipe, ("schema_version", "id", "case_id", "panels", "plane", "camera",
                  "refresh", "limits"), "recipe")
    if type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise ValueError("schema_version must be integer 1")
    for name in ("id", "case_id"):
        if not isinstance(recipe[name], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", recipe[name]):
            raise ValueError(f"{name}: use 1–64 lowercase letters, digits or hyphens")
    if recipe["case_id"] != "synthetic-jet":
        raise ValueError("fixture renderer supports only case_id synthetic-jet")
    panels = recipe["panels"]
    if not isinstance(panels, list) or not 1 <= len(panels) <= 2:
        raise ValueError("panels must contain one or two panels")
    catalog = {"U": ("magnitude", "m/s"), "p": ("scalar", "Pa")}
    for panel in panels:
        keys(panel, ("field", "operation", "association", "units", "color_range"), "panel")
        field = panel["field"]
        if not isinstance(field, str) or field not in catalog:
            raise ValueError("fixture field must be U or p")
        if (panel["operation"], panel["units"]) != catalog[field] or panel["association"] != "point":
            raise ValueError(f"{field}: incompatible operation, units, or association")
        bounds = panel["color_range"]
        if (not isinstance(bounds, list) or len(bounds) != 2 or
                not all(map(number, bounds)) or bounds[0] >= bounds[1]):
            raise ValueError("color_range must contain two increasing finite numbers")
    keys(recipe["plane"], ("origin", "normal"), "plane")
    keys(recipe["camera"], ("position", "target", "up"), "camera")
    for section in ("plane", "camera"):
        if not all(vector(value) for value in recipe[section].values()):
            raise ValueError(f"{section}: expected finite three-dimensional vectors")
    if recipe["plane"] != {"origin": [0, 0, 0], "normal": [0, 0, 1]}:
        raise ValueError("fixture supports only its declared center plane")
    if recipe["camera"] != {"position": [0, 0, 1], "target": [0, 0, 0], "up": [0, 1, 0]}:
        raise ValueError("fixture supports only its declared orthographic camera")
    keys(recipe["refresh"], ("policy", "interval_seconds"), "refresh")
    interval = recipe["refresh"]["interval_seconds"]
    if recipe["refresh"]["policy"] != "latest" or not number(interval) or not 1 <= interval <= 60:
        raise ValueError("refresh requires latest policy and interval_seconds between 1 and 60")
    keys(recipe["limits"], ("max_preview_bytes",), "limits")
    budget = recipe["limits"]["max_preview_bytes"]
    if type(budget) is not int or not 16384 <= budget <= 1048576:
        raise ValueError("max_preview_bytes must be an integer between 16384 and 1048576")
    return recipe


def digest(recipe):
    encoded = json.dumps(recipe, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()
