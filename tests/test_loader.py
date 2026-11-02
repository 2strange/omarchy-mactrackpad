"""reset removes the loader block from input.lua, also one written under the old plugin id."""
import importlib.util
import pathlib
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("trackpad_config", HERE.parent / "trackpad-config.py")
tc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tc)


class Loader(unittest.TestCase):
    def test_current_block(self):
        self.assertEqual(tc.without_loader("a\n" + tc.LOADER + "b\n"), "a\nb\n")

    def test_block_from_before_the_rename(self):
        old = tc.LOADER.replace(tc.PLUGIN_ID, "io.github.2strange.trackpad")
        self.assertEqual(tc.without_loader("a\n" + old + "b\n"), "a\nb\n")

    def test_missing_end_marker_is_left_alone(self):
        text = "a\n" + tc.MARK_BEGIN + "\nb\n"
        self.assertEqual(tc.without_loader(text), text)


if __name__ == "__main__":
    unittest.main()
