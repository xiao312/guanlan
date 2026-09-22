"""Local composition entry point; check is the non-mutating discovery path."""

import argparse
import json
from pathlib import Path

from guanlan.contracts import validate_recipe
from guanlan.delivery import create_server


def main():
    parser = argparse.ArgumentParser(description="Guanlan synthetic live-view scaffold")
    parser.add_argument("command", choices=("check", "demo"))
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if not 1 <= args.port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        recipes = {}
        for path in sorted(args.recipes.glob("*.json")):
            if path.stat().st_size > 65536:
                raise ValueError(f"recipe exceeds 64 KiB: {path}")
            recipe = validate_recipe(json.loads(path.read_text(encoding="utf-8")))
            if recipe["id"] in recipes:
                raise ValueError(f"duplicate recipe id: {recipe['id']}")
            recipes[recipe["id"]] = recipe
        if not recipes or len(recipes) > 20:
            raise ValueError("recipes directory must contain 1–20 valid JSON recipes")
        if args.command == "check":
            print(json.dumps({"valid": True, "views": list(recipes), "source_kind": "synthetic"}))
            return 0
        with create_server(recipes, args.port) as server:
            print(f"Synthetic demo: http://127.0.0.1:{args.port} (local only; Ctrl+C to stop)", flush=True)
            server.serve_forever()
    except (OSError, ValueError) as error:
        parser.exit(2, f"Guanlan: {error}\n")
    except KeyboardInterrupt:
        return 0
