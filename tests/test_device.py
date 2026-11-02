"""touchpad_device picks the built-in trackpad, never the MagicMouse plugin's virtual touchpads."""
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("trackpad_config", HERE.parent / "trackpad-config.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


def devices(*names):
    return json.dumps({"mice": [{"name": n} for n in names]})


class Device(unittest.TestCase):
    def test_virtual_touchpads_listed_first_are_skipped(self):
        with mock.patch.object(tc, "hyprctl", return_value=devices(
                "magic-mouse-virtual-touchpad", "magic-mouse-virtual-touchpad-1", "bcm5974")):
            self.assertEqual(tc.touchpad_device(), "bcm5974")

    def test_only_virtual_touchpads_means_none(self):
        with mock.patch.object(tc, "hyprctl", return_value=devices("magic-mouse-virtual-touchpad")):
            self.assertIsNone(tc.touchpad_device())


if __name__ == "__main__":
    unittest.main()
