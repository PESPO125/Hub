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
from tkinter import ttk
from tempfile import NamedTemporaryFile

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


def download_youtube_video(
    url: str,
    api_url: str | None = None,
    download_dir: Path | None = None,
    timeout: float = 1800,
) -> Path:
    api_url = (api_url or API_URL).rstrip("/")
    req = urllib.request.Request(
        f"{api_url}/api/v1/plugins/youtube-dl/download",
        data=json.dumps({"url": url}).encode("utf-8"),
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
    """Botón personalizado con esquinas verdaderamente redondeadas y efectos hover fluidos."""
    def __init__(self, parent, text, command, bg="#21262d", hover_bg="#30363d", fg="#f0f6fc", font=("Segoe UI", 10, "bold"), radius=8, padx=16, pady=8, canvas_bg="#0f1117"):
        self.font = font
        self.text = text
        self.command = command
        self.bg = bg
        self.hover_bg = hover_bg
        self.fg = fg
        self.radius = radius
        
        # Crear etiqueta temporal para medir texto
        dummy = tk.Label(parent, text=text, font=font)
        w = dummy.winfo_reqwidth() + padx * 2
        h = dummy.winfo_reqheight() + pady * 2
        dummy.destroy()

        super().__init__(parent, width=w, height=h, bg=canvas_bg, highlightthickness=0, cursor="hand2")
        
        self.w = w
        self.h = h
        
        self._draw(self.bg)
        
        # Eventos
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", lambda e: self._draw(self.hover_bg))
        self.bind("<Leave>", lambda e: self._draw(self.bg))

    def _draw(self, color):
        self.delete("all")
        r = self.radius
        w = self.w
        h = self.h
        
        # Dibujar formas redondeadas con el canvas
        self.create_arc(0, 0, r*2, r*2, start=90, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, 0, w, r*2, start=0, extent=90, fill=color, outline=color)
        self.create_arc(0, h-r*2, r*2, h, start=180, extent=90, fill=color, outline=color)
        self.create_arc(w-r*2, h-r*2, w, h, start=270, extent=90, fill=color, outline=color)
        
        self.create_rectangle(r, 0, w-r, h, fill=color, outline=color)
        self.create_rectangle(0, r, w, h-r, fill=color, outline=color)
        
        self.create_text(w/2, h/2, text=self.text, fill=self.fg, font=self.font)


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Hub  --  Cooking")
        self.geometry("580x740")
        self.minsize(480, 500)
        
        # Paleta Dark Modern
        self.bg_color = "#0f1117"
        self.card_bg = "#161b22"
        self.border_color = "#30363d"
        self.text_main = "#f0f6fc"
        self.text_muted = "#8b949e"
        self.accent_color = "#8b5cf6"
        self.accent_hover = "#7c3aed"
        
        self.configure(bg=self.bg_color)

        self._tools: list[Tool] = []
        self._active_tool: Tool | None = None
        self._tool_url: tk.StringVar | None = None
        self._download_status: tk.StringVar | None = None
        self._download_status_label: tk.Label | None = None
        self._downloading = False
        self._connected = False
        self._results: queue.Queue = queue.Queue()
        
        self._setup_styles()
        self._build()
        self.after(100, self._poll)
        self.refresh()

    def _setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=self.bg_color, foreground=self.text_main, font=("Segoe UI", 10))
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.text_main)
        style.configure("Muted.TLabel", background=self.bg_color, foreground=self.text_muted, font=("Segoe UI", 9))

    def _build(self) -> None:
        pad = {"padx": 28}
        
        # Cabecera
        head = ttk.Frame(self)
        head.pack(fill="x", pady=(28, 20), **pad)
        ttk.Label(head, text="HUB", font=("Segoe UI", 22, "bold")).pack(side="left")
        self.status = ttk.Label(head, text="Conectando…", style="Muted.TLabel")
        self.status.pack(side="right", pady=8)

        # Barra de búsqueda
        self.search_frame = tk.Frame(self, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1, bd=0)
        self.search_frame.pack(fill="x", pady=(0, 24), **pad)
        
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._render())
        
        search_entry = tk.Entry(
            self.search_frame, 
            textvariable=self.query, 
            bg=self.card_bg, 
            fg=self.text_main, 
            insertbackground=self.text_main, 
            relief="flat", 
            font=("Segoe UI", 11)
        )
        search_entry.pack(fill="x", ipady=12, ipadx=16)
        search_entry.focus_set()

        # Contenedor principal de la lista (Sin barra de scroll lateral)
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, **pad)
        
        self.canvas = tk.Canvas(self.body, highlightthickness=0, bg=self.bg_color)
        self.inner = ttk.Frame(self.canvas, style="TFrame")
        
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        
        self.canvas.pack(side="left", fill="both", expand=True)

        # Pie de página espaciado con botones redondeados reales
        foot = ttk.Frame(self)
        foot.pack(fill="x", pady=24, **pad)
        
        RoundedButton(
            foot, 
            text="Refresh", 
            command=self.refresh,
            bg="#21262d",
            hover_bg="#30363d",
            fg=self.text_main,
            radius=6,
            padx=16,
            pady=10,
            canvas_bg=self.bg_color
        ).pack(side="left")

        RoundedButton(
            foot, 
            text="Panel web", 
            command=lambda: webbrowser.open(WEB_URL),
            bg=self.accent_color,
            hover_bg=self.accent_hover,
            fg="#ffffff",
            radius=6,
            padx=16,
            pady=10,
            canvas_bg=self.bg_color
        ).pack(side="right")

    def _clear(self) -> None:
        for w in self.inner.winfo_children():
            w.destroy()

    def _message(self, title: str, detail: str, action: tuple[str, callable] | None = None) -> None:
        self._clear()
        msg_frame = tk.Frame(self.inner, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1)
        msg_frame.pack(fill="x", pady=16, ipadx=24, ipady=24)
        
        lbl_title = tk.Label(msg_frame, text=title, font=("Segoe UI", 13, "bold"), bg=self.card_bg, fg=self.text_main)
        lbl_title.pack(anchor="w", pady=(0, 8))
        
        lbl_detail = tk.Label(msg_frame, text=detail, font=("Segoe UI", 10), bg=self.card_bg, fg=self.text_muted, wraplength=440, justify="left")
        lbl_detail.pack(anchor="w", pady=(0, 20))
        
        if action:
            RoundedButton(
                msg_frame, 
                text=action[0], 
                command=action[1], 
                bg=self.accent_color, 
                hover_bg=self.accent_hover,
                fg="#ffffff", 
                radius=6,
                padx=16, 
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
            card.pack(fill="x", pady=12, ipadx=18, ipady=14)

            top_row = tk.Frame(card, bg=self.card_bg)
            top_row.pack(fill="x", pady=(0, 8))
            
            tk.Label(top_row, text=t.name, font=("Segoe UI", 11, "bold"), bg=self.card_bg, fg=self.text_main).pack(side="left")
            tk.Label(top_row, text=t.plugin_name.upper(), font=("Segoe UI", 8, "bold"), bg=self.card_bg, fg=self.accent_color).pack(side="right")

            if t.description:
                tk.Label(
                    card, 
                    text=t.description, 
                    font=("Segoe UI", 9), 
                    bg=self.card_bg, 
                    fg=self.text_muted, 
                    wraplength=440, 
                    justify="left"
                ).pack(anchor="w", pady=(0, 14))

            btn_frame = tk.Frame(card, bg=self.card_bg)
            btn_frame.pack(fill="x", pady=(4, 0))
            
            RoundedButton(
                btn_frame, 
                text="Iniciar", 
                command=lambda selected=t: self._open_tool(selected),
                bg="#21262d",
                hover_bg=self.accent_color,
                fg=self.text_main,
                radius=6,
                padx=12,
                pady=6,
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
        self._render_tool(tool)

    def _close_tool(self) -> None:
        self._active_tool = None
        self.search_frame.pack(fill="x", before=self.body, pady=(0, 24), padx=28)
        self._render()

    def _render_tool(self, tool: Tool) -> None:
        self._clear()
        panel = tk.Frame(self.inner, bg=self.card_bg, highlightbackground=self.border_color, highlightthickness=1)
        panel.pack(fill="x", pady=12, ipadx=22, ipady=22)

        RoundedButton(
            panel,
            text="← Volver a herramientas",
            command=self._close_tool,
            bg="#21262d",
            hover_bg="#30363d",
            fg=self.text_main,
            radius=6,
            padx=12,
            pady=6,
            canvas_bg=self.card_bg,
        ).pack(anchor="w", pady=(0, 22))

        tk.Label(panel, text=tool.name, font=("Segoe UI", 16, "bold"), bg=self.card_bg, fg=self.text_main).pack(anchor="w")
        tk.Label(panel, text=tool.plugin_name, font=("Segoe UI", 9), bg=self.card_bg, fg=self.text_muted).pack(anchor="w", pady=(4, 18))

        if tool.plugin_id == "youtube-dl" and tool.tool_id == "download-video":
            tk.Label(panel, text="URL de YouTube", font=("Segoe UI", 10, "bold"), bg=self.card_bg, fg=self.text_main).pack(anchor="w", pady=(0, 8))
            self._tool_url = tk.StringVar()
            entry = tk.Entry(
                panel,
                textvariable=self._tool_url,
                bg="#0f1117",
                fg=self.text_main,
                insertbackground=self.text_main,
                relief="flat",
                font=("Segoe UI", 11),
            )
            entry.pack(fill="x", ipady=10, ipadx=12)
            entry.bind("<Return>", lambda _event: self._download_tool())

            RoundedButton(
                panel,
                text="Descargar video",
                command=self._download_tool,
                bg=self.accent_color,
                hover_bg=self.accent_hover,
                fg="#ffffff",
                radius=6,
                padx=16,
                pady=9,
                canvas_bg=self.card_bg,
            ).pack(anchor="e", pady=(14, 0))
            self._download_status = tk.StringVar()
            self._download_status_label = tk.Label(
                panel,
                textvariable=self._download_status,
                font=("Segoe UI", 9),
                bg=self.card_bg,
                fg=self.text_muted,
                wraplength=440,
                justify="left",
            )
            self._download_status_label.pack(anchor="w", pady=(12, 0))
            entry.focus_set()
        else:
            detail = tool.description or "Esta herramienta todavía no tiene una interfaz nativa en Hub."
            tk.Label(panel, text=detail, font=("Segoe UI", 10), bg=self.card_bg, fg=self.text_muted, wraplength=440, justify="left").pack(anchor="w")

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
        if self._download_status_label is not None:
            self._download_status_label.config(fg="#22c55e")

        def work() -> None:
            try:
                path = download_youtube_video(url)
                self._results.put(("download_ok", (tool.plugin_id, path)))
            except BackendError as exc:
                self._results.put(("download_error", (tool.plugin_id, str(exc))))

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
            else:
                self._downloading = False
                tool_id, result = payload
                if self._active_tool and self._active_tool.plugin_id == tool_id and self._download_status is not None:
                    if kind == "download_ok":
                        self._download_status.set(f"Video guardado en: {result}")
                        if self._download_status_label is not None:
                            self._download_status_label.config(fg="#22c55e")
                    else:
                        self._download_status.set(result)
                        if self._download_status_label is not None:
                            self._download_status_label.config(fg="#f85149")
        self.after(100, self._poll)


def main() -> None:
    LauncherApp().mainloop()


if __name__ == "__main__":
    main()