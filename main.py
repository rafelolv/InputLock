"""InputLock desktop interface. --preview never blocks input."""

import ctypes
import math
import os
import sys
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

import customtkinter as ctk
from PIL import Image

from core import LockState, WindowsInputLock, normalize_shortcut
from settings import DURATIONS, load_config, save_config

VERSION = "1.0.1"
GITHUB = "https://github.com/rafelolv"
SOURCE = GITHUB + "/InputLock"
BG = "#f5f5f7"
CARD = "#ffffff"
BORDER = "#eceef1"
TEXT = "#20242b"
MUTED = "#747b85"
ACCENT = "#20242b"
FONT = "Segoe UI"


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / name


def ui_font(size=13, bold=False):
    return ctk.CTkFont(family=FONT, size=size, weight="bold" if bold else "normal")


class DeviceCard(tk.Frame):
    """One device row; the row and switch share the same selection state."""

    def __init__(self, parent, title, description, kind, command):
        super().__init__(parent, bg=CARD, height=68, takefocus=True, cursor="hand2")
        self.pack_propagate(False)
        self.selected = True
        self.command = command
        self.value = tk.BooleanVar(value=True)
        with Image.open(asset(f"{kind}.png")) as source:
            self.image = ctk.CTkImage(light_image=source.copy(), size=(22, 22))
        self.icon = ctk.CTkLabel(self, text="", image=self.image, width=40, height=40,
                                 corner_radius=10, fg_color=BG)
        self.icon.pack(side="left", padx=(0, 12))
        labels = tk.Frame(self, bg=CARD)
        labels.pack(side="left", fill="y", pady=13)
        title_label = ctk.CTkLabel(labels, text=title, text_color=TEXT, font=ui_font(14, True),
                                   height=20, anchor="w")
        title_label.pack(anchor="w")
        subtitle = ctk.CTkLabel(labels, text=description, text_color=MUTED,
                                font=ui_font(12), height=18, anchor="w")
        subtitle.pack(anchor="w")
        self.switch_images = {}
        for selected, name in ((True, "on"), (False, "off")):
            with Image.open(asset(f"switch_{name}.png")) as source:
                self.switch_images[selected] = ctk.CTkImage(light_image=source.copy(), size=(40, 24))
        self.switch = ctk.CTkButton(self, text="", image=self.switch_images[True],
                                    command=command, width=40, height=24,
                                    fg_color=CARD, hover=False, border_width=0,
                                    corner_radius=0)
        self.switch.pack(side="right")
        for widget in (self, labels, self.icon, title_label, subtitle):
            widget.bind("<Button-1>", lambda event: self.command())
        self.bind("<space>", lambda event: self.command())
        self.bind("<Return>", lambda event: self.command())
        self.bind("<FocusIn>", lambda event: self.icon.configure(fg_color="#e8ebef"))
        self.bind("<FocusOut>", lambda event: self.icon.configure(fg_color=BG))

    def set_selected(self, selected):
        self.selected = bool(selected)
        self.value.set(self.selected)
        self.switch.configure(image=self.switch_images[self.selected])

    def set_enabled(self, enabled):
        self.switch.configure(state="normal" if enabled else "disabled")


class InputLockApp:
    def __init__(self, root, preview=False):
        global FONT
        self.root = root
        self.preview = preview
        self.backend = None
        self.pending = None
        self.pending_end = None
        self._render_state = None
        self.config = load_config()
        ctk.set_appearance_mode("light")
        families = tkfont.families(root)
        FONT = next((name for name in ("Segoe UI", "Inter", "DejaVu Sans") if name in families), "Arial")
        root.title("InputLock")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda event: self.cancel_countdown())
        root.report_callback_exception = self.callback_error
        self.window_icon = tk.PhotoImage(file=str(asset("icon.png")))
        root.iconphoto(True, self.window_icon)
        if os.name == "nt":
            root.iconbitmap(str(asset("icon.ico")))
        self._build()
        root.update_idletasks()
        width = max(440, self.body.winfo_reqwidth())
        height = min(self.body.winfo_reqheight(), root.winfo_screenheight() - 100)
        self.viewport.itemconfigure(self.body_window, width=width)
        self.viewport.configure(width=width, height=height,
                                scrollregion=(0, 0, width, self.body.winfo_reqheight()))
        if self.body.winfo_reqheight() > height:
            scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.viewport.yview)
            scrollbar.pack(side="right", fill="y")
            self.viewport.configure(yscrollcommand=scrollbar.set)
            width += scrollbar.winfo_reqwidth()
            root.bind("<MouseWheel>", lambda event: self.viewport.yview_scroll(
                -1 if event.delta > 0 else 1, "units"))
            root.bind("<Button-4>", lambda event: self.viewport.yview_scroll(-1, "units"))
            root.bind("<Button-5>", lambda event: self.viewport.yview_scroll(1, "units"))
        self.viewport.pack(side="left", fill="both", expand=True)
        root.geometry(f"{width}x{height}")
        root.minsize(width, height)
        self.poll_job = root.after(100, self._poll)

    def label(self, parent, text, size=13, color=TEXT, bold=False, **kwargs):
        return ctk.CTkLabel(parent, text=text, text_color=color, height=20,
                            font=ui_font(size, bold), **kwargs)

    def divider(self, parent):
        ctk.CTkFrame(parent, height=1, corner_radius=0, fg_color=BORDER).pack(fill="x", padx=18)

    def combo(self, parent, variable, values):
        return ctk.CTkComboBox(parent, variable=variable, values=values, state="readonly",
                               width=142, height=32, corner_radius=7, border_width=0,
                               fg_color=BG, button_color=BG, button_hover_color="#e9ebef",
                               text_color=TEXT, dropdown_fg_color=CARD,
                               dropdown_hover_color=BG, dropdown_text_color=TEXT,
                               font=ui_font(12), dropdown_font=ui_font(12))

    def _build(self):
        self.viewport = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        body = self.body = tk.Frame(self.viewport, bg=BG, padx=24, pady=24)
        self.body_window = self.viewport.create_window(0, 0, window=body, anchor="nw")
        header = tk.Frame(body, bg=BG)
        header.pack(fill="x")
        with Image.open(asset("icon.png")) as source:
            self.brand_image = ctk.CTkImage(light_image=source.copy(), size=(30, 30))
        self.label(header, "", image=self.brand_image, width=30).pack(side="left", padx=(0, 10))
        self.label(header, "InputLock", 20, bold=True).pack(side="left")
        ctk.CTkButton(header, text="···", width=30, height=30, corner_radius=8,
                      font=ui_font(20, True), fg_color="transparent", hover_color="#e9ebef",
                      text_color=MUTED, command=self.about).pack(side="right")

        state_row = tk.Frame(body, bg=BG)
        state_row.pack(fill="x", pady=(26, 16))
        self.status_dot = self.label(state_row, "●", 10, "#31936a")
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status = self.label(state_row, "Desbloqueado", 14)
        self.status.pack(side="left")
        self.timer = self.label(state_row, "", 12, MUTED)
        self.timer.pack(side="right")

        devices = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12)
        devices.pack(fill="x")
        self.keyboard = DeviceCard(devices, "Teclado", "Teclas e atalhos", "keyboard",
                                    lambda: self.toggle(self.keyboard))
        self.keyboard.pack(fill="x", padx=18, pady=(4, 0))
        self.divider(devices)
        self.mouse = DeviceCard(devices, "Mouse", "Movimento e cliques", "mouse",
                                 lambda: self.toggle(self.mouse))
        self.mouse.pack(fill="x", padx=18, pady=(0, 4))

        options = ctk.CTkFrame(body, fg_color=CARD, corner_radius=12)
        options.pack(fill="x", pady=(14, 0))
        self.duration = tk.StringVar(value=next(name for name, seconds in DURATIONS.items()
                                                if seconds == self.config["duration"]))
        self.delay = tk.StringVar(value=f'{self.config["delay"]} segundos')
        self.shortcut = tk.StringVar(value=self.config["shortcut"])
        for index, title in enumerate(("Desbloquear após", "Iniciar em", "Atalho de desbloqueio")):
            row = tk.Frame(options, bg=CARD, height=50)
            row.pack(fill="x", padx=18, pady=(4 if index == 0 else 0, 4 if index == 2 else 0))
            row.pack_propagate(False)
            self.label(row, title, 12).pack(side="left")
            if index == 0:
                self.duration_box = self.combo(row, self.duration, list(DURATIONS))
                self.duration_box.pack(side="right")
            elif index == 1:
                self.delay_box = self.combo(row, self.delay, ["0 segundos", "3 segundos", "5 segundos"])
                self.delay_box.pack(side="right")
            else:
                self.shortcut_entry = ctk.CTkEntry(row, textvariable=self.shortcut, width=142,
                                                  height=32, corner_radius=7, border_width=1,
                                                  border_color=BORDER, fg_color=BG,
                                                  text_color=TEXT, font=ui_font(12), justify="center")
                self.shortcut_entry.pack(side="right")
                self.shortcut_entry.bind("<Return>", lambda event: self.save_preferences())
            if index < 2:
                self.divider(options)

        self.action = ctk.CTkButton(body, text="Bloquear dispositivos", command=self.start,
                                    height=46, corner_radius=9, fg_color=TEXT,
                                    hover_color="#363d48", text_color=CARD,
                                    font=ui_font(14, True))
        self.action.pack(fill="x", pady=(20, 0))
        self.hint = self.label(body, "Ctrl + Alt + F12 libera tudo", 11, MUTED)
        self.hint.pack(pady=(10, 0))
        footer = tk.Frame(body, bg=BG)
        footer.pack(fill="x", pady=(24, 0))
        author = self.label(footer, "made by rafaelolv", 11, MUTED, cursor="hand2")
        author.pack(side="left")
        author.bind("<Button-1>", lambda event: webbrowser.open(GITHUB))
        source = self.label(footer, "GitHub ↗", 11, MUTED, cursor="hand2")
        source.pack(side="right")
        source.bind("<Button-1>", lambda event: webbrowser.open(SOURCE))
        for link in (author, source):
            link.bind("<Enter>", lambda event, widget=link: widget.configure(text_color=TEXT))
            link.bind("<Leave>", lambda event, widget=link: widget.configure(text_color=MUTED))
        if self.preview:
            self.root.title("InputLock · Prévia")
        elif os.name != "nt":
            self.action.configure(text="Disponível no Windows", state="disabled")
            self.hint.configure(text="Bloqueio real disponível no Windows")

    def toggle(self, card):
        if self.pending is not None or (self.backend and any(self.backend.snapshot()[:2])):
            return
        card.set_selected(not card.selected)
        self._render_state = None

    def save_preferences(self):
        try:
            config = {"shortcut": normalize_shortcut(self.shortcut.get()),
                      "duration": DURATIONS[self.duration.get()],
                      "delay": int(self.delay.get().split()[0])}
            save_config(config)
            self.config = config
            self.shortcut.set(config["shortcut"])
            return True
        except (ValueError, OSError) as error:
            messagebox.showerror("Confira as preferências", str(error), parent=self.root)
            return False

    def start(self):
        if self.pending is not None:
            self.cancel_countdown()
            return
        if self.backend and any(self.backend.snapshot()[:2]):
            self.backend.unlock()
            return
        if not (self.keyboard.selected or self.mouse.selected):
            self.status.configure(text="Selecione teclado ou mouse")
            return
        if not self.save_preferences():
            return
        if not self.backend:
            try:
                self.backend = LockState() if self.preview else WindowsInputLock()
            except OSError as error:
                messagebox.showerror("Não foi possível bloquear", str(error), parent=self.root)
                return
        self._set_controls(False)
        self.pending_end = time.monotonic() + self.config["delay"]
        self._render_state = None
        self._countdown()

    def _countdown(self):
        remaining = math.ceil(self.pending_end - time.monotonic())
        if remaining > 0:
            self.status.configure(text=f"Bloqueando em {remaining}…")
            self.timer.configure(text="Esc cancela")
            self.action.configure(text=f"Cancelar · {remaining}s")
            self.pending = self.root.after(100, self._countdown)
            return
        self.pending = None
        self.pending_end = None
        try:
            self.backend.lock(self.keyboard.selected, self.mouse.selected,
                              self.config["shortcut"], self.config["duration"])
            self.root.focus_set()
        except (OSError, ValueError) as error:
            self._set_controls(True)
            messagebox.showerror("Não foi possível bloquear", str(error), parent=self.root)

    def cancel_countdown(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = self.pending_end = None
            self._render_state = None
            self._set_controls(True)

    def _set_controls(self, enabled):
        self.duration_box.configure(state="readonly" if enabled else "disabled")
        self.delay_box.configure(state="readonly" if enabled else "disabled")
        self.shortcut_entry.configure(state="normal" if enabled else "disabled")
        self.keyboard.set_enabled(enabled)
        self.mouse.set_enabled(enabled)

    def _poll(self):
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None
        if self.preview and self.backend:
            self.backend.expire()
        if self.pending is None:
            keyboard, mouse, remaining = self.backend.snapshot() if self.backend else (False, False, None)
            active = keyboard or mouse
            state = (keyboard, mouse, math.ceil(remaining) if remaining is not None else None)
            if state == self._render_state:
                self.poll_job = self.root.after(100, self._poll)
                return
            self._render_state = state
            self._set_controls(not active)
            if active:
                self.status_dot.configure(text_color="#c78537")
                text = "Teclado e mouse bloqueados" if keyboard and mouse else (
                    "Teclado bloqueado" if keyboard else "Mouse bloqueado")
                self.status.configure(text=text)
                self.timer.configure(text=f"{math.ceil(remaining) // 60:02}:{math.ceil(remaining) % 60:02}" if remaining is not None else "Sem limite")
                self.action.configure(text="Desbloquear agora", fg_color=TEXT, text_color=CARD)
            else:
                self.status_dot.configure(text_color="#31936a")
                if self.status.cget("text") != "Selecione teclado ou mouse" or self.keyboard.selected or self.mouse.selected:
                    self.status.configure(text="Desbloqueado")
                self.timer.configure(text="")
                self.action.configure(text="Bloquear dispositivos", fg_color=TEXT, text_color=CARD)
                if not self.preview and os.name != "nt":
                    self.action.configure(text="Disponível no Windows", state="disabled")
        self.poll_job = self.root.after(100, self._poll)

    def about(self):
        window = tk.Toplevel(self.root)
        window.title("Sobre o InputLock")
        window.configure(bg=BG, padx=24, pady=22)
        window.resizable(False, False)
        window.transient(self.root)
        self.label(window, f"InputLock {VERSION}", 21, bold=True).pack(anchor="w")
        self.label(window, "made by rafaelolv", 13, MUTED).pack(anchor="w", pady=(6, 16))
        self.label(window, "Bloqueio temporário de teclado e mouse.\n\nBase: Keylock, de Axorax.\nModificado por rafaelolv em novembro de 2026.\nLicença AGPL-3.0. Sem garantia.\nVocê pode modificar e redistribuir sob essa licença.\n\nBloqueia entradas na sessão atual do Windows.\nNão substitui o bloqueio de sessão (Win + L).\nCtrl + Alt + Del continua disponível.",
                   12, MUTED, justify="left").pack(anchor="w")
        for title, url in (("Código-fonte ↗", SOURCE), ("Projeto original ↗", "https://github.com/Axorax/keylock"),
                           ("Licença AGPL-3.0 ↗", SOURCE + "/blob/main/LICENSE")):
            link = self.label(window, title, 12, TEXT, cursor="hand2")
            link.pack(anchor="w", pady=(12, 0))
            link.bind("<Button-1>", lambda event, target=url: webbrowser.open(target))

    def callback_error(self, exception, value, traceback):
        if self.backend:
            self.backend.unlock()
        self.cancel_countdown()
        messagebox.showerror("InputLock", f"Dispositivos liberados.\n\n{value}", parent=self.root)

    def close(self):
        self.cancel_countdown()
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None
        if self.backend:
            self.backend.unlock()
            if hasattr(self.backend, "close"):
                self.backend.close()
        # Stop toolkit timers before destroying their registered Tcl commands.
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
