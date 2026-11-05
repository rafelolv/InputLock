import json
from pathlib import Path
import tempfile
import unittest

from settings import DEFAULTS, load_config, save_config


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "InputLock" / "settings.json"

    def test_first_run_returns_defaults_without_writing(self):
        self.assertEqual(load_config(self.path), DEFAULTS)
        self.assertFalse(self.path.exists())

    def test_preferences_round_trip(self):
        expected = {"shortcut": "alt+2", "duration": 300, "delay": 5}
        save_config(expected, self.path)
        self.assertEqual(load_config(self.path), expected)
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_corrupted_file_falls_back(self):
        self.path.parent.mkdir(parents=True)
        for content in ("broken", "[]", "null", '{"shortcut":null}', '{"shortcut":"q"}'):
            self.path.write_text(content)
            self.assertEqual(load_config(self.path), DEFAULTS)

    def test_invalid_types_do_not_enter_config(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps({"duration": True, "delay": "5"}))
        self.assertEqual(load_config(self.path), DEFAULTS)

    def test_invalid_save_preserves_existing_preferences(self):
        save_config(DEFAULTS, self.path)
        for changes in ({"shortcut": "q"}, {"delay": 99}, {"duration": -1}):
            with self.assertRaises(ValueError):
                save_config({**DEFAULTS, **changes}, self.path)
            self.assertEqual(load_config(self.path), DEFAULTS)


if __name__ == "__main__":
    unittest.main()
