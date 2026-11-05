"""InputLock: direct keyboard and mouse controls. --preview never blocks input."""

import ctypes
import os
import sys
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk
from PIL import Image

from core import LockState, WindowsInputLock, normalize_shortcut
from settings import load_config, save_config

VERSION = "1.0.7"
GITHUB = "https://github.com/rafelolv"
SOURCE = GITHUB + "/InputLock"
BG = "#211a2b"
CARD = "#30253d"
BORDER = "#806b8c"
TEXT = "#fff3e5"
MUTED = "#c8b2cf"
ACCENT = "#ff865e"
ACCENT_HOVER = "#ffa17f"
FREE = "#c6f178"
LOCKED = "#ff9f82"
FONT = "Segoe UI"


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / name


def ui_font(size=13, bold=False):
    return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")


class InputLockApp:
    def __init__(self, root, preview=False):
        global FONT
        self.root = root
        self.preview = preview
        self.backend = None
        self._render_state = None
        self.config = load_config()
        ctk.set_appearance_mode("dark")
        families = tkfont.families(root)
        FONT = next((name for name in ("Segoe UI", "Inter", "DejaVu Sans") if name in families), "Arial")
        root.title("InputLock · Prévia" if preview else "InputLock")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.report_callback_exception = self.callback_error
        self.window_icon = tk.PhotoImage(file=str(asset("icon.png")))
        root.iconphoto(True, self.window_icon)
        if os.name == "nt":
            root.iconbitmap(str(asset("icon.ico")))
        self.images = {}
        for name, size in (("icon", 24), ("keyboard", 20), ("mouse", 20),
                           ("keyboard_active", 20), ("mouse_active", 20)):
            with Image.open(asset(f"{name}.png")) as source:
                self.images[name] = ctk.CTkImage(light_image=source.copy(), size=(size, size))
        self._build()
        root.update_idletasks()
        root.geometry(f"{max(360, root.winfo_reqwidth())}x{root.winfo_reqheight()}")
        self.poll_job = root.after(100, self._poll)
        root.after_idle(self._style_titlebar)

    def _style_titlebar(self):
        if os.name != "nt":
            return
        try:
            user = ctypes.WinDLL("user32", use_last_error=True)
            user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user.GetAncestor.restype = wintypes.HWND
            handle = user.GetAncestor(self.root.winfo_id(), 2)
            dwm = ctypes.WinDLL("dwmapi")
            dwm.DwmSetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                ctypes.c_void_p, wintypes.DWORD]
            dwm.DwmSetWindowAttribute.restype = ctypes.c_long
            for attribute, color in ((20, None), (35, BG), (36, TEXT)):
                if color is None:
                    value = ctypes.c_uint(1)
                else:
                    red, green, blue = bytes.fromhex(color[1:])
                    value = ctypes.c_uint(red | (green << 8) | (blue << 16))
                # Older Windows versions may decline unsupported caption colors.
                dwm.DwmSetWindowAttribute(handle, attribute, ctypes.byref(value), ctypes.sizeof(value))
        except (OSError, AttributeError):
            pass

    def label(self, parent, text, size=12, color=TEXT, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color, height=20,
                            font=ui_font(size, bold), **kwargs)

    def _build(self):
        body = tk.Frame(self.root, bg=BG, padx=20, pady=16)
        body.pack(fill="both", expand=True)
        header = tk.Frame(body, bg=BG)
        header.pack(fill="x")
        self.label(header, "", image=self.images["icon"], width=24).pack(side="left", padx=(0, 8))
        self.label(header, "InputLock", 16, bold=True).pack(side="left")
        ctk.CTkButton(header, text="···", width=24, height=24, corner_radius=6,
                      font=ui_font(18, True), fg_color="transparent", hover_color="#453250",
                      text_color=MUTED, command=self.about).pack(side="right")

        status = tk.Frame(body, bg=BG)
        status.pack(fill="x", pady=(16, 14))
        self.keyboard_status = self.label(status, "●  Teclado livre", 11, FREE)
        self.keyboard_status.pack(side="left")
        self.mouse_status = self.label(status, "●  Mouse livre", 11, FREE)
        self.mouse_status.pack(side="right")

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(fill="x")
        buttons.columnconfigure((0, 1), weight=1, uniform="device")
        options = dict(height=48, corner_radius=8, border_width=1,
                       border_color=BORDER, fg_color=CARD, hover_color="#453250",
                       text_color=TEXT, font=ui_font(13))
        self.keyboard_button = ctk.CTkButton(buttons, text="Teclado", image=self.images["keyboard"],
                                             command=lambda: self.toggle_device("keyboard"), **options)
        self.keyboard_button.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.mouse_button = ctk.CTkButton(buttons, text="Mouse", image=self.images["mouse"],
                                          command=lambda: self.toggle_device("mouse"), **options)
        self.mouse_button.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        self.both_button = ctk.CTkButton(body, text="Bloquear ambos", command=self.toggle_both,
                                         height=40, corner_radius=8, fg_color=ACCENT,
                                         hover_color=ACCENT_HOVER, text_color=BG, font=ui_font(13))
        self.both_button.pack(fill="x", pady=(10, 0))

        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(18, 0))
        self.label(row, "Desbloquear", 12).pack(side="left")
        self.shortcut = tk.StringVar(value=self.config["shortcut"])
        self.shortcut_entry = ctk.CTkEntry(row, textvariable=self.shortcut, width=140, height=30,
                                          corner_radius=6, border_width=1, border_color=BORDER,
                                          fg_color=CARD, text_color=TEXT,
                                          font=ui_font(12), justify="center")
        self.shortcut_entry.pack(side="right")
        self.shortcut_entry.bind("<Return>", lambda event: self.save_preferences())
        self.hint = self.label(body, "Emergência: Ctrl + Alt + F12", 10, MUTED)
        self.hint.pack(pady=(8, 0))

        footer = tk.Frame(body, bg=BG)
        footer.pack(fill="x", pady=(16, 0))
        for title, url, side in (("made by rafaelolv", GITHUB, "left"), ("GitHub ↗", SOURCE, "right")):
            link = self.label(footer, title, 10, ACCENT, cursor="hand2")
            link.pack(side=side)
            link.bind("<Button-1>", lambda event, target=url: webbrowser.open(target))
            link.bind("<Enter>", lambda event, widget=link: widget.configure(text_color=ACCENT_HOVER))
            link.bind("<Leave>", lambda event, widget=link: widget.configure(text_color=ACCENT))
        if not self.preview and os.name != "nt":
            for button in (self.keyboard_button, self.mouse_button, self.both_button):
                button.configure(state="disabled")
            self.hint.configure(text="Bloqueio disponível no Windows")

    def save_preferences(self):
        try:
            config = {"shortcut": normalize_shortcut(self.shortcut.get())}
            save_config(config)
            self.config = config
            self.shortcut.set(config["shortcut"])
            return True
        except (ValueError, OSError) as error:
            messagebox.showerror("Confira o atalho", str(error), parent=self.root)
            return False

    def _state(self):
        return self.backend.snapshot() if self.backend else (False, False)

    def _apply(self, keyboard, mouse):
        # Unlocking must never depend on writing preferences or validating text.
        if not keyboard and not mouse:
            if self.backend:
                self.backend.unlock()
        else:
            if not any(self._state()) and not self.save_preferences():
                return
            try:
                if self.backend is None:
                    self.backend = LockState() if self.preview else WindowsInputLock()
                self.backend.lock(keyboard, mouse, self.config["shortcut"])
            except (OSError, ValueError) as error:
                messagebox.showerror("Não foi possível bloquear", str(error), parent=self.root)
                return
            self.root.focus_set()
        self._refresh()

    def toggle_device(self, device):
        keyboard, mouse = self._state()
        if device == "keyboard":
            self._apply(not keyboard, mouse)
        elif device == "mouse":
            self._apply(keyboard, not mouse)

    def toggle_both(self):
        keyboard, mouse = self._state()
        self._apply(not (keyboard and mouse), not (keyboard and mouse))

    def _refresh(self):
        state = self._state()
        if state == self._render_state:
            return
        self._render_state = state
        keyboard, mouse = state
        for locked, label, button, name, kind in (
            (keyboard, self.keyboard_status, self.keyboard_button, "Teclado", "keyboard"),
            (mouse, self.mouse_status, self.mouse_button, "Mouse", "mouse"),
        ):
            label.configure(text=f"●  {name} {'bloqueado' if locked else 'livre'}",
                            text_color=LOCKED if locked else FREE)
            button.configure(fg_color=FREE if locked else CARD,
                             border_color=FREE if locked else BORDER,
                             text_color=BG if locked else TEXT,
                             hover_color="#d7ff94" if locked else "#453250",
                             image=self.images[f"{kind}_active" if locked else kind])
        both_locked = keyboard and mouse
        self.both_button.configure(text="Desbloquear ambos" if both_locked else "Bloquear ambos",
                                   fg_color=FREE if both_locked else ACCENT,
                                   hover_color="#d7ff94" if both_locked else ACCENT_HOVER)
        self.shortcut_entry.configure(state="disabled" if keyboard or mouse else "normal")

    def _poll(self):
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
        self._refresh()
        self.poll_job = self.root.after(100, self._poll)

    def about(self):
        window = tk.Toplevel(self.root)
        window.title("Sobre o InputLock")
        window.configure(bg=BG, padx=24, pady=22)
        window.resizable(False, False)
        window.transient(self.root)
        self.label(window, f"InputLock {VERSION}", 21, bold=True).pack(anchor="w")
        self.label(window, "made by rafaelolv", 13, MUTED).pack(anchor="w", pady=(6, 16))
        self.label(window, "Bloqueio temporário de teclado e mouse.\n\nLicença MIT. Sem garantia.\nVocê pode modificar e redistribuir sob essa licença.\n\nBloqueia entradas na sessão atual do Windows.\nNão substitui o bloqueio de sessão (Win + L).\nCtrl + Alt + Del continua disponível.",
                   12, MUTED, justify="left").pack(anchor="w")
        for title, url in (("Código-fonte ↗", SOURCE),
                           ("Licença MIT ↗", SOURCE + "/blob/main/LICENSE")):
            link = self.label(window, title, 12, TEXT, cursor="hand2")
            link.pack(anchor="w", pady=(12, 0))
            link.bind("<Button-1>", lambda event, target=url: webbrowser.open(target))

    def callback_error(self, exception, value, traceback):
        if self.backend:
            self.backend.unlock()
        self._refresh()
        messagebox.showerror("InputLock", f"Dispositivos liberados.\n\n{value}", parent=self.root)

    def close(self):
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None
        if self.backend:
            self.backend.unlock()
            if hasattr(self.backend, "close"):
                self.backend.close()
        for job in self.root.tk.call("after", "info"):
            self.root.tk.call("after", "cancel", job)
        self.root.destroy()


def main():
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("rafaelolv.InputLock")
        except (OSError, AttributeError):
            pass
    root = tk.Tk()
    instance_handle = None
    if os.name == "nt" and "--smoke-test" not in sys.argv and "--preview" not in sys.argv:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        instance_handle = kernel.CreateMutexW(None, False, "Local\\rafaelolv.InputLock")
        if not instance_handle:
            root.destroy()
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            root.withdraw()
            messagebox.showinfo("InputLock", "O InputLock já está aberto. Confira a barra de tarefas.", parent=root)
            kernel.CloseHandle(instance_handle)
            root.destroy()
            return
    app = InputLockApp(root, preview="--preview" in sys.argv or "--smoke-test" in sys.argv)
    if "--smoke-test" in sys.argv:
        root.after(1200, app.close)
    try:
        root.mainloop()
    finally:
        if app.backend:
            app.backend.unlock()
            if hasattr(app.backend, "close"):
                app.backend.close()
        if instance_handle:
            kernel.CloseHandle(instance_handle)


if __name__ == "__main__":
    main()
