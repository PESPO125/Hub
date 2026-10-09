import { render } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { QueryClient } from "@tanstack/react-query";
import { Providers } from "@/app/providers";
import { createTestRouter } from "@/app/router";

export const emptyCatalog = { items: [], total: 0, categories: [], installed_total: 0 };

export const plugin = (over: Record<string, unknown> = {}) => ({
  id: "demo-tool", folder: "demo", name: "Demo Tool", description: "Una herramienta", version: "1.0", contract_version: 1,
  categories: ["utilities"], icon: "wrench", integration_type: "subprocess", tools: [{ id: "run", name: "Ejecutar", description: "" }],
  capabilities: [], permissions: ["files.read"], config_requirements: [], platform: { min_version: "1.0", max_version: null },
  status: "available", admin_state: "disabled", enabled: false, executable: false, executable_reason: null, problems: [], favorite: false, ...over,
});

type Routes = Record<string, { status?: number; body: unknown }>;

/** Simula el backend a nivel fetch (los tests de UI no dependen de datos falsos en el código de producción). */
export function mockApi(routes: Routes) {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const path = String(input).replace("/api/v1", "");
    const key = Object.keys(routes).find((k) => path === k || path.startsWith(k + "?"));
    if (!key) return new Response(JSON.stringify({ error: { code: "not_found", message: "no mock" } }), { status: 404 });
    const r = routes[key]!;
    return new Response(JSON.stringify(r.body), { status: r.status ?? 200 });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const baseRoutes = (): Routes => ({
  "/catalog": { body: emptyCatalog },
  "/tasks": { body: { items: [], total: 0, active_count: 0, limit: 50, offset: 0 } },
  "/files": { body: { items: [], total: 0, limit: 50, offset: 0 } },
  "/settings": { body: { theme: "system" } },
  "/app/info": { body: { name: "Hub", version: "1.2", api_version: "v1", environment: "test", untrusted_plugins_allowed: false, mode: "single_user_local" } },
  "/plugins": { body: { items: [], total: 0, limit: 100, offset: 0 } },
  "/plugins/youtube-dl/config": { body: { output_directory: "C:/Users/test/Downloads", output_format: "mp4", quality: "best" } },
});

export function renderApp(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<Providers client={client}><RouterProvider router={createTestRouter(path)} /></Providers>);
}
