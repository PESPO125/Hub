import { FileArchive, ListChecks } from "lucide-react";
import { Link } from "react-router-dom";
import { NoPluginsState } from "@/components/shared/no-plugins";
import { PluginGrid } from "@/components/shared/plugin-grid";
import { TaskStatusBadge } from "@/components/shared/status-badges";
import { ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { formatBytes } from "@/lib/utils";
import { useCatalog, useFiles, useTasks } from "@/services/queries";

function Panel({ title, to, children }: { title: string; to: string; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border bg-card p-4 shadow-card">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        <Link to={to} className="text-xs text-primary hover:underline">Ver todo</Link>
      </div>
      {children}
    </section>
  );
}

export function DashboardPage() {
  const catalog = useCatalog();
  const tasks = useTasks(undefined, 5);
  const files = useFiles();

  const favorites = catalog.data?.items.filter((p) => p.favorite) ?? [];
  const rest = catalog.data?.items.filter((p) => !p.favorite).slice(0, 6) ?? [];
  const running = tasks.data?.items.filter((t) => t.status === "pending" || t.status === "running") ?? [];

  return (
    <>
      <PageHeader title="Inicio" description="Tus herramientas, tareas y resultados en un solo lugar." />

      {catalog.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-36" />)}</div>
      ) : catalog.isError ? (
        <ErrorState error={catalog.error} onRetry={() => catalog.refetch()} />
      ) : catalog.data.installed_total === 0 ? (
        <NoPluginsState />
      ) : (
        <div className="space-y-6">
          {favorites.length > 0 && (<section><h2 className="mb-3 text-sm font-semibold">Favoritas</h2><PluginGrid plugins={favorites} /></section>)}
          {rest.length > 0 && (
            <section>
              <div className="mb-3 flex items-center justify-between"><h2 className="text-sm font-semibold">Herramientas</h2><Link to="/tools" className="text-xs text-primary hover:underline">Ver todas ({catalog.data.installed_total})</Link></div>
              <PluginGrid plugins={rest} />
            </section>
          )}
        </div>
      )}

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <Panel title="Tareas en curso" to="/tasks">
          {tasks.isPending ? <Skeleton className="h-12" /> : tasks.isError ? <p className="text-sm text-destructive">No se pudieron cargar las tareas.</p> :
            running.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground"><ListChecks className="h-4 w-4" aria-hidden />No hay tareas en ejecución.</p>
            ) : (
              <ul className="space-y-2">{running.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{t.operation} · {t.plugin_id}</span><TaskStatusBadge status={t.status} /></li>
              ))}</ul>
            )}
        </Panel>
        <Panel title="Resultados recientes" to="/files">
          {files.isPending ? <Skeleton className="h-12" /> : files.isError ? <p className="text-sm text-destructive">No se pudieron cargar los archivos.</p> :
            files.data.items.length === 0 ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground"><FileArchive className="h-4 w-4" aria-hidden />Todavía no hay resultados generados.</p>
            ) : (
              <ul className="space-y-2">{files.data.items.slice(0, 5).map((f) => (
                <li key={f.id} className="flex items-center justify-between gap-2 text-sm"><span className="truncate">{f.display_name}</span><span className="shrink-0 text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span></li>
              ))}</ul>
            )}
        </Panel>
      </div>
    </>
  );
}
