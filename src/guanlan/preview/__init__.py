"""Deterministic SVG fixture, explicitly unrelated to measured CFD data."""

import html
import json
import math

from guanlan.contracts import digest, validate_recipe


def render(recipe, frame):
    validate_recipe(recipe)
    if type(frame) is not int or not 0 <= frame <= 1000000000:
        raise ValueError("frame must be an integer between 0 and 1000000000")
    width = 560 * len(recipe["panels"])
    metadata = {"recipe": recipe, "recipe_digest": digest(recipe), "frame_id": frame,
                "simulation_time": frame * 0.001, "simulation_time_units": "s",
                "source_kind": "synthetic"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 390">',
             f'<metadata>{html.escape(json.dumps(metadata))}</metadata>',
             '<rect width="100%" height="100%" fill="#101d29"/>',
             '<g font-family="sans-serif" fill="#e0ebf1">']
    for index, panel in enumerate(recipe["panels"]):
        x_offset = 560 * index
        title = "Velocity magnitude" if panel["field"] == "U" else "Pressure"
        parts.append(f'<text x="{x_offset + 24}" y="34" font-size="19">{title} · {panel["units"]}</text>')
        low, high = panel["color_range"]
        for row in range(20):
            for column in range(40):
                x, y = column / 39, (row - 9.5) / 9.5
                center = 0.18 * math.sin(x * 10 - frame * 0.18) * x
                jet = math.exp(-((y - center) / (0.12 + x * 0.42)) ** 2)
                value = 100 * jet * (1 - 0.4 * x)
                if panel["field"] == "p":
                    value = 50000 + 35000 * math.cos(x * 9 - frame * 0.12) * jet
                fraction = max(0, min(1, (value - low) / (high - low)))
                hue = 225 - 210 * fraction
                parts.append(f'<rect x="{x_offset + 24 + column * 12.8:.1f}" y="{60 + row * 12}" '
                             f'width="13" height="12.2" fill="hsl({hue:.1f},76%,55%)"/>')
        parts.append(f'<text x="{x_offset + 24}" y="328" font-size="13">'
                     f'Fixed range {low:g} – {high:g} {panel["units"]} · center plane</text>')
    parts.append(f'<text x="24" y="369" font-size="13">SYNTHETIC DEMO · '
                 f't = {frame * 0.001:.3f} s · {html.escape(recipe["case_id"])}</text></g></svg>')
    payload = "".join(parts).encode("utf-8")
    if len(payload) > recipe["limits"]["max_preview_bytes"]:
        raise ValueError("preview exceeds max_preview_bytes; increase budget or reduce panel count")
    return payload
