import { useEffect, useRef } from "react";

/** Sincroniza un <dialog> nativo con un booleano `open` (trampa de foco, Esc y backdrop gratis). */
export function useModalDialog(open: boolean) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    else if (!open && dialog.open) dialog.close();
  }, [open]);
  return ref;
}