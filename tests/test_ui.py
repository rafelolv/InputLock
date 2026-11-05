"""Exercise UI transitions in preview mode, without suppressing real input."""
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
        self.main = main
        self.preferences = patch("main.load_config", return_value={"shortcut": "ctrl+q", "duration": 60, "delay": 0})
        self.saving = patch("main.save_config")
        self.preferences.start()
        self.saving.start()
        self.addCleanup(self.preferences.stop)
        self.addCleanup(self.saving.stop)
        self.app = main.InputLockApp(self.root, preview=True)
        self.root.update()

    def cleanup(self):
        if hasattr(self, "app"):
            self.app.close()
        else:
            self.root.destroy()

    def test_lock_both_and_unlock_button(self):
        self.app.start()
        self.assertEqual(self.app.backend.snapshot()[:2], (True, True))
        self.app._poll()
        self.assertEqual(self.app.action.cget("text"), "Desbloquear agora")
        self.assertEqual(str(self.app.shortcut_entry.cget("state")), "disabled")
        self.app.start()
        self.assertEqual(self.app.backend.snapshot()[:2], (False, False))

    def test_cancel_countdown_never_locks(self):
        self.app.delay.set("3 segundos")
        self.app.start()
        self.assertIsNotNone(self.app.pending)
        self.app.cancel_countdown()
        self.assertIsNone(self.app.pending)
        self.assertFalse(any(self.app.backend.snapshot()[:2]))

    def test_keyboard_only_and_shortcut_unlock(self):
        self.app.toggle(self.app.mouse)
        self.app.start()
        self.assertEqual(self.app.backend.snapshot()[:2], (True, False))
        self.app.backend.key_event(0xA3, True)
        self.app.backend.key_event(ord("Q"), True)
        self.assertFalse(any(self.app.backend.snapshot()[:2]))

    def test_empty_selection_does_not_start_backend(self):
        self.app.toggle(self.app.mouse)
        self.app.toggle(self.app.keyboard)
        self.app.start()
        self.assertIsNone(self.app.backend)
        self.assertEqual(self.app.status.cget("text"), "Selecione teclado ou mouse")

    def test_selection_frozen_during_countdown(self):
        self.app.delay.set("3 segundos")
        self.app.start()
        self.app.toggle(self.app.mouse)
        self.assertTrue(self.app.mouse.selected)

    def test_about_displays_credits(self):
        self.app.about()
        self.root.update()
        windows = [child for child in self.root.winfo_children() if isinstance(child, tk.Toplevel)]
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].title(), "Sobre o InputLock")
        windows[0].destroy()


if __name__ == "__main__":
    unittest.main()
