import { Download, Settings2, X } from "lucide-react";
import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { Section } from "@/components/shared/section";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { DownloadFileLink } from "@/features/files/download-file-link";
import { useModalDialog } from "@/hooks/use-modal-dialog";
import { isAudioFormat, normalizeQuality, qualityOptionsFor } from "@/lib/youtube";
import { useCancelTask, useDownloadYoutubeVideo, useSaveYoutubeDownloaderSettings, useTasks, useYoutubeDownloaderSettings } from "@/services/queries";
import type { TaskStatus, YoutubeDownloaderSettings } from "@/types/api";

type Format = YoutubeDownloaderSettings["output_format"];
type Quality = YoutubeDownloaderSettings["quality"];

const FORMAT_OPTIONS: { value: Format; label: string }[] = [
  { value: "mp4", label: "MP4" }, { value: "webm", label: "WEBM" }, { value: "mov", label: "MOV" },
  { value: "mp3", label: "MP3 (solo audio)" }, { value: "wav", label: "WAV (solo audio)" },
];

function SelectField({ label, value, onChange, children }: {
  label: string; value: string; onChange: (value: string) => void; children: ReactNode;
}) {
  return (
    <label className="block space-y-1.5 text-sm">
      <span className="font-medium text-black">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="h-9 w-full rounded-md border border-gray-400 bg-white px-3 text-sm text-black">
        {children}
      </select>
    </label>
  );
}

function SettingsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialogRef = useModalDialog(open);
  const toast = useToast();
  const query = useYoutubeDownloaderSettings();
  const save = useSaveYoutubeDownloaderSettings();
  const [draft, setDraft] = useState<YoutubeDownloaderSettings | null>(null);

  useEffect(() => { if (query.data) setDraft(normalizeQuality(query.data)); }, [query.data]);

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    save.mutate(draft, {
      onSuccess: () => { toast.success("Preferencias de descarga guardadas."); onClose(); },
      onError: (error) => toast.error(error),
    });
  };

  return (
    <dialog ref={dialogRef} onClose={onClose} aria-labelledby="youtube-settings-title"
      className="w-[calc(100%-2rem)] max-w-lg rounded-lg border border-gray-300 bg-white p-0 text-black shadow-pop backdrop:bg-black/60">
      <form onSubmit={submit}>
        <div className="space-y-4 p-5">
          <h2 id="youtube-settings-title" className="text-base font-semibold text-black">Preferencias de descarga</h2>
          {query.isPending || !draft ? <Skeleton className="h-40" /> : query.isError ? (
            <p role="alert" className="text-sm text-destructive">No se pudieron cargar las preferencias.</p>
          ) : (
            <>
              <SelectField label="Formato" value={draft.output_format}
                onChange={(value) => setDraft({ ...draft, output_format: value as Format, quality: "best" })}>
                {FORMAT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </SelectField>
              <SelectField label={isAudioFormat(draft.output_format) ? "Calidad de audio" : "Resolución máxima"}
                value={draft.quality} onChange={(value) => setDraft({ ...draft, quality: value as Quality })}>
                {qualityOptionsFor(draft.output_format).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </SelectField>
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

function DownloadProgress({ status, message, progress, onCancel, canceling }: {
  status: Extract<TaskStatus, "pending" | "running">;
  message: string;
  progress: number | null | undefined;
  onCancel: () => void;
  canceling: boolean;
}) {
  const percent = Math.round((progress ?? 0) * 100);
  return (
    <div className="mt-3 space-y-1.5" aria-live="polite">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-success">
        <span><strong>{status === "pending" ? "En espera" : "En ejecución"}:</strong> {message}</span>
        <div className="flex items-center gap-2">
          {status === "running" && progress !== null && progress !== undefined && <span>{percent}%</span>}
          <Button variant="outline" size="sm" disabled={canceling} onClick={onCancel} aria-label="Cancelar descarga">
            <X className="h-3.5 w-3.5" aria-hidden />{canceling ? "Cancelando…" : "Cancelar"}
          </Button>
        </div>
      </div>
      <div role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent} className="h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-success transition-all" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function YoutubeDownloader({ enabled }: { enabled: boolean }) {
  const [url, setUrl] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const download = useDownloadYoutubeVideo();
  const cancelTask = useCancelTask();
  const toast = useToast();
  const { data: settings } = useYoutubeDownloaderSettings();
  const { data: tasks } = useTasks(undefined, 50, download.isPending);
  const submittedTask = tasks?.items.find((t) => t.id === download.data?.id);
  const activeTask = submittedTask ?? tasks?.items.find((t) => t.plugin_id === "youtube-dl" && t.operation === "download-video" && (t.status === "running" || t.status === "pending"));

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    download.mutate(url, { onSuccess: () => setUrl("") });
  };

  const cancelActiveTask = () => {
    if (!activeTask) return;
    cancelTask.mutate(activeTask.id, {
      onSuccess: () => toast.success("Cancelación solicitada."),
      onError: (error) => toast.error(error),
    });
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
            <input id="youtube-url" name="url" type="url" required maxLength={2048} value={url}
              onChange={(e) => setUrl(e.target.value)} placeholder="https://www.youtube.com/watch?v=..."
              className="h-9 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
            <Button type="submit" loading={download.isPending} disabled={!enabled || !url.trim()}>
              <Download className="h-4 w-4" aria-hidden />load
            </Button>
          </div>
        </form>
        {!enabled && <p className="mt-3 text-sm text-muted-foreground">Habilita el plugin para poder descargar.</p>}
        {activeTask && (activeTask.status === "running" || activeTask.status === "pending") && (
          <DownloadProgress status={activeTask.status} message={activeTask.message ?? "Preparando descarga…"}
            progress={activeTask.progress} onCancel={cancelActiveTask}
            canceling={cancelTask.isPending || activeTask.cancel_requested} />
        )}
        {download.isError && <p role="alert" className="mt-3 text-sm text-destructive">{download.error.message}</p>}
        {submittedTask?.status === "failed" && <p role="alert" className="mt-3 text-sm text-destructive">{submittedTask.error?.message ?? "La tarea falló."}</p>}
        {submittedTask?.status === "completed" && (
          <div role="status" className="mt-3 space-y-2 text-sm text-success">
            <p>{isAudioFormat(settings?.output_format) ? "Audio listo para guardar en tu equipo:" : "Video listo para guardar en tu equipo:"}</p>
            <div className="flex flex-wrap gap-2">
              {(submittedTask.files ?? []).map((file) => (
                <DownloadFileLink key={file.id} fileId={file.id} fileName={file.display_name} className="px-3" label="download" />
              ))}
            </div>
          </div>
        )}
      </Section>
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </>
  );
}
