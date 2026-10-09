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

API_URL = os.environ.get("HUB_API_URL", "http://127.0.0.1:8000").rstrip("/")
WEB_URL = os.environ.get("HUB_WEB_URL", "http://localhost:5173").rstrip("/")

@dataclass(frozen=True)
class Tool:
    plugin_id: str
    plugin_name: str
    tool_id: str
    name: str
    description: str


class BackendError(Exception):
    """El backend no responde o devolvió algo inesperado."""


def fetch_catalog(api_url: str | None = None, timeout: float = 2.5) -> dict:
    api_url = (api_url or API_URL).rstrip("/")
    req = urllib.request.Request(f"{api_url}/api/v1/catalog", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return json.load(res)
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as exc:
        raise BackendError(str(exc)) from exc


def _api_request(path: str, method: str = "GET", body: dict | None = None, timeout: float = 5) -> dict:
    api_url = API_URL.rstrip("/")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{api_url}/api/v1/{path.lstrip('/')}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
            message = detail.get("error", {}).get("message", f"El backend respondió {exc.code}.")
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = f"El backend respondió {exc.code}."
        raise BackendError(message) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError, OSError) as exc:
        raise BackendError(str(exc)) from exc


def fetch_youtube_downloader_settings() -> dict:
    return _api_request("plugins/youtube-dl/config")


def save_youtube_downloader_settings(settings: dict) -> dict:
    return _api_request("plugins/youtube-dl/config", "PUT", settings)


def fetch_tasks(limit: int = 20) -> list[dict]:
    return _api_request(f"tasks?limit={limit}").get("items", [])


def download_youtube_video(
    url: str,
    api_url: str | None = None,
    download_dir: Path | None = None,
    timeout: float = 1800,
) -> Path:
    api_url = (api_url or API_URL).rstrip("/")
    req = urllib.request.Request(
        f"{api_url}/api/v1/plugins/youtube-dl/download",
        data=json.dumps({"url": url, "save_to_output_directory": True}).encode("utf-8"),
        headers={"Accept": "application/octet-stream", "Content-Type": "application/json"},
        method="POST",
    )
    target_dir = download_dir or (Path.home() / "Downloads")
    temporary_path: Path | None = None
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            filename = Path(response.headers.get_filename() or "youtube-video").name
            if filename in {"", ".", ".."}:
                filename = "youtube-video"
            destination = target_dir / filename
            if destination.is_file():
                while response.read(1024 * 1024):
                    pass
                return destination
            suffix = destination.suffix
            stem = destination.stem
            index = 1
            while destination.exists():
                destination = target_dir / f"{stem} ({index}){suffix}"
                index += 1
            with NamedTemporaryFile(prefix=".hub-download-", dir=target_dir, delete=False) as output:
                temporary_path = Path(output.name)
                shutil.copyfileobj(response, output)
        os.replace(temporary_path, destination)
        return destination
    except urllib.error.HTTPError as exc:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        try:
            body = json.loads(exc.read().decode("utf-8"))
            message = body.get("error", {}).get("message", f"El backend respondió {exc.code}.")
        except (UnicodeDecodeError, json.JSONDecodeError):
            message = f"El backend respondió {exc.code}."
        raise BackendError(message) from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()
        raise BackendError(str(exc)) from exc


def tools_from_catalog(catalog: dict) -> list[Tool]:
    out: list[Tool] = []
    for p in catalog.get("items", []):
        if p.get("status") != "available" or not p.get("enabled"):
            continue
        for t in p.get("tools", []):
            out.append(Tool(p["id"], p["name"], t["id"], t["name"], t.get("description", "")))
    return sorted(out, key=lambda t: (t.name.lower(), t.plugin_name.lower()))


def filter_tools(tools: list[Tool], term: str) -> list[Tool]:
    term = term.strip().lower()
    if not term:
        return tools
    return [t for t in tools if term in t.name.lower() or term in t.description.lower() or term in t.plugin_name.lower()]


class RoundedButton(tk.Canvas):
    """Botón personalizado con esquinas muy redondeadas (estilo píldora) y efectos fluidos."""
    def __init__(self, parent, text, command, bg="#1f2937", hover_bg="#374151", fg="#f8fafc", font=("Segoe UI", 10, "bold"), radius=12, padx=18, pady=10, canvas_bg="#0b0f19"):
        self.font = font
        self.text = text
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        self.radius = radius
        
        dummy = tk.Label(parent, text=text, font=font)
        w = dummy.winfo_reqwidth() + padx * 2
        h = dummy.winfo_reqheight() + pady * 2
        dummy.destroy()

        super().__init__(parent, width=w, height=h, bg=canvas_bg, highlightthickness=0, cursor="hand2")
        
        self.w = w
        self.h = h
        
        self._draw(self.bg)
        
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg))

    def _draw(self, color):
        self.delete("all")
        r = self.radius
        w = self.w
        h = self.h
        
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, h-r*2, r*2, h, start=180, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, fill=color, outline=color)
        
        self.create_rectangle(r, 0, w-r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h-r, fill=color, outline=color)
        
        self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)


class SettingsIconButton(tk.Canvas):
    """Botón con el icono de configuración (sliders) rediseñado limpiamente."""
    def __init__(self, parent, command, bg="#111827", hover_bg="#1f2937", fg="#f8fafc"):
        super().__init__(parent, width=36, height=36, bg=bg, highlightthickness=0, cursor="hand2")
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        
        self._draw(self.bg)
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg))

    def _draw(self, color):
        self.delete("all")
        self.create_rectangle(0, 0, 36, 36, fill=color, outline=color)
        self.create_line(8, 13, 28, 13, fill=self.fg, width=2)
        self.create_oval(12, 10, 18, 16, fill=self.bg, outline=self.fg, width=2)
        self.create_line(8, 23, 28, 23, fill=self.fg, width=2)
        self.create_oval(20, 20, 26, 26, fill=self.bg, outline=self.fg, width=2)


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hub   ---   Cooking")
        self.geometry("600x760")
        self.minsize(500, 520)
        
        self.bg_color = "#0b0f19"
        self.card_bg = "#111827"
        self.border_color = "#1f2937"
        self.text_main = "#f8fafc"
        self.text_muted = "#94a3b8"
        self.accent_color = "#38bdf8"
        self.accent_hover = "#0ea5e9"
        self.gold_color = "#eab308"      # Color amarillo/dorado solicitado[cite: 11, 12]
        
        self.configure(bg=self.bg_color)

        self._tools: list[Tool] = []
        self._active_tool: Tool | None = None
        self._tool_url: tk.StringVar | None = None
        self._tool_entry: tk.Entry | None = None
        self._download_status: tk.StringVar | None = None
        self._download_status_label: tk.Label | None = None
        self._download_progressbar: ttk.Progressbar | None = None
        self._download_config: dict | None = None
        self._settings_window: tk.Toplevel | None = None
        self._downloading = False
        self._connected = False
        self._results: queue.Queue = queue.Queue()
        
        self._setup_styles()
        self._build()
        
        self.bind_all("<Button-1>", self._handle_global_click, add="+")
        
        self.after(100, self._poll)
        self.refresh()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=self.bg_color, foreground=self.text_main, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.text_main)
        style.configure("Muted.TLabel", background=self.bg_color, foreground=self.gold_color, font=("Segoe UI", 9)) # Aplicado color dorado/amarillo aquí[cite: 11, 12]
        style.configure("Download.Horizontal.TProgressbar", troughcolor=self.border_color, background="#38bdf8")

    def _build(self) -> None:
        pad = {"padx": 32}
        
        self.head = ttk.Frame(self)
        self.head.pack(fill="x", pady=(28, 20), **pad)
        self.header_title_lbl = ttk.Label(self.head, text="HUB", font=("Segoe UI", 22, "bold"))
        self.header_title_lbl.pack(side="left")
        self.back_btn = RoundedButton(
            self.head,
            text="← Back",
            command=self._close_tool,
            bg="#1f2937",
            hover_bg="#374151",
            fg=self.text_main,
            radius=10,
            padx=14,
            pady=7,
            canvas_bg=self.bg_color,
        )
        self.status = ttk.Label(self.head, text="Conectando…", style="Muted.TLabel")
        self.status.pack(side="right", pady=8)

        self.search_frame = tk.Frame(self, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1, bd=0)
        self.search_frame.pack(fill="x", pady=(0, 24), **pad)
        
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())
        
        self.search_entry = tk.Entry(
            self.search_frame, 
            textvariable=self.query, 
            bg=self.card_bg, 
            fg=self.text_main, 
            insertbackground=self.text_main, 
            relief="flat", 
            font=("Segoe UI", 11)
        )
        self.search_entry.pack(fill="x", ipady=12, ipadx=16)

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, **pad)
        
        self.canvas = tk.Canvas(self.body, highlightthickness=0, bg=self.bg_color)
        self.inner = ttk.Frame(self.canvas, style="TFrame")
        
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        
        self.canvas.pack(side="left", fill="both", expand=True)

        foot = ttk.Frame(self)
        foot.pack(fill="x", pady=24, **pad)
        
        RoundedButton(
            foot, 
            text="Actualizar", 
            command=self.refresh,
            bg="#1f2937",
            hover_bg="#374151",
            fg=self.text_main,
            radius=12,
            padx=18,
            pady=10,
            canvas_bg=self.bg_color
        ).pack(side="left")

        RoundedButton(
            foot, 
            text="Panel web", 
            command=lambda: webbrowser.open(WEB_URL),
            bg=self.accent_color,
            hover_bg=self.accent_hover,
            fg="#0b0f19",
            radius=12,
            padx=18,
            pady=10,
            canvas_bg=self.bg_color
        ).pack(side="right")

    def _handle_global_click(self, event) -> None:
        widget = event.widget
        if not isinstance(widget, tk.Entry):
            self.focus_set()

    def _clear(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()

    def _message(self, title: str, detail: str, action: tuple[str, callable] | None = None) -> None:
        self._clear()
        msg_frame = tk.Frame(self.inner, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1)
        msg_frame.pack(fill="x", pady=16, ipadx=24, ipady=24)
        
        lbl_title = tk.Label(msg_frame, text=title, font=("Segoe UI", 13, "bold"), bg=self.card_bg, fg=self.text_main)
        lbl_title.pack(anchor="w", pady=(0, 8))
        
        lbl_detail = tk.Label(msg_frame, text=detail, font=("Segoe UI", 10), bg=self.card_bg, fg=self.text_muted, wraplength=460, justify="left")
        lbl_detail.pack(anchor="w", pady=(0, 20))
        
        if action:
            RoundedButton(
                msg_frame, 
                text=action[0], 
                command=action[1], 
                bg=self.accent_color, 
                hover_bg=self.accent_hover,
                fg="#0b0f19", 
                radius=12,
                padx=18, 
                pady=10,
                canvas_bg=self.card_bg
            ).pack(anchor="w")

    def _render(self) -> None:
        if self._active_tool is not None:
            self._render_tool(self._active_tool)
            return
        if not self._connected:
            self._message(
                "Sin conexión con el Hub",
                "El servidor local no está activo en este momento. Verificalo e intentá de nuevo.",
                ("Reintentar conexión", self.refresh),
            )
            return
        if not self._tools:
            self._message(
                "No hay herramientas habilitadas",
                "Agregá un plugin y activalo desde la configuración del panel web.",
                ("Abrir administración", lambda: webbrowser.open(f"{WEB_URL}/settings?tab=plugins")),
            )
            return
        shown = filter_tools(self._tools, self.query.get())
        if not shown:
            self._message("Sin resultados", "Ninguna herramienta coincide con los términos de búsqueda.")
            return
        
        self._clear()
        
        for t in shown:
            card = tk.Frame(self.inner, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1)
            card.pack(fill="x", pady=10, ipadx=20, ipady=16)

            top_row = tk.Frame(card, bg=self.card_bg)
            top_row.pack(fill="x", pady=(0, 6))
            
            tk.Label(top_row, text=t.name, font=("Segoe UI", 12, "bold"), bg=self.card_bg, fg=self.text_main).pack(side="left")

            if t.description:
                tk.Label(
                    card, 
                    text=t.description, 
                    font=("Segoe UI", 9), 
                    bg=self.card_bg, 
                    fg=self.text_muted, 
                    wraplength=460, 
                    justify="left"
                ).pack(anchor="w", pady=(0, 12))

            btn_frame = tk.Frame(card, bg=self.card_bg)
            btn_frame.pack(fill="x", pady=(4, 0))
            
            RoundedButton(
                btn_frame, 
                text="Iniciar", 
                command=lambda selected=t: self._open_tool(selected),
                bg="#1f2937",
                hover_bg=self.accent_color,
                fg=self.text_main,
                radius=10,
                padx=16,
                pady=8,
                canvas_bg=self.card_bg
            ).pack(anchor="e")

            def on_enter(e, c=card):
                c.config(highlightbackground=self.accent_color)
            def on_leave(e, c=card):
                c.config(highlightbackground=self.border_color)

            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)
            top_row.bind("<Enter>", on_enter)
            top_row.bind("<Leave>", on_leave)

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
        self.search_frame.pack(fill="x", before=self.body, pady=(0, 24), padx=32)
        self._render()

    def _render_tool(self, tool: Tool) -> None:
        self._clear()
        
        panel = tk.Frame(self.inner, bg=self.bg_color)
        panel.pack(fill="x", pady=10)

        title_row = tk.Frame(panel, bg=self.bg_color)
        title_row.pack(fill="x", pady=(0, 4))
        
        tk.Label(title_row, text=tool.name, font=("Segoe UI", 18, "bold"), bg=self.bg_color, fg=self.text_main).pack(side="left")
        
        if tool.plugin_id == "youtube-dl" and tool.tool_id == "download-video":
            SettingsIconButton(title_row, command=self._open_tool_settings, bg=self.bg_color, hover_bg="#1f2937", fg=self.text_main).pack(side="right")

        tk.Label(panel, text=tool.plugin_name.upper(), font=("Segoe UI", 8, "bold"), bg=self.bg_color, fg=self.accent_color).pack(anchor="w", pady=(0, 20))

        if tool.plugin_id == "youtube-dl" and tool.tool_id == "download-video":
            tk.Label(panel, text="URL de YouTube", font=("Segoe UI", 10, "bold"), bg=self.bg_color, fg=self.text_main).pack(anchor="w", pady=(0, 8))
            self._tool_url = tk.StringVar()
            self._tool_entry = tk.Entry(
                panel,
                textvariable=self._tool_url,
                bg=self.card_bg,
                fg=self.text_main,
                insertbackground=self.text_main,
                relief="flat",
                font=("Segoe UI", 11),
            )
            self._tool_entry.pack(fill="x", ipady=12, ipadx=14, pady=(0, 16))
            self._tool_entry.bind("<Return>", lambda _event: self._download_tool())

            RoundedButton(
                panel,
                text="Descargar",
                command=self._download_tool,
                bg=self.accent_color,
                hover_bg=self.accent_hover,
                fg="#0b0f19",
                radius=12,
                padx=20,
                pady=10,
                canvas_bg=self.bg_color,
            ).pack(anchor="e")
            
            self._download_progressbar = ttk.Progressbar(
                panel,
                mode="determinate",
                maximum=100,
                style="Download.Horizontal.TProgressbar",
            )
            self._download_progressbar.pack(fill="x", pady=(16, 0))
            self._download_progressbar.pack_forget()
            
            self._download_status = tk.StringVar()
            self._download_status_label = tk.Label(
                panel,
                textvariable=self._download_status,
                font=("Segoe UI", 9),
                bg=self.bg_color,
                fg=self.text_muted,
                wraplength=460,
                justify="left",
            )
            self._download_status_label.pack(anchor="w", pady=(8, 0))
            self._tool_entry.focus_set()
        else:
            detail = tool.description or "Esta herramienta todavía no tiene una interfaz nativa en Hub."
            tk.Label(panel, text=detail, font=("Segoe UI", 10), bg=self.bg_color, fg=self.text_muted, wraplength=460, justify="left").pack(anchor="w")

    def _open_tool_settings(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            return
        try:
            self._download_config = fetch_youtube_downloader_settings()
        except BackendError as exc:
            if self._download_status is not None:
                self._download_status.set(str(exc))
            return

        config = self._download_config
        window = tk.Toplevel(self)
        self._settings_window = window
        window.title("Preferencias de descarga")
        window.configure(bg="#ffffff")
        window.transient(self)
        window.resizable(False, False)
        window.geometry("500x500")
        window.protocol("WM_DELETE_WINDOW", lambda: self._close_tool_settings(window))

        settings_bg = "#ffffff"
        settings_fg = "#111111"
        content = tk.Frame(window, bg=settings_bg, padx=24, pady=22)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Preferencias de descarga", font=("Segoe UI", 15, "bold"), bg=settings_bg, fg=settings_fg).pack(anchor="w", pady=(0, 20))

        directory_var = tk.StringVar(value=config["output_directory"])
        tk.Label(content, text="Carpeta de descarga", bg=settings_bg, fg=settings_fg).pack(anchor="w", pady=(0, 6))
        directory_row = tk.Frame(content, bg=settings_bg)
        directory_row.pack(fill="x", pady=(0, 16))
        tk.Entry(directory_row, textvariable=directory_var, state="readonly", readonlybackground="#ffffff", fg=settings_fg, relief="solid", bd=1).pack(side="left", fill="x", expand=True, ipady=9, ipadx=10)

        def choose_directory() -> None:
            selected = filedialog.askdirectory(parent=window, initialdir=directory_var.get(), mustexist=False)
            if selected:
                directory_var.set(selected)

        RoundedButton(directory_row, text="Examinar…", command=choose_directory, bg="#1f2937", hover_bg="#374151", fg="#ffffff", radius=10, padx=12, pady=8, canvas_bg=settings_bg).pack(side="left", padx=(8, 0))

        format_labels = {"mp4": "MP4", "webm": "WEBM", "mov": "MOV", "mp3": "MP3 (solo audio)", "wav": "WAV (solo audio)"}
        quality_labels = {"best": "Máxima disponible", "2160": "2160p (4K)", "1440": "1440p", "1080": "1080p", "720": "720p", "480": "480p"}
        format_var = tk.StringVar(value=format_labels[config["output_format"]])
        quality_var = tk.StringVar(value=quality_labels[config["quality"]])

        tk.Label(content, text="Formato", bg=settings_bg, fg=settings_fg).pack(anchor="w", pady=(0, 6))
        def update_video_options(_value=None) -> None:
            audio_only = format_var.get() in (format_labels["mp3"], format_labels["wav"])
            quality_menu.configure(state="disabled" if audio_only else "normal")

        format_menu = tk.OptionMenu(
            content,
            format_var,
            *format_labels.values(),
            command=update_video_options,
        )
        format_menu.configure(
            bg="#ffffff",
            fg=settings_fg,
            activebackground="#e5e7eb",
            activeforeground=settings_fg,
            anchor="w",
            relief="solid",
            bd=1,
            highlightthickness=0,
        )
        format_menu["menu"].configure(
            bg="#ffffff",
            fg=settings_fg,
            activebackground="#e5e7eb",
            activeforeground=settings_fg,
            font=("Segoe UI", 10),
        )
        format_menu.pack(fill="x", ipady=4, pady=(0, 14))
        tk.Label(content, text="Resolución máxima", bg=settings_bg, fg=settings_fg).pack(anchor="w", pady=(0, 6))
        quality_menu = tk.OptionMenu(content, quality_var, *quality_labels.values())
        quality_menu.configure(
            bg="#ffffff",
            fg=settings_fg,
            activebackground="#e5e7eb",
            activeforeground=settings_fg,
            anchor="w",
            relief="solid",
            bd=1,
            highlightthickness=0,
        )
        quality_menu["menu"].configure(
            bg="#ffffff",
            fg=settings_fg,
            activebackground="#e5e7eb",
            activeforeground=settings_fg,
            font=("Segoe UI", 10),
        )
        quality_menu.pack(fill="x", ipady=4, pady=(0, 14))

        update_video_options()

        def save() -> None:
            values = {
                "output_directory": directory_var.get().strip(),
                "output_format": next(key for key, label in format_labels.items() if label == format_var.get()),
                "quality": next(key for key, label in quality_labels.items() if label == quality_var.get()),
            }
            try:
                self._download_config = save_youtube_downloader_settings(values)
            except BackendError as exc:
                self._settings_status.config(text=str(exc), fg="#b42318")
                return
            self._close_tool_settings(window)
            if self._download_status is not None:
                self._download_status.set("Preferencias guardadas.")
            if self._download_status_label is not None:
                self._download_status_label.config(fg="#38bdf8")

        self._settings_status = tk.Label(content, text="", bg=settings_bg, fg=settings_fg, wraplength=460, justify="left")
        self._settings_status.pack(anchor="w", pady=(0, 8))
        RoundedButton(content, text="Guardar preferencias", command=save, bg=self.accent_color, hover_bg=self.accent_hover, fg="#0b0f19", radius=12, padx=18, pady=10, canvas_bg=settings_bg).pack(anchor="e")

    def _close_tool_settings(self, window: tk.Toplevel) -> None:
        if window.winfo_exists():
            window.destroy()
        self._settings_window = None

    def _watch_download_progress(self, tool_id: str, stop: threading.Event) -> None:
        while not stop.wait(0.75):
            try:
                task = next((
                    row for row in fetch_tasks()
                    if row["plugin_id"] == "youtube-dl" and row["operation"] == "download-video" and row["status"] == "running"
                ), None)
            except BackendError:
                continue
            if task is not None:
                self._results.put(("download_progress", (tool_id, task.get("progress"), task.get("message") or "Descargando video…")))

    def _download_tool(self) -> None:
        if self._downloading or self._tool_url is None or self._download_status is None:
            return
        url = self._tool_url.get().strip()
        if not url:
            self._download_status.set("Ingresa una URL de YouTube.")
            return
        tool = self._active_tool
        if tool is None:
            return

        self._downloading = True
        self._download_status.set("Descargando video…")
        if self._download_progressbar is not None:
            self._download_progressbar.configure(value=0)
            self._download_progressbar.pack(fill="x", pady=(16, 0), before=self._download_status_label)
        if self._download_status_label is not None:
            self._download_status_label.config(fg="#38bdf8")

        def work() -> None:
            stop_watcher = threading.Event()
            watcher = threading.Thread(target=self._watch_download_progress, args=(tool.plugin_id, stop_watcher), daemon=True)
            watcher.start()
            try:
                config = fetch_youtube_downloader_settings()
                path = download_youtube_video(url, download_dir=Path(config["output_directory"]))
                self._results.put(("download_ok", (tool.plugin_id, path)))
            except BackendError as exc:
                self._results.put(("download_error", (tool.plugin_id, str(exc))))
            finally:
                stop_watcher.set()
                watcher.join(timeout=2)

        threading.Thread(target=work, daemon=True).start()

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
                self._connected = kind == "ok"
                self._tools = payload if kind == "ok" else []
                n = len(self._tools)
                self.status.config(text=f"● {n} {'herramienta' if n == 1 else 'herramientas'}" if self._connected else "● Sin conexión")
                self._render()
            elif kind == "download_progress":
                tool_id, progress, message = payload
                if self._active_tool and self._active_tool.plugin_id == tool_id and self._download_status is not None:
                    self._download_status.set(message)
                    if self._download_status_label is not None:
                        self._download_status_label.config(fg="#38bdf8")
                    if self._download_progressbar is not None and self._download_progressbar.winfo_manager() == "pack":
                        self._download_progressbar.configure(value=(progress or 0) * 100)
            else:
                self._downloading = False
                tool_id, result = payload
                if self._active_tool and self._active_tool.plugin_id == tool_id and self._download_status is not None:
                    if kind == "download_ok":
                        self._download_status.set(f"Video guardado en: {result}")
                        if self._download_status_label is not None:
                            self._download_status_label.config(fg="#38bdf8")
                        if self._download_progressbar is not None:
                            self._download_progressbar.configure(value=100)
                    else:
                        self._download_status.set(result)
                        if self._download_status_label is not None:
                            self._download_status_label.config(fg="#f87171")
        self.after(100, self._poll)


def main() -> None:
    LauncherApp().mainloop()


if __name__ == "__main__":
    main()