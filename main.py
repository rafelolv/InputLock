"""InputLock desktop interface. Run with --preview for a non-blocking demo."""

import ctypes
import math
import os
import sys
import time
import tkinter as tk
import webbrowser
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

from core import EMERGENCY_SHORTCUT, LockState, WindowsInputLock, normalize_shortcut
from settings import DURATIONS, load_config, save_config

VERSION = "1.0.0"
GITHUB = "https://github.com/rafelolv"
SOURCE = GITHUB + "/InputLock"
BG = "#101210"
CARD = "#191c19"
BORDER = "#30362d"
TEXT = "#f1f4eb"
MUTED = "#979f91"
ACCENT = "#c4f56b"
DARK = "#19220e"
FONT = "Segoe UI"


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / name


def draw_icon(canvas, kind, color, x=0, y=0, scale=1):
    def line(points, **options):
        return canvas.create_line(*[v * scale + (x if i % 2 == 0 else y)
                                    for i, v in enumerate(points)],
                                  fill=color, width=2 * scale, **options)

    def rect(box, **options):
        return canvas.create_rectangle(*[v * scale + (x if i % 2 == 0 else y)
                                         for i, v in enumerate(box)],
                                       outline=color, width=2 * scale, **options)

    if kind == "keyboard":
        rect([1, 8, 43, 34])
        for row in (14, 21):
            for col in (8, 16, 24, 32, 39):
                line([col, row, col + 1, row])
        line([12, 28, 32, 28])
    elif kind == "mouse":
        canvas.create_oval(x + 10 * scale, y + 1 * scale, x + 34 * scale,
                           y + 41 * scale, outline=color, width=2 * scale)
        line([22, 2, 22, 17])
        line([11, 18, 33, 18])
    elif kind == "lock":
        canvas.create_arc(x + 11 * scale, y + 1 * scale, x + 33 * scale,
                          y + 29 * scale, start=0, extent=180, style="arc",
                          outline=color, width=3 * scale)
        rect([7, 15, 37, 39])
        line([22, 24, 22, 30])


class DeviceCard(tk.Frame):
    def __init__(self, parent, title, description, kind, command):
        super().__init__(parent, bg=CARD, highlightthickness=1, highlightbackground=ACCENT,
                         cursor="hand2", padx=18, pady=14, takefocus=True)
        self.selected = True
        self.command = command
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x")
        self.icon = tk.Canvas(top, width=48, height=46, bg=CARD, highlightthickness=0)
        self.icon.pack(side="left")
        draw_icon(self.icon, kind, ACCENT)
        self.check = tk.Label(top, text="✓", bg=ACCENT, fg=DARK, font=(FONT, 10, "bold"),
                              width=2)
        self.check.pack(side="right", anchor="n")
        tk.Label(self, text=title, bg=CARD, fg=TEXT, font=(FONT, 13, "bold"),
                 anchor="w").pack(fill="x", pady=(10, 2))
        tk.Label(self, text=description, bg=CARD, fg=MUTED, font=(FONT, 9),
                 anchor="w").pack(fill="x")
        self._bind_tree(self)
        self.bind("<space>", lambda event: self.command())
        self.bind("<Return>", lambda event: self.command())

    def _bind_tree(self, widget):
        widget.bind("<Button-1>", lambda event: self.command())
        for child in widget.winfo_children():
            self._bind_tree(child)

    def set_selected(self, selected):
        self.selected = selected
        self.configure(highlightbackground=ACCENT if selected else BORDER)
        self.check.configure(text="✓" if selected else " ", bg=ACCENT if selected else BORDER)
        for item in self.icon.find_all():
            if self.icon.type(item) == "line":
                self.icon.itemconfigure(item, fill=ACCENT if selected else MUTED)
            else:
                self.icon.itemconfigure(item, outline=ACCENT if selected else MUTED)


class InputLockApp:
    def __init__(self, root, preview=False):
        self.root = root
        self.preview = preview
        self.backend = None
        self.pending = None
        self.pending_end = None
        self.config = load_config()
        root.title("InputLock")
        root.configure(bg=BG)
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda event: self.cancel_countdown())
        root.report_callback_exception = self.callback_error
        try:
            self.window_icon = tk.PhotoImage(file=str(asset("icon.png")))
            root.iconphoto(True, self.window_icon)
            if os.name == "nt":
                root.iconbitmap(str(asset("icon.ico")))
        except tk.TclError:
            pass
        self._style()
        self._build()
        root.update_idletasks()
        width = max(556, self.body.winfo_reqwidth())
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

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground="#232722", background="#232722",
                        foreground=TEXT, arrowcolor=ACCENT, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=6,
                        selectbackground="#232722", selectforeground=TEXT)
        style.map("TCombobox", fieldbackground=[("readonly", "#232722")],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", "#232722")])
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#354428")
        self.root.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kwargs):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=(FONT, size, "bold" if bold else "normal"), **kwargs)

    def _build(self):
        self.viewport = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        body = self.body = tk.Frame(self.viewport, bg=BG, padx=28, pady=20)
        self.body_window = self.viewport.create_window(0, 0, window=body, anchor="nw")
        header = tk.Frame(body, bg=BG)
        header.pack(fill="x")
        mark = tk.Canvas(header, width=36, height=36, bg=BG, highlightthickness=0)
        mark.pack(side="left", padx=(0, 10))
        mark.create_rectangle(0, 0, 35, 35, fill=ACCENT, outline=ACCENT)
        draw_icon(mark, "lock", DARK, 5, 3, .6)
        self.label(header, "InputLock", 17, bold=True).pack(side="left")
        self.label(header, f"v{VERSION}", 9, MUTED).pack(side="right")

        self.label(body, "Bloqueio de entrada", 24, bold=True, anchor="w").pack(fill="x", pady=(19, 4))
        self.label(body, "Bloqueie o teclado, o mouse ou os dois.",
                   10, MUTED, anchor="w").pack(fill="x")

        self.status_box = tk.Frame(body, bg=CARD, padx=14, pady=10)
        self.status_box.pack(fill="x", pady=(16, 16))
        self.status_dot = self.label(self.status_box, "●", 11, ACCENT)
        self.status_dot.pack(side="left", padx=(0, 9))
        self.status = self.label(self.status_box, "Desbloqueado", 10, bold=True)
        self.status.pack(side="left")
        self.timer = self.label(self.status_box, "AGUARDANDO", 8, MUTED)
        self.timer.pack(side="right")

        section = tk.Frame(body, bg=BG)
        section.pack(fill="x", pady=(0, 10))
        self.label(section, "DISPOSITIVOS", 9, MUTED, bold=True).pack(side="left")
        self.label(section, "Clique para selecionar", 9, MUTED).pack(side="right")
        devices = tk.Frame(body, bg=BG)
        devices.pack(fill="x")
        devices.columnconfigure((0, 1), weight=1, uniform="device")
        self.keyboard = DeviceCard(devices, "Teclado", "Teclas e atalhos", "keyboard",
                                   lambda: self.toggle(self.keyboard))
        self.keyboard.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        self.mouse = DeviceCard(devices, "Mouse", "Movimento, cliques e rolagem", "mouse",
                                lambda: self.toggle(self.mouse))
        self.mouse.grid(row=0, column=1, sticky="nsew", padx=(7, 0))

        options = tk.Frame(body, bg=CARD, padx=16, pady=12,
                           highlightthickness=1, highlightbackground=BORDER)
        options.pack(fill="x", pady=(16, 0))
        self.label(options, "OPÇÕES", 9, MUTED, bold=True).pack(anchor="w", pady=(0, 8))
        row = tk.Frame(options, bg=CARD)
        row.pack(fill="x")
        row.columnconfigure((0, 1), weight=1, uniform="option")
        for column, title in enumerate(("Desbloquear após", "Começar em")):
            self.label(row, title, 10).grid(row=0, column=column, sticky="w", pady=(0, 6))
        self.duration = tk.StringVar(value=next(name for name, seconds in DURATIONS.items()
                                              if seconds == self.config["duration"]))
        self.duration_box = ttk.Combobox(row, textvariable=self.duration, values=list(DURATIONS),
                                        state="readonly", width=18, font=(FONT, 10))
        self.duration_box.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.delay = tk.StringVar(value=f'{self.config["delay"]} segundos')
        self.delay_box = ttk.Combobox(row, textvariable=self.delay,
                                     values=["0 segundos", "3 segundos", "5 segundos"],
                                     state="readonly", width=16, font=(FONT, 10))
        self.delay_box.grid(row=1, column=1, sticky="ew")
        shortcut_row = tk.Frame(options, bg=CARD)
        shortcut_row.pack(fill="x", pady=(12, 0))
        self.label(shortcut_row, "Atalho para liberar", 10).pack(side="left")
        self.shortcut = tk.StringVar(value=self.config["shortcut"])
        self.shortcut_entry = tk.Entry(shortcut_row, textvariable=self.shortcut, width=17,
                                       bg="#232722", fg=ACCENT, insertbackground=ACCENT,
                                       relief="flat", font=(FONT, 11), justify="center",
                                       highlightthickness=1, highlightbackground=BORDER,
                                       highlightcolor=ACCENT)
        self.shortcut_entry.pack(side="right", ipady=5)
        self.shortcut_entry.bind("<Return>", lambda event: self.save_preferences())
        self.label(options, "Ex.: ctrl+q, alt+1 ou ctrl+shift+f8", 9, MUTED).pack(anchor="w", pady=(7, 0))

        self.action = tk.Button(body, text="Bloquear dispositivos", command=self.start,
                                bg=ACCENT, fg=DARK, activebackground="#d3ff8c",
                                activeforeground=DARK, relief="flat", bd=0, pady=12,
                                font=(FONT, 12, "bold"), cursor="hand2",
                                highlightthickness=0)
        self.action.pack(fill="x", pady=(16, 0))
        self.hint = self.label(body, "Emergência: Ctrl + Alt + F12 sempre libera tudo.", 9, MUTED)
        self.hint.pack(pady=(8, 12))
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x")
        footer = tk.Frame(body, bg=BG)
        footer.pack(fill="x", pady=(12, 0))
        self.label(footer, "made by", 9, MUTED).pack(side="left")
        author = self.label(footer, " rafaelolv ↗", 9, ACCENT, cursor="hand2")
        author.pack(side="left")
        author.bind("<Button-1>", lambda event: webbrowser.open(GITHUB))
        about = self.label(footer, "Sobre", 9, MUTED, cursor="hand2")
        about.pack(side="right", padx=(14, 0))
        about.bind("<Button-1>", lambda event: self.about())
        source = self.label(footer, "GitHub ↗", 9, TEXT, cursor="hand2")
        source.pack(side="right")
        source.bind("<Button-1>", lambda event: webbrowser.open(SOURCE))
        if self.preview or os.name != "nt":
            self.hint.configure(text="Prévia visual · bloqueio real disponível no Windows.")
            if not self.preview:
                self.action.configure(text="Disponível no Windows", state="disabled")

    def toggle(self, card):
        if self.pending is not None or (self.backend and any(self.backend.snapshot()[:2])):
            return
        card.set_selected(not card.selected)

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
        self._countdown()

    def _countdown(self):
        remaining = math.ceil(self.pending_end - time.monotonic())
        if remaining > 0:
            self.status.configure(text=f"Bloqueando em {remaining}…")
            self.timer.configure(text="ESC PARA CANCELAR")
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
            self._set_controls(True)

    def _set_controls(self, enabled):
        self.duration_box.configure(state="readonly" if enabled else "disabled")
        self.delay_box.configure(state="readonly" if enabled else "disabled")
        self.shortcut_entry.configure(state="normal" if enabled else "disabled")

    def _poll(self):
        if self.poll_job is not None:
            self.root.after_cancel(self.poll_job)
            self.poll_job = None
        if self.preview and self.backend:
            self.backend.expire()
        if self.pending is None:
            keyboard, mouse, remaining = self.backend.snapshot() if self.backend else (False, False, None)
            active = keyboard or mouse
            self._set_controls(not active)
            if active:
                text = "Teclado e mouse bloqueados" if keyboard and mouse else (
                    "Teclado bloqueado" if keyboard else "Mouse bloqueado")
                self.status.configure(text=text)
                self.timer.configure(text=f"{math.ceil(remaining) // 60:02}:{math.ceil(remaining) % 60:02}" if remaining is not None else "SEM LIMITE")
                self.action.configure(text="Desbloquear agora", bg="#354428", fg=ACCENT)
            else:
                if self.status.cget("text") != "Selecione teclado ou mouse" or self.keyboard.selected or self.mouse.selected:
                    self.status.configure(text="Desbloqueado")
                self.timer.configure(text="AGUARDANDO")
                self.action.configure(text="Bloquear dispositivos", bg=ACCENT, fg=DARK)
                if not self.preview and os.name != "nt":
                    self.action.configure(text="Disponível no Windows", state="disabled")
        self.poll_job = self.root.after(100, self._poll)

    def about(self):
        window = tk.Toplevel(self.root)
        window.title("Sobre o InputLock")
        window.configure(bg=BG, padx=24, pady=22)
        window.resizable(False, False)
        window.transient(self.root)
        self.label(window, f"InputLock {VERSION}", 18, bold=True).pack(anchor="w")
        self.label(window, "made by rafaelolv", 11, ACCENT).pack(anchor="w", pady=(6, 16))
        self.label(window, "Bloqueio temporário de teclado e mouse.\n\nBase: Keylock, de Axorax.\nModificado por rafaelolv em novembro de 2026.\nLicença AGPL-3.0. Sem garantia.\nVocê pode modificar e redistribuir sob essa licença.\n\nBloqueia entradas na sessão atual do Windows.\nNão substitui o bloqueio de sessão (Win + L).\nCtrl + Alt + Del continua disponível.",
                   10, MUTED, justify="left").pack(anchor="w")
        for title, url in (("Código-fonte ↗", SOURCE), ("Projeto original ↗", "https://github.com/Axorax/keylock"),
                           ("Licença AGPL-3.0 ↗", SOURCE + "/blob/main/LICENSE")):
            link = self.label(window, title, 10, ACCENT, cursor="hand2")
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
