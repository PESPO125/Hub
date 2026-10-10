import { Button } from "@/components/ui/button";
import { useModalDialog } from "@/hooks/use-modal-dialog";

interface Props {
  open: boolean; title: string; description: string; confirmLabel: string;
  destructive?: boolean; loading?: boolean; onConfirm: () => void; onClose: () => void;
}

/** Usa <dialog> nativo: trampa de foco, Esc y backdrop gratis y accesibles. */
export function ConfirmDialog({ open, title, description, confirmLabel, destructive, loading, onConfirm, onClose }: Props) {
  const ref = useModalDialog(open);
  return (
    <dialog ref={ref} onClose={onClose} aria-labelledby="dlg-title" aria-describedby="dlg-desc"
      className="w-[calc(100%-2rem)] max-w-md rounded-lg border bg-card p-0 text-foreground shadow-pop">
      <div className="p-5">
        <h2 id="dlg-title" className="text-base font-semibold">{title}</h2>
        <p id="dlg-desc" className="mt-2 text-sm text-muted-foreground">{description}</p>
      </div>
      <div className="flex justify-end gap-2 border-t bg-muted/40 px-5 py-3">
        <Button variant="outline" onClick={onClose} disabled={loading}>Cancelar</Button>
        <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} loading={loading}>{confirmLabel}</Button>
      </div>
    </dialog>
  );
}