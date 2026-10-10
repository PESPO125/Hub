import { CheckCircle2, FolderOpen, Monitor, Moon, RefreshCw, Sun, XCircle } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { PluginStatusBadge } from "@/components/shared/status-badges";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/toast";
import { usePluginToggle } from "@/hooks/use-plugin-toggle";
import { resolveIcon } from "@/lib/icons";
import { cn } from "@/lib/utils";
import { useAppInfo, useDiagnostics, usePlugins, useRefreshPlugins, useSaveTheme, useSettings } from "@/services/queries";
import type { Plugin, Theme } from "@/types/api";

const TABS = [
  { id: "appearance", label: "Apariencia" },
  { id: "plugins", label: "Plugins" },
  { id: "system", label: "Sistema" },
] as const;

const THEME_OPTIONS: { value: Theme; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Claro", icon: Sun },
  { value: "dark", label: "Oscuro", icon: Moon },
  { value: "system", label: "Sistema", icon: Monitor },
];

function Appearance() {
  const { data, isPending, isError, error, refetch } = useSettings();
  const save = useSaveTheme();
  const toast = useToast();
  if (isPending) return <Skeleton className="h-24" />;
  if (isError) return <ErrorState error={error} onRetry={() => refetch()} />;
  return (
    <section aria-labelledby="theme-h">
      <h2 id="theme-h" className="mb-1 text-sm font-semibold">Tema</h2>
      <p className="mb-3 text-sm text-muted-foreground">Elegí cómo se ve Hub.</p>
      <div role="radiogroup" aria-labelledby="theme-h" className="grid max-w-md grid-cols-3 gap-2">
        {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
          <button key={value} type="button" role="radio" aria-checked={data.theme === value} disabled={save.isPending}
            onClick={() => save.mutate(value, { onError: toast.error })}
            className={cn("flex flex-col items-center gap-2 rounded-lg border bg-card p-4 text-sm font-medium hover:bg-muted", data.theme === value && "border-primary ring-1 ring-primary")}>
            <Icon className="h-5 w-5" aria-hidden />{label}
          </button>
        ))}
      </div>
    </section>
  );
}

function PluginRow({ plugin }: { plugin: Plugin }) {
  const Icon = resolveIcon(plugin.icon);
  const { apply, confirming, setConfirming, isPending } = usePluginToggle(plugin);
  const valid = plugin.status === "available";
  const linkable = valid || plugin.status === "incompatible";
  return (
    <li className="flex flex-wrap items-start gap-3 p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted"><Icon className="h-4 w-4" aria-hidden /></div>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          {linkable
            ? <Link to={`/tools/${encodeURIComponent(plugin.id)}`} className="text-sm font-medium hover:underline">{plugin.name}</Link>
            : <span className="text-sm font-medium">{plugin.name}</span>}
          <PluginStatusBadge plugin={plugin} />
        </div>
        <p className="text-xs text-muted-foreground">{plugin.version ? `v${plugin.version} · ` : ""}carpeta: {plugin.folder}</p>
        {plugin.problems.length > 0 && <ul className="mt-1 list-inside list-disc text-xs text-destructive">{plugin.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      </div>
      <Switch checked={plugin.enabled} disabled={!valid} busy={isPending} label={`Habilitar ${plugin.name}`}
        onChange={(next) => (next ? apply(true) : setConfirming(true))} />
      <ConfirmDialog open={confirming} title={`¿Deshabilitar ${plugin.name}?`} confirmLabel="Deshabilitar" destructive loading={isPending}
        description="La herramienta dejará de estar disponible para su uso." onConfirm={() => apply(false)} onClose={() => setConfirming(false)} />
    </li>
  );
}

function Plugins() {
  const { data, isPending, isError, error, refetch } = usePlugins();
  const refresh = useRefreshPlugins();
  const toast = useToast();
  return (
    <section>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-xl text-sm text-muted-foreground">Hub busca plugins en la carpeta <code className="rounded bg-muted px-1">plugins/</code>. Buscar solo lee los manifiestos; nunca ejecuta código del plugin.</p>
        <Button variant="outline" loading={refresh.isPending}
          onClick={() => refresh.mutate(undefined, { onSuccess: (r) => toast.success(`Búsqueda completa: ${r.total} ${r.total === 1 ? "plugin" : "plugins"}.`), onError: toast.error })}>
          {!refresh.isPending && <RefreshCw className="h-4 w-4" aria-hidden />}Buscar plugins
        </Button>
      </div>
      {isPending ? <Skeleton className="h-24" /> : isError ? <ErrorState error={error} onRetry={() => refetch()} />
        : data.items.length === 0 ? (
          <EmptyState icon={FolderOpen} title="No se encontraron plugins">Copiá la carpeta de un plugin dentro de <code className="rounded bg-muted px-1">plugins/</code> y presioná “Buscar plugins”.</EmptyState>
        ) : <ul className="divide-y rounded-lg border bg-card shadow-card">{data.items.map((p) => <PluginRow key={p.id} plugin={p} />)}</ul>}
    </section>
  );
}

function StatusLine({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-sm">
      {ok ? <CheckCircle2 className="h-4 w-4 text-success" aria-label="Correcto" /> : <XCircle className="h-4 w-4 text-destructive" aria-label="Con problemas" />}
      {label}
    </li>
  );
}

function System() {
  const info = useAppInfo();
  const diag = useDiagnostics();
  if (info.isPending || diag.isPending) return <Skeleton className="h-40" />;
  if (info.isError) return <ErrorState error={info.error} onRetry={() => info.refetch()} />;
  if (diag.isError) return <ErrorState error={diag.error} onRetry={() => diag.refetch()} />;
  const i = info.data, d = diag.data;
  const platformRows: [string, string][] = [
    ["Versión", i.version], ["API", i.api_version], ["Entorno", i.environment],
    ["Modo", i.mode === "single_user_local" ? "Usuario único local" : i.mode],
    ["Plugins no confiables", i.untrusted_plugins_allowed ? "Permitidos" : "Deshabilitados"],
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <section className="rounded-lg border bg-card p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold">Plataforma</h2>
        <dl className="space-y-1.5 text-sm">
          {platformRows.map(([k, v]) => (
            <div key={k} className="flex justify-between gap-3"><dt className="text-muted-foreground">{k}</dt><dd>{v}</dd></div>
          ))}
        </dl>
      </section>
      <section className="rounded-lg border bg-card p-4 shadow-card">
        <h2 className="mb-3 text-sm font-semibold">Diagnóstico</h2>
        <ul className="space-y-1.5">
          <StatusLine ok={d.database.ok} label={`Base de datos (${d.database.engine})`} />
          <StatusLine ok={d.storage.ok} label="Almacenamiento escribible" />
          <StatusLine ok={d.plugins.directory_exists} label="Carpeta de plugins" />
        </ul>
        <p className="mt-3 text-xs text-muted-foreground">Plugins: {d.plugins.counts.available} válidos · {d.plugins.counts.incompatible} incompatibles · {d.plugins.counts.invalid} inválidos</p>
      </section>
    </div>
  );
}

export function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const tab = TABS.find((t) => t.id === params.get("tab"))?.id ?? "appearance";
  return (
    <>
      <PageHeader title="Configuración" />
      <div role="tablist" aria-label="Secciones de configuración" className="mb-6 flex gap-1 border-b">
        {TABS.map((t) => (
          <button key={t.id} role="tab" id={`tab-${t.id}`} aria-selected={tab === t.id} aria-controls="settings-panel" type="button"
            onClick={() => setParams({ tab: t.id }, { replace: true })}
            className={cn("-mb-px border-b-2 px-4 py-2 text-sm font-medium", tab === t.id ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="settings-panel" aria-labelledby={`tab-${tab}`}>
        {tab === "appearance" && <Appearance />}
        {tab === "plugins" && <Plugins />}
        {tab === "system" && <System />}
      </div>
    </>
  );
}