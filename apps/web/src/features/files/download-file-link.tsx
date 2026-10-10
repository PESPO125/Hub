import { Download } from "lucide-react";
import type { MouseEvent } from "react";
import { buttonClass } from "@/components/ui/button-link";
import { useToast } from "@/components/ui/toast";

type SaveFileHandle = { createWritable: () => Promise<WritableStream> };
type SavePickerWindow = Window & {
  showSaveFilePicker?: (options: { suggestedName: string }) => Promise<SaveFileHandle>;
};

export function DownloadFileLink({ fileId, fileName, className = "", label }: {
  fileId: string;
  fileName: string;
  className?: string;
  label?: string;
}) {
  const toast = useToast();
  const href = `/api/v1/files/${encodeURIComponent(fileId)}/download`;
  const pickerAvailable = typeof window !== "undefined"
    && typeof (window as SavePickerWindow).showSaveFilePicker === "function";

  const saveAs = async (event: MouseEvent<HTMLAnchorElement>) => {
    const picker = (window as SavePickerWindow).showSaveFilePicker;
    if (!picker) return;
    event.preventDefault();
    try {
      const handle = await picker.call(window, { suggestedName: fileName });
      const response = await fetch(href);
      if (!response.ok || !response.body) throw new Error("No se pudo obtener el archivo de Hub.");
      await response.body.pipeTo(await handle.createWritable());
      toast.success("Archivo guardado en tu equipo.");
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") return;
      toast.error(error instanceof Error ? error.message : "No se pudo guardar el archivo.");
    }
  };

  return (
    <a href={href} download aria-label={`${pickerAvailable ? "Guardar como" : "Descargar"} ${fileName}`}
      onClick={saveAs} className={buttonClass("outline", className)}>
      <Download className="h-4 w-4" aria-hidden />
      {label ?? (pickerAvailable ? "Guardar como…" : "Descargar")}
    </a>
  );
}
