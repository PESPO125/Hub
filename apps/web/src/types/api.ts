// Espejo de las respuestas de /api/v1. Pendiente: generarlo desde packages/contracts/api/openapi.json.
export type PluginStatus = "available" | "incompatible" | "invalid";
export type TaskStatus = "pending" | "running" | "completed" | "failed" | "cancelled";
export type Theme = "light" | "dark" | "system";

export interface Plugin {
  id: string;
  folder: string;
  name: string;
  description: string;
  version: string | null;
  contract_version: number | null;
  categories: string[];
  icon: string;
  integration_type: "python_inprocess" | "subprocess" | "remote_api" | null;
  tools: { id: string; name: string; description: string }[];
  capabilities: string[];
  permissions: string[];
  config_requirements: string[];
  platform: { min_version: string; max_version: string | null } | null;
  status: PluginStatus;
  admin_state: "enabled" | "disabled";
  enabled: boolean;
  executable: boolean;
  executable_reason: string | null;
  problems: string[];
  favorite: boolean;
}

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Catalog { items: Plugin[]; total: number; categories: string[]; installed_total: number }

export interface Task {
  id: string; plugin_id: string; operation: string; status: TaskStatus; progress: number | null;
  message: string | null; error: { code?: string; message?: string } | null; cancel_requested: boolean;
  timeout_seconds: number | null; created_at: string; finished_at: string | null;
}
export interface TaskPage extends Page<Task> { active_count: number }

export interface StoredFile {
  id: string; task_id: string | null; display_name: string; size_bytes: number;
  mime_type: string | null; created_at: string; expires_at: string | null;
}

export interface AppInfo {
  name: string; version: string; api_version: string; environment: string;
  untrusted_plugins_allowed: boolean; mode: string;
}
export interface Diagnostics {
  database: { ok: boolean; engine: string };
  storage: { ok: boolean };
  plugins: { directory_exists: boolean; counts: Record<PluginStatus, number> };
}
