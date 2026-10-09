import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { baseRoutes, mockApi, plugin, renderApp } from "@/test/utils";

afterEach(() => vi.unstubAllGlobals());

describe("navegación", () => {
  it("muestra todas las secciones del sidebar y navega", async () => {
    mockApi(baseRoutes());
    renderApp("/");
    const nav = screen.getByRole("navigation", { name: "Navegación principal" });
    for (const name of ["Inicio", "Todas las herramientas", "Favoritos", "Tareas", "Archivos y resultados", "Configuración"]) {
      expect(within(nav).getByRole("link", { name })).toBeInTheDocument();
    }
    await userEvent.click(within(nav).getByRole("link", { name: "Tareas" }));
    expect(await screen.findByRole("heading", { name: "Tareas" })).toBeInTheDocument();
  });

  it("contrae y expande la barra lateral", async () => {
    mockApi(baseRoutes());
    renderApp("/");
    await userEvent.click(screen.getByRole("button", { name: "Contraer barra lateral" }));
    expect(screen.getByRole("button", { name: "Expandir barra lateral" })).toHaveAttribute("aria-expanded", "false");
  });

  it("ruta inexistente muestra 404 útil", async () => {
    mockApi(baseRoutes());
    renderApp("/nada");
    expect(await screen.findByText("Página no encontrada")).toBeInTheDocument();
  });
});

describe("catálogo vacío", () => {
  it("inicio y catálogo explican cómo agregar plugins, sin herramientas inventadas", async () => {
    mockApi(baseRoutes());
    renderApp("/tools");
    expect(await screen.findByText("Todavía no hay herramientas instaladas")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Administrar plugins/ })).toHaveAttribute("href", "/settings?tab=plugins");
    expect(screen.queryAllByRole("listitem").length).toBe(0);
  });

  it("el inicio muestra estado vacío de tareas y resultados", async () => {
    mockApi(baseRoutes());
    renderApp("/");
    expect(await screen.findByText("Todavía no hay herramientas instaladas")).toBeInTheDocument();
    expect(await screen.findByText("No hay tareas en ejecución.")).toBeInTheDocument();
    expect(await screen.findByText("Todavía no hay resultados generados.")).toBeInTheDocument();
  });
});

describe("catálogo con datos reales del backend", () => {
  it("renderiza tarjetas y alterna favorito", async () => {
    const fetchMock = mockApi({
      ...baseRoutes(),
      "/catalog": { body: { items: [plugin()], total: 1, categories: ["utilities"], installed_total: 1 } },
      "/favorites/demo-tool": { body: { favorites: ["demo-tool"] } },
    });
    renderApp("/tools");
    expect(await screen.findByRole("link", { name: "Demo Tool" })).toHaveAttribute("href", "/tools/demo-tool");
    await userEvent.click(screen.getByRole("button", { name: "Agregar Demo Tool a favoritos" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/favorites/demo-tool", expect.objectContaining({ method: "PUT" })));
  });

  it("sin resultados de búsqueda permite limpiar filtros", async () => {
    mockApi({ ...baseRoutes(), "/catalog": { body: { items: [], total: 0, categories: ["utilities"], installed_total: 2 } } });
    renderApp("/tools?q=zzz");
    expect(await screen.findByText("Sin resultados")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Limpiar filtros" })).toBeInTheDocument();
  });
});

describe("detalle de plugin", () => {
  it("muestra el formulario de descarga en YouTube Downloader", async () => {
    mockApi({
      ...baseRoutes(),
      "/plugins/youtube-dl": { body: plugin({ id: "youtube-dl", name: "YouTube Downloader", enabled: true, admin_state: "enabled" }) },
    });
    renderApp("/tools/youtube-dl");
    expect(await screen.findByRole("heading", { name: "YouTube Downloader" })).toBeInTheDocument();
    expect(screen.getByText("Formato del plugin")).toBeInTheDocument();
    const urlInput = screen.getByRole("textbox", { name: "URL de YouTube" });
    const downloadButton = screen.getByRole("button", { name: /Descargar video/ });
    expect(downloadButton).toBeDisabled();
    await userEvent.type(urlInput, "https://youtu.be/example");
    expect(downloadButton).toBeEnabled();
  });

  it("muestra permisos y pide confirmación al deshabilitar", async () => {
    const fetchMock = mockApi({
      ...baseRoutes(),
      "/plugins/demo-tool": { body: plugin({ enabled: true, admin_state: "enabled", executable_reason: "Plugins no confiables deshabilitados." }) },
      "/plugins/demo-tool/state": { body: plugin() },
    });
    renderApp("/tools/demo-tool");
    expect(await screen.findByRole("heading", { name: "Demo Tool" })).toBeInTheDocument();
    expect(screen.getByText(/Leer archivos que le entregues/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Deshabilitar" }));
    const dialog = await screen.findByRole("dialog", { name: /¿Deshabilitar Demo Tool\?/ });
    await userEvent.click(within(dialog).getByRole("button", { name: "Deshabilitar" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/plugins/demo-tool/state", expect.objectContaining({ method: "PATCH" })));
  });

  it("plugin inexistente muestra error comprensible", async () => {
    mockApi({ ...baseRoutes(), "/plugins/x": { status: 404, body: { error: { code: "plugin_not_found", message: "Plugin no encontrado." } } } });
    renderApp("/tools/x");
    expect(await screen.findByRole("alert")).toHaveTextContent(/No encontramos esta herramienta/);
  });
});

describe("errores y carga", () => {
  it("backend caído: mensaje claro y reintento", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("fail"); }));
    renderApp("/tools");
    expect(await screen.findByText("Sin conexión con el backend")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reintentar/ })).toBeInTheDocument();
  });

  it("error estructurado de la API incluye el ID de solicitud", async () => {
    mockApi({ ...baseRoutes(), "/files": { status: 500, body: { error: { code: "internal_error", message: "Error interno del servidor.", request_id: "abc123" } } } });
    renderApp("/files");
    expect(await screen.findByText("Error interno del servidor.")).toBeInTheDocument();
    expect(screen.getByText(/abc123/)).toBeInTheDocument();
  });

  it("muestra esqueletos mientras carga", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const { container } = renderApp("/files");
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
  });
});

describe("tareas y configuración", () => {
  it("lista tareas reales con progreso y permite cancelar con confirmación", async () => {
    const task = { id: "t1", plugin_id: "demo-tool", operation: "convertir", status: "running", progress: 0.4, message: null, error: null, cancel_requested: false, timeout_seconds: null, created_at: "2026-10-08T10:00:00Z", finished_at: null };
    const fetchMock = mockApi({ ...baseRoutes(), "/tasks": { body: { items: [task], total: 1, active_count: 1, limit: 50, offset: 0 } }, "/tasks/t1/cancel": { body: task } });
    renderApp("/tasks");
    expect(await screen.findByRole("progressbar")).toHaveAttribute("aria-valuenow", "40");
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancelar tarea" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/tasks/t1/cancel", expect.objectContaining({ method: "POST" })));
  });

  it("cambiar el tema llama a la API", async () => {
    const fetchMock = mockApi({ ...baseRoutes(), "/settings": { body: { theme: "system" } } });
    renderApp("/settings");
    await userEvent.click(await screen.findByRole("radio", { name: "Oscuro" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith("/api/v1/settings", expect.objectContaining({ method: "PUT" })));
  });

  it("administración de plugins: estado vacío y plugin inválido con su causa", async () => {
    mockApi(baseRoutes());
    renderApp("/settings?tab=plugins");
    expect(await screen.findByText("No se encontraron plugins")).toBeInTheDocument();
  });

  it("plugin inválido no se puede habilitar y muestra su problema", async () => {
    const bad = plugin({ id: "invalid:x", name: "x", status: "invalid", version: null, problems: ["plugin.json no es JSON válido."] });
    mockApi({ ...baseRoutes(), "/plugins": { body: { items: [bad], total: 1, limit: 100, offset: 0 } } });
    renderApp("/settings?tab=plugins");
    expect(await screen.findByText("plugin.json no es JSON válido.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Habilitar x" })).toBeDisabled();
  });
});
