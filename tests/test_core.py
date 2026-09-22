import copy
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from guanlan.contracts import digest, validate_recipe
from guanlan.preview import render
from guanlan.scheduling import LatestFirst

PROJECT = Path(__file__).resolve().parents[1]


def example(name="velocity"):
    return json.loads((PROJECT / "examples" / "recipes" / f"{name}.json").read_text())


class ContractTests(unittest.TestCase):
    def test_examples_render_within_budget(self):
        for name in ("velocity", "pressure", "compare"):
            recipe = validate_recipe(example(name))
            self.assertLessEqual(len(render(recipe, 2)), recipe["limits"]["max_preview_bytes"])

    def test_rejects_invalid_semantics(self):
        for key, value in (("field", "temperature"), ("units", "bar"),
                           ("association", "cell"), ("operation", "scalar"),
                           ("color_range", [0, float("nan")]), ("color_range", [1, 0])):
            recipe = example()
            recipe["panels"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_recipe(recipe)

    def test_rejects_unknown_keys_and_unsupported_camera(self):
        recipe = example()
        recipe["assessment"] = True
        with self.assertRaises(ValueError):
            validate_recipe(recipe)
        recipe = example()
        recipe["camera"]["position"] = [1, 0, 1]
        with self.assertRaises(ValueError):
            validate_recipe(recipe)

    def test_snapshot_freezes_full_recipe(self):
        recipe = example()
        payload = render(recipe, 42)
        root = ET.fromstring(payload)
        metadata = json.loads(root.find("{http://www.w3.org/2000/svg}metadata").text)
        self.assertEqual(metadata["recipe"], recipe)
        self.assertEqual(metadata["frame_id"], 42)
        self.assertEqual(payload, render(recipe, 42))
        self.assertNotEqual(payload, render(recipe, 43))

    def test_color_range_changes_render_and_digest(self):
        first = example()
        second = copy.deepcopy(first)
        second["panels"][0]["color_range"] = [0, 200]
        self.assertNotEqual(digest(first), digest(second))
        self.assertNotEqual(render(first, 1), render(second, 1))

    def test_payload_limit_is_enforced(self):
        recipe = example("compare")
        recipe["limits"]["max_preview_bytes"] = 16384
        with self.assertRaisesRegex(ValueError, "exceeds"):
            render(recipe, 0)


class SchedulingTests(unittest.TestCase):
    def test_latest_pending_replaces_obsolete_without_cancelling_active(self):
        queue = LatestFirst()
        queue.submit("A")
        self.assertEqual(queue.start(), "A")
        queue.submit("B")
        queue.submit("C")
        self.assertEqual(queue.active, "A")
        with self.assertRaises(RuntimeError):
            queue.start()
        self.assertEqual(queue.finish(), "A")
        self.assertEqual(queue.start(), "C")
        queue.finish()
        self.assertIsNone(queue.start())

    def test_burst_keeps_only_newest_request(self):
        queue = LatestFirst()
        for frame in range(10000):
            queue.submit(frame)
        self.assertEqual(queue.start(), 9999)


if __name__ == "__main__":
    unittest.main()
