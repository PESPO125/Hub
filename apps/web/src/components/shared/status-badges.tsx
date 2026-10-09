import { Badge } from "@/components/ui/badge";
import type { Plugin, TaskStatus } from "@/types/api";

export function PluginStatusBadge({ plugin }: { plugin: Plugin }) {
  if (plugin.status === "invalid") return <Badge tone="danger">Inválido</Badge>;
  if (plugin.status === "incompatible") return <Badge tone="warning">Incompatible</Badge>;
  return plugin.enabled ? <Badge tone="success">Habilitado</Badge> : <Badge>Deshabilitado</Badge>;
}

const TASK: Record<TaskStatus, [string, "neutral" | "primary" | "success" | "danger" | "warning"]> = {
  pending: ["En espera", "neutral"], running: ["En ejecución", "primary"], completed: ["Completada", "success"],
  failed: ["Fallida", "danger"], cancelled: ["Cancelada", "warning"],
};
export function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const [label, tone] = TASK[status];
  return <Badge tone={tone}>{label}</Badge>;
}
