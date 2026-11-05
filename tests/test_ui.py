"""Exercise the same one-click controls users see; never suppress real input."""
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
except ImportError:
    tk = None


@unittest.skipIf(tk is None, "Tkinter is not installed")
class InterfaceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Display unavailable: {error}")
        self.addCleanup(self.cleanup)
        import main
        self.preferences = patch("main.load_config", return_value={"shortcut": "ctrl+q"})
        self.preferences.start()
        self.addCleanup(self.preferences.stop)
        saving = patch("main.save_config")
        self.saving = saving.start()
        self.addCleanup(saving.stop)
        self.app = main.InputLockApp(self.root, preview=True)
        self.root.update()

    def cleanup(self):
        if hasattr(self, "app"):
            self.app.close()
        else:
            self.root.destroy()

    def test_keyboard_button_locks_and_unlocks_immediately(self):
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (True, False))
        self.assertEqual(self.app.keyboard_status.cget("text"), "●  Teclado bloqueado")
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, False))

    def test_mouse_button_locks_only_mouse(self):
        self.app.mouse_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, True))
        self.app.backend.key_event(0xA3, True)
        self.app.backend.key_event(ord("Q"), True)
        self.app._refresh()
        self.assertEqual(self.app.backend.snapshot(), (False, False))
        self.assertEqual(self.app.mouse_status.cget("text"), "●  Mouse livre")

    def test_both_button_preserves_already_locked_keyboard(self):
        self.app.keyboard_button.invoke()
        self.app.both_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (True, True))
        self.assertEqual(self.app.both_button.cget("text"), "Desbloquear ambos")
        self.app.both_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, False))

    def test_devices_toggle_independently(self):
        self.app.both_button.invoke()
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, True))
        self.app.mouse_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, False))

    def test_shortcut_editing_disabled_only_while_locked(self):
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.shortcut_entry.cget("state"), "disabled")
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.shortcut_entry.cget("state"), "normal")

    def test_unlock_does_not_require_writable_preferences(self):
        self.app.keyboard_button.invoke()
        self.saving.side_effect = OSError("read-only")
        self.app.keyboard_button.invoke()
        self.assertEqual(self.app.backend.snapshot(), (False, False))
        self.assertEqual(self.saving.call_count, 1)

    def test_invalid_shortcut_never_locks(self):
        self.app.shortcut.set("q")
        with patch("main.messagebox.showerror") as error:
            self.app.mouse_button.invoke()
        error.assert_called_once()
        self.assertIsNone(self.app.backend)

    def test_about_displays_credits(self):
        self.app.about()
        self.root.update()
        windows = [child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)]
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].title(), "Sobre o InputLock")
        windows[0].destroy()


if __name__ == "__main__":
    unittest.main()
