import { ArrowLeft, Info, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { FavoriteButton } from "@/components/shared/plugin-card";
import { Section } from "@/components/shared/section";
import { PluginStatusBadge } from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { usePluginToggle } from "@/hooks/use-plugin-toggle";
import { resolveIcon } from "@/lib/icons";
import { ApiError } from "@/services/api";
import { usePlugin } from "@/services/queries";
import type { Plugin } from "@/types/api";
import { YoutubeDownloader } from "./youtube-downloader";

const PERMISSION_LABELS: Record<string, string> = {
  "files.read": "Leer archivos que le entregues",
  "files.write": "Crear archivos de resultado",
  "network.outbound": "Conectarse a internet",
  "process.spawn": "Ejecutar procesos del sistema",
  "config.read": "Leer su propia configuración",
};

const Row = ({ k, v }: { k: string; v: ReactNode }) => (
  <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">{k}</dt><dd className="text-right">{v}</dd></div>
);

function Body({ plugin }: { plugin: Plugin }) {
  const { apply, confirming, setConfirming, isPending } = usePluginToggle(plugin);
  const Icon = resolveIcon(plugin.icon);
  const usable = plugin.status === "available";
  const { platform } = plugin;

  return (
    <>
      <div className="mb-6 flex flex-wrap items-start gap-4">
        <div className="flex h-14 w-14 items-center justify-center rounded-lg bg-primary/10 text-primary"><Icon className="h-7 w-7" aria-hidden /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">{plugin.name}</h1>
            <PluginStatusBadge plugin={plugin} />
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{plugin.version && `v${plugin.version} · `}{plugin.description || "Sin descripción."}</p>
        </div>
        <div className="flex items-center gap-2">
          {usable && <FavoriteButton plugin={plugin} />}
          {usable && (plugin.enabled
            ? <Button variant="outline" onClick={() => setConfirming(true)}>Deshabilitar</Button>
            : <Button loading={isPending} onClick={() => apply(true)}>Habilitar</Button>)}
        </div>
      </div>

      {plugin.problems.length > 0 && (
        <div role="alert" className="mb-4 rounded-lg border border-warning/40 bg-warning/10 p-4 text-sm">
          <p className="mb-1 flex items-center gap-2 font-medium"><ShieldAlert className="h-4 w-4" aria-hidden />{plugin.status === "invalid" ? "Este plugin no es válido" : "Este plugin no es compatible"}</p>
          <ul className="list-inside list-disc text-muted-foreground">{plugin.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Section title="Herramientas">
            {plugin.tools.length === 0 ? <p className="text-sm text-muted-foreground">Este plugin no declara herramientas.</p> : (
              <ul className="divide-y">{plugin.tools.map((t) => (
                <li key={t.id} className="py-2 first:pt-0 last:pb-0"><p className="text-sm font-medium">{t.name}</p>{t.description && <p className="text-sm text-muted-foreground">{t.description}</p>}</li>
              ))}</ul>
            )}
            {usable && plugin.id !== "youtube-dl" && (
              <p className="mt-4 flex items-start gap-2 rounded-md bg-muted p-3 text-sm text-muted-foreground">
                <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {!plugin.enabled ? "Habilitá el plugin para poder usar sus herramientas."
                  : plugin.executable_reason ?? "El runner de plugins todavía no está implementado en esta versión, por lo que las herramientas aún no se pueden ejecutar."}
              </p>
            )}
          </Section>
          {plugin.id === "youtube-dl" && <YoutubeDownloader enabled={plugin.enabled} />}
          <Section title="Permisos solicitados">
            {plugin.permissions.length === 0 ? <p className="text-sm text-muted-foreground">No solicita permisos.</p> : (
              <ul className="space-y-1 text-sm">{plugin.permissions.map((p) => <li key={p}>{PERMISSION_LABELS[p] ?? p} <code className="text-xs text-muted-foreground">({p})</code></li>)}</ul>
            )}
            <p className="mt-3 text-xs text-muted-foreground">Los permisos son declarados por el plugin; no reemplazan el aislamiento de ejecución.</p>
          </Section>
        </div>
        <div className="space-y-4">
          <Section title="Información">
            <dl className="space-y-2 text-sm">
              <Row k="Identificador" v={<code className="text-xs">{plugin.id}</code>} />
              <Row k="Integración" v={plugin.integration_type ?? "—"} />
              <Row k="Formato del plugin" v={plugin.contract_version ? `v${plugin.contract_version}` : "—"} />
              <Row k="Versión requerida" v={platform ? `${platform.min_version}${platform.max_version ? ` · ≤ ${platform.max_version}` : ""}` : "—"} />
              <Row k="Carpeta" v={<code className="text-xs">{plugin.folder}</code>} />
              <Row k="Categorías" v={plugin.categories.length ? <span className="flex flex-wrap justify-end gap-1">{plugin.categories.map((c) => <Badge key={c}>{c}</Badge>)}</span> : "—"} />
            </dl>
          </Section>
          {plugin.config_requirements.length > 0 && (
            <Section title="Configuración requerida"><ul className="list-inside list-disc text-sm text-muted-foreground">{plugin.config_requirements.map((c) => <li key={c}>{c}</li>)}</ul></Section>
          )}
        </div>
      </div>

      <ConfirmDialog open={confirming} title={`¿Deshabilitar ${plugin.name}?`} confirmLabel="Deshabilitar" destructive loading={isPending}
        description="La herramienta dejará de estar disponible para su uso. Podés volver a habilitarla cuando quieras."
        onConfirm={() => apply(false)} onClose={() => setConfirming(false)} />
    </>
  );
}

export function PluginDetailsPage() {
  const { pluginId = "" } = useParams();
  const { data, isPending, isError, error, refetch } = usePlugin(pluginId);
  return (
    <>
      <Link to="/tools" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" aria-hidden />Todas las herramientas</Link>
      {isPending ? <Skeleton className="h-48" /> : isError ? (
        error instanceof ApiError && error.status === 404
          ? <ErrorState error={new ApiError(404, "plugin_not_found", "No encontramos esta herramienta. Puede que se haya eliminado o que la carpeta ya no exista.")} />
          : <ErrorState error={error} onRetry={() => refetch()} />
      ) : <Body plugin={data} />}
    </>
  );
}