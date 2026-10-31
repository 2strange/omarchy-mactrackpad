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
  workspace_rule = function(r) end,
}
"""


def swipe(cur, open_here, direction, end="wrap", empty=True, invert=False, other=()):
    ws = ", ".join([f'{{ id = {i}, monitor = {{ name = "A" }} }}' for i in open_here]
                   + [f'{{ id = {i}, monitor = {{ name = "B" }} }}' for i in other])
    s = {"swipe_fingers": 3, "swipe_end": end, "swipe_use_r": empty, "swipe_invert": invert}
    code = (STUB.replace("CUR", str(cur)).replace("WS", "{ " + ws + " }")
            + tc.gesture_lua(s) + f'\ngestures["{direction}"]()\nprint(focused)\n')
    return subprocess.run([LUA, "-"], input=code, capture_output=True, text=True, check=True).stdout.strip()


@unittest.skipUnless(LUA, "no lua interpreter")
class SwipeTest(unittest.TestCase):
    def test_wrap_reaches_empty_workspaces(self):
        self.assertEqual(swipe(4, [1, 2, 3, 4], "right"), "5")
        self.assertEqual(swipe(1, [1, 3], "right"), "2")
        self.assertEqual(swipe(1, [1, 3], "right", empty=False), "3")

    def test_wrap_around(self):
        self.assertEqual(swipe(5, [1, 5], "right"), "1")
        self.assertEqual(swipe(1, [1, 2], "left"), "5")
        self.assertEqual(swipe(1, [1, 3], "left", empty=False), "3")
        self.assertEqual(swipe(7, [1, 7], "right"), "1")
        self.assertEqual(swipe(5, [1, 7], "right"), "7")  # same set as Stop / New one: 1-5 + open ones

    def test_other_monitor_is_skipped(self):
        self.assertEqual(swipe(1, [1], "right", other=[2]), "3")

    def test_hyprland_r_mode_stays_off(self):
        # with workspace_swipe_use_r, Hyprland's swipe does nothing on workspace 1 (both directions)
        self.assertIn("workspace_swipe_use_r = false", tc.render(dict(tc.effective(), swipe_use_r=True), None))

    def test_live_swipe_for_stop_and_new(self):
        for end in ("stop", "new"):
            lua = tc.gesture_lua({"swipe_fingers": 3, "swipe_end": end, "swipe_use_r": True, "swipe_invert": False})
            self.assertIn('direction = "horizontal", action = "workspace"', lua)
            self.assertEqual(lua.count("persistent = true"), 5)
        lua = tc.gesture_lua({"swipe_fingers": 3, "swipe_end": "stop", "swipe_use_r": False, "swipe_invert": False})
        self.assertNotIn("persistent", lua)

    def test_invert_swaps_directions(self):
        self.assertEqual(swipe(2, [1, 2], "left", invert=True), "3")
        self.assertEqual(swipe(2, [1, 2], "right", invert=True), "1")

    def test_named_workspace_falls_back(self):
        self.assertEqual(swipe(-98, [1], "right"), "e+1")


if __name__ == "__main__":
    unittest.main()
