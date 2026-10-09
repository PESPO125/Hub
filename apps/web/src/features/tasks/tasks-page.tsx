import { ListChecks } from "lucide-react";
import { useState } from "react";
import { TaskStatusBadge } from "@/components/shared/status-badges";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { cn, formatDate } from "@/lib/utils";
import { useCancelTask, useTasks } from "@/services/queries";
import type { Task, TaskStatus } from "@/types/api";

const FILTERS: { value: TaskStatus | ""; label: string }[] = [
  { value: "", label: "Todas" }, { value: "pending", label: "En espera" }, { value: "running", label: "En ejecución" },
  { value: "completed", label: "Completadas" }, { value: "failed", label: "Fallidas" }, { value: "cancelled", label: "Canceladas" },
];

export function TasksPage() {
  const [status, setStatus] = useState<TaskStatus | "">("");
  const [toCancel, setToCancel] = useState<Task | null>(null);
  const { data, isPending, isError, error, refetch } = useTasks(status || undefined);
  const cancel = useCancelTask();
  const toast = useToast();

  return (
    <>
      <PageHeader title="Tareas" description="Operaciones en curso y su historial. Se actualizan automáticamente." />
      <div className="mb-4 flex flex-wrap gap-2" role="group" aria-label="Filtrar por estado">
        {FILTERS.map((f) => (
          <button key={f.value} type="button" aria-pressed={status === f.value} onClick={() => setStatus(f.value)}
            className={cn("rounded-full border px-3 py-1 text-xs font-medium", status === f.value ? "border-primary bg-primary text-primary-foreground" : "bg-card text-muted-foreground hover:bg-muted")}>
            {f.label}
          </button>
        ))}
      </div>

      {isPending ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-16" />)}</div>
        : isError ? <ErrorState error={error} onRetry={() => refetch()} />
        : data.items.length === 0 ? (
          <EmptyState icon={ListChecks} title={status ? "No hay tareas con este estado" : "Todavía no hay tareas"}>
            {status ? "Probá con otro filtro." : "Cuando una herramienta realice una operación larga, vas a ver acá su progreso y su resultado."}
          </EmptyState>
        ) : (
          <ul className="divide-y rounded-lg border bg-card shadow-card">
            {data.items.map((t) => (
              <li key={t.id} className="flex flex-wrap items-center gap-3 p-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{t.operation} <span className="font-normal text-muted-foreground">· {t.plugin_id}</span></p>
                  <p className="truncate text-xs text-muted-foreground">{t.message ?? t.error?.message ?? formatDate(t.created_at)}</p>
                  {t.status === "running" && t.progress !== null && (
                    <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(t.progress * 100)} className="mt-2 h-1.5 w-full max-w-xs overflow-hidden rounded-full bg-muted">
                      <div className="h-full bg-primary transition-all" style={{ width: `${Math.round(t.progress * 100)}%` }} />
                    </div>
                  )}
                </div>
                <TaskStatusBadge status={t.status} />
                {(t.status === "pending" || t.status === "running") && (
                  <Button variant="outline" size="sm" disabled={t.cancel_requested} onClick={() => setToCancel(t)}>{t.cancel_requested ? "Cancelando…" : "Cancelar"}</Button>
                )}
              </li>
            ))}
          </ul>
        )}

      <ConfirmDialog open={toCancel !== null} title="¿Cancelar esta tarea?" confirmLabel="Cancelar tarea" destructive loading={cancel.isPending}
        description="Se solicitará detener la operación. El trabajo realizado hasta ahora podría perderse."
        onClose={() => setToCancel(null)}
        onConfirm={() => toCancel && cancel.mutate(toCancel.id, {
          onSuccess: () => { toast.success("Cancelación solicitada."); setToCancel(null); },
          onError: (e) => { toast.error(e); setToCancel(null); },
        })} />
    </>
  );
}
