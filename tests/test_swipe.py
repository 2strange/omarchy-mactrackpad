"""Runs the generated workspace swipe Lua against a stubbed `hl` (needs a `lua` binary)."""
import importlib.util
import pathlib
import shutil
import subprocess
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("trackpad_config", HERE.parent / "trackpad-config.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)
LUA = shutil.which("lua") or shutil.which("luajit")

STUB = """
local focused = "none"
local gestures = {}
hl = {
  get_active_monitor = function() return { name = "A", active_workspace = { id = CUR } } end,
  get_workspaces = function() return WS end,
  dispatch = function(d) focused = d end,
  dsp = { focus = function(t) return t.workspace end },
  gesture = function(g) gestures[g.direction] = g.action end,
}
"""


def swipe(cur, open_here, direction, end="stop", empty=True, invert=False, other=()):
    ws = ", ".join([f'{{ id = {i}, monitor = {{ name = "A" }} }}' for i in open_here]
                   + [f'{{ id = {i}, monitor = {{ name = "B" }} }}' for i in other])
    s = {"swipe_fingers": 3, "swipe_end": end, "swipe_use_r": empty, "swipe_invert": invert}
    code = (STUB.replace("CUR", str(cur)).replace("WS", "{ " + ws + " }")
            + tc.gesture_lua(s) + f'\ngestures["{direction}"]()\nprint(focused)\n')
    return subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, check=True).stdout.strip()


@unittest.skipUnless(LUA, "no lua interpreter")
class SwipeTest(unittest.TestCase):
    def test_empty_workspaces_are_reached(self):
        self.assertEqual(swipe(4, [1, 2, 3, 4], "right"), "5")
        self.assertEqual(swipe(1, [1, 3], "right"), "2")

    def test_skip_empty_when_off(self):
        self.assertEqual(swipe(1, [1, 3], "right", empty=False), "3")
        self.assertEqual(swipe(3, [1, 3], "left", empty=False), "1")

    def test_stop_at_both_ends(self):
        self.assertEqual(swipe(5, [1, 5], "right"), "none")
        self.assertEqual(swipe(1, [1, 5], "left"), "none")
        self.assertEqual(swipe(3, [1, 3], "right", empty=False), "none")

    def test_stop_still_moves_inside(self):
        self.assertEqual(swipe(3, [1, 3], "left"), "2")

    def test_new_opens_after_the_last(self):
        self.assertEqual(swipe(5, [1, 5], "right", end="new"), "6")
        self.assertEqual(swipe(3, [1, 3], "right", end="new", empty=False), "4")
        self.assertEqual(swipe(10, [10], "right", end="new"), "none")
        self.assertEqual(swipe(1, [1], "left", end="new"), "none")

    def test_wrap(self):
        self.assertEqual(swipe(5, [1, 5], "right", end="wrap"), "1")
        self.assertEqual(swipe(1, [1, 2], "left", end="wrap"), "5")
        self.assertEqual(swipe(1, [1, 3], "left", end="wrap", empty=False), "3")

    def test_open_workspace_beyond_five_counts(self):
        self.assertEqual(swipe(5, [1, 7], "right"), "6")
        self.assertEqual(swipe(7, [1, 7], "right", end="wrap"), "1")

    def test_other_monitor_is_skipped(self):
        self.assertEqual(swipe(1, [1], "right", other=[2]), "3")
        self.assertEqual(swipe(5, [5], "right", end="new", other=[6]), "7")

    def test_invert_swaps_directions(self):
        self.assertEqual(swipe(2, [1, 2], "left", invert=True), "3")
        self.assertEqual(swipe(2, [1, 2], "right", invert=True), "1")

    def test_named_workspace_falls_back(self):
        self.assertEqual(swipe(-98, [1], "right"), "e+1")


if __name__ == "__main__":
    unittest.main()
