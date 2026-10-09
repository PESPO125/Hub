export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public requestId?: string | null,
  ) {
    super(message);
  }
  get isNetwork() { return this.status === 0; }
}

const BASE = "/api/v1";

async function responseError(res: Response): Promise<ApiError> {
  let code = "http_error", message = `Error ${res.status}`, rid: string | null = null;
  try {
    const body = await res.json();
    code = body.error?.code ?? code; message = body.error?.message ?? message; rid = body.error?.request_id ?? null;
  } catch { /* cuerpo no JSON (p. ej. proxy sin backend) */ }
  return new ApiError(res.status, code, message, rid);
}

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const { json, headers, ...rest } = init;
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...rest,
      headers: { Accept: "application/json", ...(json !== undefined ? { "Content-Type": "application/json" } : {}), ...headers },
      body: json !== undefined ? JSON.stringify(json) : rest.body,
    });
  } catch {
    throw new ApiError(0, "network_error", "No se pudo conectar con el servidor de Hub. ¿Está en ejecución el backend?");
  }
  if (!res.ok) throw await responseError(res);
  return (await res.json()) as T;
}

export async function downloadYoutubeVideo(url: string): Promise<void> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/plugins/youtube-dl/download`, {
      method: "POST",
      headers: { Accept: "application/octet-stream", "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
  } catch {
    throw new ApiError(0, "network_error", "No se pudo conectar con el servidor de Hub. ¿Está en ejecución el backend?");
  }
  if (!res.ok) throw await responseError(res);

  const filename = res.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/i)?.[1] ?? "video-youtube";
  const objectUrl = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
