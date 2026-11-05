"""InputLock state and Windows hooks. No input is logged or stored."""

import ctypes
import os
import threading
import time
from ctypes import wintypes

EMERGENCY_SHORTCUT = "ctrl+alt+f12"
MODIFIERS = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10}
KEY_ALIASES = {0xA0: 0x10, 0xA1: 0x10, 0xA2: 0x11, 0xA3: 0x11,
               0xA4: 0x12, 0xA5: 0x12}


def parse_shortcut(text):
    """Accept modifiers plus one ASCII letter, digit or F1–F12."""
    parts = [part.strip().lower() for part in text.split("+")]
    if len(parts) < 2 or len(set(parts)) != len(parts):
        raise ValueError("Use Ctrl, Alt ou Shift + uma letra, número ou F1–F12.")
    if any(part not in MODIFIERS for part in parts[:-1]):
        raise ValueError("Modificadores válidos: Ctrl, Alt e Shift.")
    key = parts[-1]
    if len(key) == 1 and key.isascii() and key.isalnum():
        code = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 12:
        code = 0x70 + int(key[1:]) - 1
    else:
        raise ValueError("Termine o atalho com uma letra, número ou F1–F12.")
    return frozenset([MODIFIERS[part] for part in parts[:-1]] + [code])


def normalize_shortcut(text):
    parse_shortcut(text)
    return "+".join(part.strip().lower() for part in text.split("+"))


class LockState:
    """Platform-independent state; listeners never touch Tk widgets."""

    def __init__(self):
        self._mutex = threading.RLock()
        self.keyboard_locked = False
        self.mouse_locked = False
        self.deadline = None
        self.shortcut = parse_shortcut("ctrl+q")
        self.emergency = parse_shortcut(EMERGENCY_SHORTCUT)
        self.pressed = set()
        self.physical_keys = set()
        self.swallowed = set()

    def lock(self, keyboard, mouse, shortcut="ctrl+q", seconds=0):
        keys = parse_shortcut(shortcut)
        with self._mutex:
            self.shortcut = keys
            self.pressed.clear()
            self.physical_keys.clear()
            self.keyboard_locked = bool(keyboard)
            self.mouse_locked = bool(mouse)
            self.deadline = time.monotonic() + seconds if seconds else None

    def unlock(self):
        with self._mutex:
            self.keyboard_locked = self.mouse_locked = False
            self.deadline = None
            self.pressed.clear()
            self.physical_keys.clear()

    def snapshot(self):
        with self._mutex:
            remaining = max(0, self.deadline - time.monotonic()) if self.deadline else None
            return self.keyboard_locked, self.mouse_locked, remaining

    def expire(self):
        with self._mutex:
            if self.deadline is not None and time.monotonic() >= self.deadline:
                self.unlock()

    def key_event(self, code, down):
        """Return True to suppress. Consume unlock key-up as well as key-down."""
        raw_code = code
        with self._mutex:
            active = self.keyboard_locked or self.mouse_locked
            if down:
                self.physical_keys.add(raw_code)
            else:
                self.physical_keys.discard(raw_code)
            self.pressed = {KEY_ALIASES.get(key, key) for key in self.physical_keys}
            suppress = self.keyboard_locked or raw_code in self.swallowed
            if active and down and (
                self.shortcut <= self.pressed or self.emergency <= self.pressed
            ):
                suppress = True
                self.unlock()
            if suppress and down:
                self.swallowed.add(raw_code)
            elif not down:
                self.swallowed.discard(raw_code)
            return suppress


class WindowsInputLock(LockState):
    def __init__(self):
        super().__init__()
        if os.name != "nt":
            raise OSError("O bloqueio de entrada está disponível apenas no Windows.")
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._error = None
        self._thread_id = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="InputLock hooks")
        self._thread.start()
        if not self._ready.wait(5):
            self._stop.set()
            raise OSError("O Windows não respondeu ao iniciar o bloqueio.")
        if self._error:
            raise OSError(f"Não foi possível iniciar o bloqueio: {self._error}")
        self._timer = threading.Thread(target=self._watch, daemon=True, name="InputLock timer")
        self._timer.start()

    def _watch(self):
        while not self._stop.wait(0.1):
            self.expire()

    def lock(self, *args, **kwargs):
        if self._error or not self._thread.is_alive():
            raise OSError("Bloqueio indisponível. Reinicie o InputLock.")
        super().lock(*args, **kwargs)

    def _run(self):
        keyboard_hook = mouse_hook = None
        user = None
        try:
            user = ctypes.WinDLL("user32", use_last_error=True)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            result_type = ctypes.c_ssize_t
            callback_type = ctypes.WINFUNCTYPE(result_type, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
            user.SetWindowsHookExW.argtypes = [ctypes.c_int, callback_type, wintypes.HINSTANCE, wintypes.DWORD]
            user.SetWindowsHookExW.restype = wintypes.HANDLE
            user.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
            user.CallNextHookEx.restype = result_type
            user.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
            user.UnhookWindowsHookEx.restype = wintypes.BOOL
            user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user.GetMessageW.restype = wintypes.BOOL
            user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
            kernel.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel.GetModuleHandleW.restype = wintypes.HMODULE

            @callback_type
            def keyboard_callback(code, message, data):
                if code >= 0 and message in (0x100, 0x101, 0x104, 0x105):
                    try:
                        virtual_key = ctypes.cast(data, ctypes.POINTER(wintypes.DWORD)).contents.value
                        if self.key_event(virtual_key, message in (0x100, 0x104)):
                            return 1
                    except Exception:
                        self.unlock()
                return user.CallNextHookEx(None, code, message, data)

            @callback_type
            def mouse_callback(code, message, data):
                if code >= 0 and self.mouse_locked:
                    return 1
                return user.CallNextHookEx(None, code, message, data)

            self._thread_id = kernel.GetCurrentThreadId()
            message = wintypes.MSG()
            user.PeekMessageW(ctypes.byref(message), None, 0, 0, 0)
            module = kernel.GetModuleHandleW(None)
            keyboard_hook = user.SetWindowsHookExW(13, keyboard_callback, module, 0)
            if not keyboard_hook:
                raise ctypes.WinError(ctypes.get_last_error())
            mouse_hook = user.SetWindowsHookExW(14, mouse_callback, module, 0)
            if not mouse_hook:
                raise ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            while not self._stop.is_set():
                result = user.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result == -1:
                    raise ctypes.WinError(ctypes.get_last_error())
                if result == 0:
                    break
                user.TranslateMessage(ctypes.byref(message))
                user.DispatchMessageW(ctypes.byref(message))
        except Exception as error:
            self._error = error
        finally:
            self.unlock()
            for hook in (mouse_hook, keyboard_hook):
                if hook:
                    user.UnhookWindowsHookEx(hook)
            self._ready.set()

    def close(self):
        self.unlock()
        self._stop.set()
        if self._thread_id and self._thread.is_alive():
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            user.PostThreadMessageW(self._thread_id, 0x12, 0, 0)
            self._thread.join(timeout=2)
