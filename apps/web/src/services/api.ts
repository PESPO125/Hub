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
  if (!res.ok) {
    let code = "http_error", message = `Error ${res.status}`, rid: string | null = null;
    try {
      const body = await res.json();
      code = body.error?.code ?? code; message = body.error?.message ?? message; rid = body.error?.request_id ?? null;
    } catch { /* cuerpo no JSON (p. ej. proxy sin backend) */ }
    throw new ApiError(res.status, code, message, rid);
  }
  return (await res.json()) as T;
}
