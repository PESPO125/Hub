import { ArrowLeft, Download, Info, Settings2, ShieldAlert } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { FavoriteButton } from "@/components/shared/plugin-card";
import { PluginStatusBadge } from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ErrorState, Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { resolveIcon } from "@/lib/icons";
import { ApiError } from "@/services/api";
import { useDownloadYoutubeVideo, usePlugin, useSaveYoutubeDownloaderSettings, useSetPluginState, useTasks, useYoutubeDownloaderSettings } from "@/services/queries";
import type { Plugin, YoutubeDownloaderSettings } from "@/types/api";

const PERMISSION_LABELS: Record<string, string> = {
  "files.read": "Leer archivos que le entregues",
  "files.write": "Crear archivos de resultado",
  "network.outbound": "Conectarse a internet",
  "process.spawn": "Ejecutar procesos del sistema",
  "config.read": "Leer su propia configuración",
};

function Section({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return <section className="rounded-lg border bg-card p-4 shadow-card"><div className="mb-3 flex items-center justify-between gap-3"><h2 className="text-sm font-semibold">{title}</h2>{action}</div>{children}</section>;
}

const QUALITY_OPTIONS: { value: YoutubeDownloaderSettings["quality"]; label: string }[] = [
  { value: "best", label: "Máxima disponible" },
  { value: "2160", label: "2160p (4K)" },
  { value: "1440", label: "1440p" },
  { value: "1080", label: "1080p" },
  { value: "720", label: "720p" },
  { value: "480", label: "480p" },
];

function YoutubeSettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const toast = useToast();
  const query = useYoutubeDownloaderSettings();
  const save = useSaveYoutubeDownloaderSettings();
  const [draft, setDraft] = useState<YoutubeDownloaderSettings | null>(null);

  useEffect(() => {
    if (query.data) setDraft(query.data);
  }, [query.data]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  const update = <K extends keyof YoutubeDownloaderSettings>(key: K, value: YoutubeDownloaderSettings[K]) =>
    setDraft((current) => current ? { ...current, [key]: value } : current);
  const audioOnly = draft?.output_format === "mp3" || draft?.output_format === "wav";

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    save.mutate(draft, {
      onSuccess: () => { toast.success("Preferencias de descarga guardadas."); onClose(); },
      onError: (error) => toast.error(error),
    });
  };

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="youtube-settings-title"
      className="w-[calc(100%-2rem)] max-w-lg rounded-lg border border-gray-300 bg-white p-0 text-black shadow-pop backdrop:bg-black/60"
    >
      <form onSubmit={submit}>
        <div className="space-y-4 p-5">
          <h2 id="youtube-settings-title" className="text-base font-semibold text-black">Preferencias de descarga</h2>
          {query.isPending || !draft ? <Skeleton className="h-40" /> : query.isError ? (
            <p role="alert" className="text-sm text-destructive">No se pudieron cargar las preferencias.</p>
          ) : (
            <>
              <label className="block space-y-1.5 text-sm">
                <span className="font-medium text-black">Formato</span>
                <select value={draft.output_format} onChange={(event) => update("output_format", event.target.value as YoutubeDownloaderSettings["output_format"])}
                  className="h-9 w-full rounded-md border border-gray-400 bg-white px-3 text-sm text-black">
                  <option value="mp4">MP4</option><option value="webm">WEBM</option><option value="mov">MOV</option>
                  <option value="mp3">MP3 (solo audio)</option><option value="wav">WAV (solo audio)</option>
                </select>
              </label>
              <label className="block space-y-1.5 text-sm">
                <span className="font-medium text-black">Resolución máxima</span>
                <select value={draft.quality} disabled={audioOnly} onChange={(event) => update("quality", event.target.value as YoutubeDownloaderSettings["quality"])}
                  className="h-9 w-full rounded-md border border-gray-400 bg-white px-3 text-sm text-black">
                  {QUALITY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </label>
              {audioOnly && <p className="text-xs text-gray-700">La resolución solo aplica al video.</p>}
            </>
          )}
        </div>
        <div className="flex justify-end gap-2 border-t border-gray-300 bg-white px-5 py-3">
          <Button type="button" variant="outline" className="border-gray-400 bg-white text-black hover:bg-gray-100" onClick={onClose} disabled={save.isPending}>Cerrar</Button>
          <Button type="submit" loading={save.isPending} disabled={!draft || query.isError}>Guardar</Button>
        </div>
      </form>
    </dialog>
  );
}

function YoutubeDownloader({ enabled }: { enabled: boolean }) {
  const [url, setUrl] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const download = useDownloadYoutubeVideo();
  const { data: tasks } = useTasks(undefined, 50, download.isPending);
  const activeTask = tasks?.items.find((task) =>
    task.plugin_id === "youtube-dl" && task.operation === "download-video" && task.status === "running",
  );

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    download.mutate(url, { onSuccess: () => setUrl("") });
  };

  return (
    <>
      <Section title="Descargar video" action={(
        <Button variant="ghost" size="icon" aria-label="Preferencias de descarga" title="Preferencias de descarga" onClick={() => setSettingsOpen(true)}>
          <Settings2 className="h-4 w-4" aria-hidden />
        </Button>
      )}>
        <form onSubmit={submit} className="space-y-3">
          <label htmlFor="youtube-url" className="block text-sm font-medium">URL de YouTube</label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              id="youtube-url"
              name="url"
              type="url"
              required
              maxLength={2048}
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              placeholder="https://www.youtube.com/watch?v=..."
              className="h-9 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
            <Button type="submit" loading={download.isPending} disabled={!enabled || !url.trim()}>
              <Download className="h-4 w-4" aria-hidden />
              Descargar
            </Button>
          </div>
        </form>
        {!enabled && <p className="mt-3 text-sm text-muted-foreground">Habilita el plugin para poder descargar.</p>}
        {download.isPending && (
          <div className="mt-3 space-y-1.5" aria-live="polite">
            <div className="flex justify-between gap-3 text-xs text-success">
              <span>{activeTask?.message ?? "Preparando descarga…"}</span>
              {activeTask?.progress !== null && activeTask?.progress !== undefined && <span>{Math.round(activeTask.progress * 100)}%</span>}
            </div>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round((activeTask?.progress ?? 0) * 100)}
              className="h-1.5 overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full bg-success transition-all" style={{ width: `${Math.round((activeTask?.progress ?? 0) * 100)}%` }} />
            </div>
          </div>
        )}
        {download.isError && <p role="alert" className="mt-3 text-sm text-destructive">{download.error.message}</p>}
        {download.isSuccess && <p role="status" className="mt-3 text-sm text-success">Video descargado y guardado.</p>}
      </Section>
      <YoutubeSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}

function Body({ plugin }: { plugin: Plugin }) {
  const toast = useToast();
  const setState = useSetPluginState();
  const [confirm, setConfirm] = useState(false);
  const Icon = resolveIcon(plugin.icon);
  const usable = plugin.status === "available";

  const apply = (enabled: boolean) =>
    setState.mutate({ id: plugin.id, enabled }, {
      onSuccess: () => { toast.success(enabled ? `${plugin.name} habilitado.` : `${plugin.name} deshabilitado.`); setConfirm(false); },
      onError: (e) => { toast.error(e); setConfirm(false); },
    });

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
            ? <Button variant="outline" onClick={() => setConfirm(true)}>Deshabilitar</Button>
            : <Button loading={setState.isPending} onClick={() => apply(true)}>Habilitar</Button>)}
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
              <Row k="Versión requerida" v={plugin.platform ? `${plugin.platform.min_version}${plugin.platform.max_version ? ` · ≤ ${plugin.platform.max_version}` : ""}` : "—"} />
              <Row k="Carpeta" v={<code className="text-xs">{plugin.folder}</code>} />
              <Row k="Categorías" v={plugin.categories.length ? <span className="flex flex-wrap justify-end gap-1">{plugin.categories.map((c) => <Badge key={c}>{c}</Badge>)}</span> : "—"} />
            </dl>
          </Section>
          {plugin.config_requirements.length > 0 && (
            <Section title="Configuración requerida"><ul className="list-inside list-disc text-sm text-muted-foreground">{plugin.config_requirements.map((c) => <li key={c}>{c}</li>)}</ul></Section>
          )}
        </div>
      </div>

      <ConfirmDialog open={confirm} title={`¿Deshabilitar ${plugin.name}?`} confirmLabel="Deshabilitar" destructive loading={setState.isPending}
        description="La herramienta dejará de estar disponible para su uso. Podés volver a habilitarla cuando quieras."
        onConfirm={() => apply(false)} onClose={() => setConfirm(false)} />
    </>
  );
}

const Row = ({ k, v }: { k: string; v: React.ReactNode }) => (
  <div className="flex items-start justify-between gap-3"><dt className="text-muted-foreground">{k}</dt><dd className="text-right">{v}</dd></div>
);

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
