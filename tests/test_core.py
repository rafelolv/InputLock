import os
import unittest

from core import LockState, WindowsInputLock, normalize_shortcut, parse_shortcut


class ShortcutTests(unittest.TestCase):
    def test_normalizes_whitespace_and_case(self):
        self.assertEqual(normalize_shortcut(" Ctrl + Shift + F8 "), "ctrl+shift+f8")
        self.assertEqual(parse_shortcut("alt+1"), frozenset((0x12, 0x31)))

    def test_rejects_unusable_shortcuts(self):
        for shortcut in ("", "q", "ctrl+", "ctrl+ctrl+q", "ctrl+alt", "ctrl+f13",
                         "ctrl+ç", "ctrl++", "win+q", "ctrl+space", "q+ctrl"):
            with self.subTest(shortcut=shortcut), self.assertRaises(ValueError):
                parse_shortcut(shortcut)


class LockTests(unittest.TestCase):
    def setUp(self):
        self.state = LockState()

    def press(self, *codes):
        return [self.state.key_event(code, True) for code in codes]

    def test_both_always_locks_both(self):
        self.state.lock(True, False)
        self.state.lock(True, True)
        self.assertEqual(self.state.snapshot()[:2], (True, True))

    def test_unlock_works_with_right_control(self):
        self.state.lock(True, True)
        self.assertEqual(self.press(0xA3, ord("Q")), [True, True])
        self.assertEqual(self.state.snapshot()[:2], (False, False))
        self.assertTrue(self.state.key_event(ord("Q"), False))
        self.assertTrue(self.state.key_event(0xA3, False))
        self.assertFalse(self.state.key_event(ord("A"), True))

    def test_mouse_only_unlock_with_control_and_digit(self):
        self.state.lock(False, True, "ctrl+1")
        self.assertFalse(self.state.key_event(0xA2, True))
        self.assertTrue(self.state.key_event(ord("1"), True))
        self.assertEqual(self.state.snapshot()[:2], (False, False))
        self.assertFalse(self.state.key_event(0xA2, False))

    def test_emergency_ignores_custom_shortcut(self):
        self.state.lock(True, True, "shift+f2")
        self.press(0xA3, 0xA5, 0x7B)
        self.assertEqual(self.state.snapshot()[:2], (False, False))

    def test_released_modifier_does_not_count(self):
        self.state.lock(True, True)
        self.press(0xA2)
        self.state.key_event(0xA2, False)
        self.press(ord("Q"))
        self.assertEqual(self.state.snapshot()[:2], (True, True))

    def test_two_sides_of_modifier(self):
        self.state.lock(True, True)
        self.press(0xA2, 0xA3)
        self.state.key_event(0xA2, False)
        self.press(ord("Q"))
        self.assertEqual(self.state.snapshot()[:2], (False, False))

    def test_changing_shortcut_between_sessions(self):
        self.state.lock(True, True, "ctrl+q")
        self.state.unlock()
        self.state.lock(True, True, "alt+2")
        self.press(0xA2, ord("Q"))
        self.assertTrue(self.state.keyboard_locked)
        self.press(0xA4, ord("2"))
        self.assertFalse(self.state.keyboard_locked)

    def test_invalid_shortcut_never_locks(self):
        with self.assertRaises(ValueError):
            self.state.lock(True, True, "bad")
        self.assertEqual(self.state.snapshot()[:2], (False, False))

    def test_keys_not_suppressed_while_idle(self):
        self.assertEqual(self.press(0xA2, ord("Q")), [False, False])

    @unittest.skipUnless(os.name == "nt", "Windows hooks require Windows")
    def test_windows_hooks_start_and_stop_without_locking_input(self):
        backend = WindowsInputLock()
        try:
            self.assertTrue(backend._thread.is_alive())
            self.assertEqual(backend.snapshot(), (False, False))
        finally:
            backend.close()
        self.assertFalse(backend._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
