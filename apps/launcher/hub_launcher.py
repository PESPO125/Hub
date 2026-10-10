"""Lanzador de Hub: ventana simple para acceder a las microapps.

Solo usa la librería estándar de Python (tkinter + urllib), así que se puede
convertir en .exe con PyInstaller sin dependencias extra. Habla con el mismo
backend que el panel web: no tiene lógica propia sobre plugins.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import tkinter as tk
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from tkinter import filedialog, ttk
from typing import Callable

API_URL = os.environ.get("HUB_API_URL", "http://127.0.0.1:8000").rstrip("/")
WEB_URL = os.environ.get("HUB_WEB_URL", "http://localhost:5173").rstrip("/")

YOUTUBE_PLUGIN_ID = "youtube-dl"
YOUTUBE_TOOL_ID = "download-video"
DOWNLOAD_TIMEOUT = 1800
AUDIO_FORMATS = ("mp3", "wav")

FONT = "Segoe UI"
PAD_X = 32
BG, CARD, BORDER = "#0b0f19", "#111827", "#1f2937"
TEXT, MUTED, GOLD = "#f8fafc", "#94a3b8", "#eab308"
ACCENT, ACCENT_HOVER = "#38bdf8", "#0ea5e9"
BUTTON_BG, BUTTON_HOVER = BORDER, "#374151"
ERROR = "#f87171"

FORMAT_LABELS = {"mp4": "MP4", "webm": "WEBM", "mov": "MOV", "mp3": "MP3 (solo audio)", "wav": "WAV (solo audio)"}
VIDEO_QUALITY_LABELS = {"best": "Máxima disponible", "2160": "2160p (4K)", "1440": "1440p", "1080": "1080p", "720": "720p", "480": "480p"}
AUDIO_QUALITY_LABELS = {"best": "Máxima disponible", "320": "320 kbps", "256": "256 kbps", "192": "192 kbps", "128": "128 kbps"}


@dataclass(frozen=True)
class Tool:
    plugin_id: str
    plugin_name: str
    tool_id: str
    name: str
    description: str


class BackendError(Exception):
    """El backend no responde o devolvió algo inesperado."""


# --------------------------------------------------------------------------- cliente HTTP

_NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError, OSError)


def _http_error_message(exc: urllib.error.HTTPError) -> str:
    default = f"El backend respondió {exc.code}."
    try:
        return json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", default)
    except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return default


def _api_request(path: str, method: str = "GET", body: dict | None = None,
                 timeout: float = 5, api_url: str | None = None) -> dict:
    base = (api_url or API_URL).rstrip("/")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{base}/api/v1/{path.lstrip('/')}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise BackendError(_http_error_message(exc)) from exc
    except (*_NETWORK_ERRORS, json.JSONDecodeError) as exc:
        raise BackendError(str(exc)) from exc


def fetch_catalog(api_url: str | None = None, timeout: float = 2.5) -> dict:
    return _api_request("catalog", api_url=api_url, timeout=timeout)


def fetch_youtube_downloader_settings() -> dict:
    return _api_request(f"plugins/{YOUTUBE_PLUGIN_ID}/config")


def save_youtube_downloader_settings(settings: dict) -> dict:
    return _api_request(f"plugins/{YOUTUBE_PLUGIN_ID}/config", "PUT", settings)


def fetch_tasks(limit: int = 20) -> list[dict]:
    return _api_request(f"tasks?limit={limit}").get("items", [])


def _unique_destination(directory: Path, name: str) -> Path:
    destination = directory / name
    index = 1
    while destination.exists():
        destination = directory / f"{destination.stem.rsplit(' (', 1)[0] if index > 1 else Path(name).stem} ({index}){Path(name).suffix}"
        index += 1
    return destination


def download_youtube_video(url: str, api_url: str | None = None, download_dir: Path | None = None,
                           timeout: float = DOWNLOAD_TIMEOUT) -> Path:
    base = (api_url or API_URL).rstrip("/")
    request = urllib.request.Request(
        f"{base}/api/v1/plugins/{YOUTUBE_PLUGIN_ID}/download",
        data=json.dumps({"url": url, "save_to_output_directory": True}).encode("utf-8"),
        headers={"Accept": "application/octet-stream", "Content-Type": "application/json"},
        method="POST",
    )
    target_dir = download_dir or (Path.home() / "Downloads")
    temporary_path: Path | None = None
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            filename = Path(response.headers.get_filename() or "youtube-video").name
            if filename in {"", ".", ".."}:
                filename = "youtube-video"
            destination = target_dir / filename
            if destination.is_file():
                # El backend ya guardó el archivo en esta carpeta con nombre único: no se duplica.
                while response.read(1024 * 1024):
                    pass
                return destination
            destination = _unique_destination(target_dir, filename)
            with NamedTemporaryFile(prefix=".hub-download-", dir=target_dir, delete=False) as output:
                temporary_path = Path(output.name)
                shutil.copyfileobj(response, output)
        os.replace(temporary_path, destination)
        return destination
    except urllib.error.HTTPError as exc:
        raise BackendError(_http_error_message(exc)) from exc
    except _NETWORK_ERRORS as exc:
        raise BackendError(str(exc)) from exc
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)  # no-op si os.replace ya lo movió


# --------------------------------------------------------------------------- catálogo

def tools_from_catalog(catalog: dict) -> list[Tool]:
    tools = [
        Tool(p["id"], p["name"], t["id"], t["name"], t.get("description", ""))
        for p in catalog.get("items", [])
        if p.get("status") == "available" and p.get("enabled")
        for t in p.get("tools", [])
    ]
    return sorted(tools, key=lambda t: (t.name.lower(), t.plugin_name.lower()))


def filter_tools(tools: list[Tool], term: str) -> list[Tool]:
    term = term.strip().lower()
    if not term:
        return tools
    return [t for t in tools if term in t.name.lower() or term in t.description.lower() or term in t.plugin_name.lower()]


def _is_youtube_downloader(tool: Tool) -> bool:
    return tool.plugin_id == YOUTUBE_PLUGIN_ID and tool.tool_id == YOUTUBE_TOOL_ID


# --------------------------------------------------------------------------- widgets

def _label(parent, text: str = "", size: int = 10, bold: bool = False, fg: str = TEXT, bg: str = BG, **kwargs) -> tk.Label:
    return tk.Label(parent, text=text, font=(FONT, size, "bold") if bold else (FONT, size), bg=bg, fg=fg, **kwargs)


def _surface(parent) -> tk.Frame:
    return tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)


class _HoverCanvas(tk.Canvas):
    """Canvas clicable que se redibuja con otro color al pasar el cursor."""

    def _setup_hover(self, command: Callable[[], None], color: str, hover_color: str) -> None:
        self.command = command
        self._draw(color)
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", lambda _e: self._draw(hover_color))
        self.bind("<Leave>", lambda _e: self._draw(color))

    def _draw(self, color: str) -> None:  # pragma: no cover - lo implementan las subclases
        raise NotImplementedError


class RoundedButton(_HoverCanvas):
    """Botón con esquinas muy redondeadas (estilo píldora)."""

    def __init__(self, parent, text, command, bg=BUTTON_BG, hover_bg=BUTTON_HOVER, fg=TEXT,
                 font=(FONT, 10, "bold"), radius=12, padx=18, pady=10, canvas_bg=BG):
        probe = tk.Label(parent, text=text, font=font)
        width, height = probe.winfo_reqwidth() + padx * 2, probe.winfo_reqheight() + pady * 2
        probe.destroy()
        super().__init__(parent, width=width, height=height, bg=canvas_bg, highlightthickness=0, cursor="hand2")
        self.text, self.font, self.fg, self.radius, self.w, self.h = text, font, fg, radius, width, height
        self._setup_hover(command, bg, hover_bg)

    def _draw(self, color: str) -> None:
        self.delete("all")
        r, w, h = self.radius, self.w, self.h
        for x, y, start in ((0, 0, 90), (w - 2 * r, 0, 0), (0, h - 2 * r, 180), (w - 2 * r, h - 2 * r, 270)):
            self.create_arc(x, y, x + 2 * r, y + 2 * r, start=start, extent=90, fill=color, outline=color)
        self.create_rectangle(r, 0, w - r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h - r, fill=color, outline=color)
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg, font=self.font)


class SettingsIconButton(_HoverCanvas):
    """Icono de configuración (dos sliders)."""

    def __init__(self, parent, command, bg=CARD, hover_bg=BORDER, fg=TEXT):
        super().__init__(parent, width=36, height=36, bg=bg, highlightthickness=0, cursor="hand2")
        self.bg, self.fg = bg, fg
        self._setup_hover(command, bg, hover_bg)

    def _draw(self, color: str) -> None:
        self.delete("all")
        self.create_rectangle(0, 0, 36, 36, fill=color, outline=color)
        for y, knob_x in ((13, 12), (23, 20)):
            self.create_line(8, y, 28, y, fill=self.fg, width=2)
            self.create_oval(knob_x, y - 3, knob_x + 6, y + 3, fill=self.bg, outline=self.fg, width=2)


def _key_for(labels: dict[str, str], label: str, default: str = "best") -> str:
    return next((key for key, value in labels.items() if value == label), default)


class DownloadSettingsDialog(tk.Toplevel):
    """Preferencias del descargador: carpeta, formato y calidad."""

    BG, FG = "#ffffff", "#111111"

    def __init__(self, parent, config: dict, on_saved: Callable[[dict], None], on_closed: Callable[[], None]):
        super().__init__(parent)
        self._on_saved, self._on_closed = on_saved, on_closed
        self.title("Preferencias de descarga")
        self.configure(bg=self.BG)
        self.transient(parent)
        self.resizable(False, False)
        self.geometry("500x500")
        self.protocol("WM_DELETE_WINDOW", self.close)

        content = tk.Frame(self, bg=self.BG, padx=24, pady=22)
        content.pack(fill="both", expand=True)
        self._text(content, "Preferencias de descarga", size=15, bold=True).pack(anchor="w", pady=(0, 20))

        self.directory_var = tk.StringVar(value=config["output_directory"])
        self._build_directory_row(content)

        self.format_var = tk.StringVar(value=FORMAT_LABELS[config["output_format"]])
        self._text(content, "Formato").pack(anchor="w", pady=(0, 6))
        self._option_menu(content, self.format_var, FORMAT_LABELS.values(), self._refresh_quality)

        initial_labels = self._quality_labels()
        self.quality_var = tk.StringVar(value=initial_labels.get(config.get("quality", "best"), initial_labels["best"]))
        self.quality_caption = tk.StringVar()
        tk.Label(content, textvariable=self.quality_caption, bg=self.BG, fg=self.FG).pack(anchor="w", pady=(0, 6))
        self.quality_menu = self._option_menu(content, self.quality_var, initial_labels.values())
        self._refresh_quality()

        self.status_label = self._text(content, "", wraplength=460, justify="left")
        self.status_label.pack(anchor="w", pady=(0, 8))
        RoundedButton(content, text="Guardar preferencias", command=self._save, bg=ACCENT, hover_bg=ACCENT_HOVER,
                      fg=BG, radius=12, padx=18, pady=10, canvas_bg=self.BG).pack(anchor="e")

    def _text(self, parent, text: str, size: int = 10, bold: bool = False, **kwargs) -> tk.Label:
        return _label(parent, text, size, bold, fg=self.FG, bg=self.BG, **kwargs)

    def _build_directory_row(self, parent) -> None:
        self._text(parent, "Carpeta de descarga").pack(anchor="w", pady=(0, 6))
        row = tk.Frame(parent, bg=self.BG)
        row.pack(fill="x", pady=(0, 16))
        tk.Entry(row, textvariable=self.directory_var, state="readonly", readonlybackground=self.BG,
                 fg=self.FG, relief="solid", bd=1).pack(side="left", fill="x", expand=True, ipady=9, ipadx=10)
        RoundedButton(row, text="Examinar…", command=self._choose_directory, bg=BUTTON_BG, hover_bg=BUTTON_HOVER,
                      fg="#ffffff", radius=10, padx=12, pady=8, canvas_bg=self.BG).pack(side="left", padx=(8, 0))

    def _option_menu(self, parent, variable, values, command=None) -> tk.OptionMenu:
        menu = tk.OptionMenu(parent, variable, *values, command=command)
        menu.configure(bg=self.BG, fg=self.FG, activebackground="#e5e7eb", activeforeground=self.FG,
                       anchor="w", relief="solid", bd=1, highlightthickness=0)
        menu["menu"].configure(bg=self.BG, fg=self.FG, activebackground="#e5e7eb", activeforeground=self.FG, font=(FONT, 10))
        menu.pack(fill="x", ipady=4, pady=(0, 14))
        return menu

    def _is_audio(self) -> bool:
        return _key_for(FORMAT_LABELS, self.format_var.get(), "mp4") in AUDIO_FORMATS

    def _quality_labels(self) -> dict[str, str]:
        return AUDIO_QUALITY_LABELS if self._is_audio() else VIDEO_QUALITY_LABELS

    def _refresh_quality(self, _value: str | None = None) -> None:
        labels = self._quality_labels()
        if self.quality_var.get() not in labels.values():
            self.quality_var.set(labels["best"])
        self.quality_caption.set("Calidad de audio" if self._is_audio() else "Resolución máxima")
        menu = self.quality_menu["menu"]
        menu.delete(0, "end")
        for label in labels.values():
            menu.add_command(label=label, command=lambda value=label: self.quality_var.set(value))

    def _choose_directory(self) -> None:
        selected = filedialog.askdirectory(parent=self, initialdir=self.directory_var.get(), mustexist=False)
        if selected:
            self.directory_var.set(selected)

    def _save(self) -> None:
        values = {
            "output_directory": self.directory_var.get().strip(),
            "output_format": _key_for(FORMAT_LABELS, self.format_var.get(), "mp4"),
            "quality": _key_for(self._quality_labels(), self.quality_var.get()),
        }
        try:
            saved = save_youtube_downloader_settings(values)
        except BackendError as exc:
            self.status_label.config(text=str(exc), fg="#b42318")
            return
        self._on_saved(saved)
        self.close()

    def close(self) -> None:
        if self.winfo_exists():
            self.destroy()
        self._on_closed()


# --------------------------------------------------------------------------- aplicación

class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hub   ---   Cooking")
        self.geometry("600x760")
        self.minsize(500, 520)
        self.configure(bg=BG)

        self._tools: list[Tool] = []
        self._active_tool: Tool | None = None
        self._tool_url: tk.StringVar | None = None
        self._tool_entry: tk.Entry | None = None
        self._download_status: tk.StringVar | None = None
        self._download_status_label: tk.Label | None = None
        self._download_progressbar: ttk.Progressbar | None = None
        self._download_config: dict | None = None
        self._settings_window: DownloadSettingsDialog | None = None
        self._downloading = False
        self._connected = False
        self._results: queue.Queue = queue.Queue()

        self._setup_styles()
        self._build()
        self.bind_all("<Button-1>", self._handle_global_click, add="+")
        self.after(100, self._poll)
        self.refresh()

    # ---- construcción

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=TEXT, font=(FONT, 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Muted.TLabel", background=BG, foreground=GOLD, font=(FONT, 9))
        style.configure("Download.Horizontal.TProgressbar", troughcolor=BORDER, background=ACCENT)

    def _build(self) -> None:
        self._build_header()
        self._build_search()
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=PAD_X)
        self.canvas = tk.Canvas(self.body, highlightthickness=0, bg=BG)
        self.inner = ttk.Frame(self.canvas, style="TFrame")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.canvas.pack(side="left", fill="both", expand=True)
        self._build_footer()

    def _build_header(self) -> None:
        self.head = ttk.Frame(self)
        self.head.pack(fill="x", pady=(28, 20), padx=PAD_X)
        self.header_title_lbl = ttk.Label(self.head, text="HUB", font=(FONT, 22, "bold"))
        self.header_title_lbl.pack(side="left")
        self.back_btn = RoundedButton(self.head, text="← Back", command=self._close_tool, radius=10, padx=14, pady=7)
        self.status = ttk.Label(self.head, text="Conectando…", style="Muted.TLabel")
        self.status.pack(side="right", pady=8)

    def _build_search(self) -> None:
        self.search_frame = _surface(self)
        self.search_frame.pack(fill="x", pady=(0, 24), padx=PAD_X)
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())
        self.search_entry = tk.Entry(self.search_frame, textvariable=self.query, bg=CARD, fg=TEXT,
                                     insertbackground=TEXT, relief="flat", font=(FONT, 11))
        self.search_entry.pack(fill="x", ipady=12, ipadx=16)

    def _build_footer(self) -> None:
        foot = ttk.Frame(self)
        foot.pack(fill="x", pady=24, padx=PAD_X)
        RoundedButton(foot, text="Actualizar", command=self.refresh).pack(side="left")
        RoundedButton(foot, text="Panel web", command=lambda: webbrowser.open(WEB_URL),
                      bg=ACCENT, hover_bg=ACCENT_HOVER, fg=BG).pack(side="right")

    def _handle_global_click(self, event) -> None:
        if not isinstance(event.widget, tk.Entry):
            self.focus_set()

    # ---- render

    def _clear(self) -> None:
        for widget in self.inner.winfo_children():
            widget.destroy()

    def _message(self, title: str, detail: str, action: tuple[str, Callable[[], None]] | None = None) -> None:
        self._clear()
        frame = _surface(self.inner)
        frame.pack(fill="x", pady=16, ipadx=24, ipady=24)
        _label(frame, title, 13, True, bg=CARD).pack(anchor="w", pady=(0, 8))
        _label(frame, detail, fg=MUTED, bg=CARD, wraplength=460, justify="left").pack(anchor="w", pady=(0, 20))
        if action:
            RoundedButton(frame, text=action[0], command=action[1], bg=ACCENT, hover_bg=ACCENT_HOVER,
                          fg=BG, canvas_bg=CARD).pack(anchor="w")

    def _render(self) -> None:
        if self._active_tool is not None:
            self._render_tool(self._active_tool)
        elif not self._connected:
            self._message("Sin conexión con el Hub",
                          "El servidor local no está activo en este momento. Verificalo e intentá de nuevo.",
                          ("Reintentar conexión", self.refresh))
        elif not self._tools:
            self._message("No hay herramientas habilitadas",
                          "Agregá un plugin y activalo desde la configuración del panel web.",
                          ("Abrir administración", lambda: webbrowser.open(f"{WEB_URL}/settings?tab=plugins")))
        else:
            shown = filter_tools(self._tools, self.query.get())
            if not shown:
                self._message("Sin resultados", "Ninguna herramienta coincide con los términos de búsqueda.")
                return
            self._clear()
            for tool in shown:
                self._render_card(tool)

    def _render_card(self, tool: Tool) -> None:
        card = _surface(self.inner)
        card.pack(fill="x", pady=10, ipadx=20, ipady=16)
        top_row = tk.Frame(card, bg=CARD)
        top_row.pack(fill="x", pady=(0, 6))
        _label(top_row, tool.name, 12, True, bg=CARD).pack(side="left")
        if tool.description:
            _label(card, tool.description, 9, fg=MUTED, bg=CARD, wraplength=460, justify="left").pack(anchor="w", pady=(0, 12))
        buttons = tk.Frame(card, bg=CARD)
        buttons.pack(fill="x", pady=(4, 0))
        RoundedButton(buttons, text="Iniciar", command=lambda selected=tool: self._open_tool(selected),
                      hover_bg=ACCENT, radius=10, padx=16, pady=8, canvas_bg=CARD).pack(anchor="e")

        highlight = lambda color: (lambda _e: card.config(highlightbackground=color))  # noqa: E731
        for widget in (card, top_row):
            widget.bind("<Enter>", highlight(ACCENT))
            widget.bind("<Leave>", highlight(BORDER))

    def _open_tool(self, tool: Tool) -> None:
        self._active_tool = tool
        self.search_frame.pack_forget()
        self.header_title_lbl.pack_forget()
        self.back_btn.pack(side="left")
        self._render_tool(tool)

    def _close_tool(self) -> None:
        self._active_tool = None
        self._tool_entry = None
        self.back_btn.pack_forget()
        self.header_title_lbl.config(text="HUB")
        self.header_title_lbl.pack(side="left")
        self.search_frame.pack(fill="x", before=self.body, pady=(0, 24), padx=PAD_X)
        self._render()

    def _render_tool(self, tool: Tool) -> None:
        self._clear()
        panel = tk.Frame(self.inner, bg=BG)
        panel.pack(fill="x", pady=10)

        title_row = tk.Frame(panel, bg=BG)
        title_row.pack(fill="x", pady=(0, 4))
        _label(title_row, tool.name, 18, True).pack(side="left")
        is_downloader = _is_youtube_downloader(tool)
        if is_downloader:
            SettingsIconButton(title_row, command=self._open_tool_settings, bg=BG).pack(side="right")
        _label(panel, tool.plugin_name.upper(), 8, True, fg=ACCENT).pack(anchor="w", pady=(0, 20))

        if is_downloader:
            self._render_youtube_form(panel)
        else:
            detail = tool.description or "Esta herramienta todavía no tiene una interfaz nativa en Hub."
            _label(panel, detail, fg=MUTED, wraplength=460, justify="left").pack(anchor="w")

    def _render_youtube_form(self, panel: tk.Frame) -> None:
        _label(panel, "URL de YouTube", bold=True).pack(anchor="w", pady=(0, 8))
        self._tool_url = tk.StringVar()
        self._tool_entry = tk.Entry(panel, textvariable=self._tool_url, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                    relief="flat", font=(FONT, 11))
        self._tool_entry.pack(fill="x", ipady=12, ipadx=14, pady=(0, 16))
        self._tool_entry.bind("<Return>", lambda _e: self._download_tool())
        RoundedButton(panel, text="Descargar", command=self._download_tool, bg=ACCENT, hover_bg=ACCENT_HOVER,
                      fg=BG, padx=20).pack(anchor="e")

        self._download_progressbar = ttk.Progressbar(panel, mode="determinate", maximum=100,
                                                     style="Download.Horizontal.TProgressbar")
        self._download_status = tk.StringVar()
        self._download_status_label = _label(panel, fg=MUTED, textvariable=self._download_status,
                                             size=9, wraplength=460, justify="left")
        self._download_status_label.pack(anchor="w", pady=(8, 0))
        self._tool_entry.focus_set()

    # ---- preferencias de descarga

    def _set_download_status(self, text: str, color: str = ACCENT) -> None:
        if self._download_status is not None:
            self._download_status.set(text)
        if self._download_status_label is not None:
            self._download_status_label.config(fg=color)

    def _open_tool_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            return
        try:
            self._download_config = fetch_youtube_downloader_settings()
        except BackendError as exc:
            self._set_download_status(str(exc), ERROR)
            return
        self._settings_window = DownloadSettingsDialog(
            self, self._download_config, self._on_settings_saved, self._on_settings_closed)

    def _on_settings_saved(self, config: dict) -> None:
        self._download_config = config
        self._set_download_status("Preferencias guardadas.")

    def _on_settings_closed(self) -> None:
        self._settings_window = None

    # ---- descarga

    def _watch_download_progress(self, plugin_id: str, stop: threading.Event) -> None:
        while not stop.wait(0.75):
            try:
                task = next((row for row in fetch_tasks()
                             if row["plugin_id"] == YOUTUBE_PLUGIN_ID and row["operation"] == YOUTUBE_TOOL_ID
                             and row["status"] == "running"), None)
            except BackendError:
                continue
            if task is not None:
                self._results.put(("download_progress",
                                   (plugin_id, task.get("progress"), task.get("message") or "Descargando video…")))

    def _download_tool(self) -> None:
        if self._downloading or self._tool_url is None or self._download_status is None or self._active_tool is None:
            return
        url = self._tool_url.get().strip()
        if not url:
            self._download_status.set("Ingresa una URL de YouTube.")
            return
        tool = self._active_tool

        self._downloading = True
        is_audio = bool(self._download_config and self._download_config.get("output_format") in AUDIO_FORMATS)
        if self._download_progressbar is not None:
            self._download_progressbar.configure(value=0)
            self._download_progressbar.pack(fill="x", pady=(16, 0), before=self._download_status_label)
        self._set_download_status("Descargando audio…" if is_audio else "Descargando video…")

        def work() -> None:
            stop_watcher = threading.Event()
            watcher = threading.Thread(target=self._watch_download_progress, args=(tool.plugin_id, stop_watcher), daemon=True)
            watcher.start()
            try:
                config = fetch_youtube_downloader_settings()
                path = download_youtube_video(url, download_dir=Path(config["output_directory"]))
                self._results.put(("download_ok", (tool.plugin_id, path, config.get("output_format") in AUDIO_FORMATS)))
            except BackendError as exc:
                self._results.put(("download_error", (tool.plugin_id, str(exc), False)))
            finally:
                stop_watcher.set()
                watcher.join(timeout=2)

        threading.Thread(target=work, daemon=True).start()

    # ---- ciclo de eventos

    def refresh(self) -> None:
        self.status.config(text="Actualizando…")

        def work() -> None:
            try:
                self._results.put(("ok", tools_from_catalog(fetch_catalog())))
            except BackendError as exc:
                self._results.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True).start()

    def _poll(self) -> None:
        try:
            kind, payload = self._results.get_nowait()
        except queue.Empty:
            pass
        else:
            if kind in ("ok", "error"):
                self._on_catalog(kind == "ok", payload)
            elif kind == "download_progress":
                self._on_download_progress(*payload)
            else:
                self._downloading = False
                self._on_download_finished(kind == "download_ok", *payload)
        self.after(100, self._poll)

    def _on_catalog(self, connected: bool, payload) -> None:
        self._connected = connected
        self._tools = payload if connected else []
        count = len(self._tools)
        self.status.config(text=f"● {count} {'plugin' if count == 1 else 'plugins'}" if connected else "● Sin conexión")
        self._render()

    def _is_showing(self, plugin_id: str) -> bool:
        return bool(self._active_tool and self._active_tool.plugin_id == plugin_id and self._download_status is not None)

    def _on_download_progress(self, plugin_id: str, progress: float | None, message: str) -> None:
        if not self._is_showing(plugin_id):
            return
        self._set_download_status(message)
        if self._download_progressbar is not None and self._download_progressbar.winfo_manager() == "pack":
            self._download_progressbar.configure(value=(progress or 0) * 100)

    def _on_download_finished(self, ok: bool, plugin_id: str, result, is_audio: bool) -> None:
        if not self._is_showing(plugin_id):
            return
        if ok:
            self._set_download_status(f"{'Audio' if is_audio else 'Video'} guardado en: {result}")
            if self._download_progressbar is not None:
                self._download_progressbar.configure(value=100)
        else:
            self._set_download_status(result, ERROR)


def main() -> None:
    LauncherApp().mainloop()


if __name__ == "__main__":
    main()