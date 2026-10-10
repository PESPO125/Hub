import { useState } from "react";
import { useToast } from "@/components/ui/toast";
import { useSetPluginState } from "@/services/queries";
import type { Plugin } from "@/types/api";

/** Comparte el flujo de habilitar y confirmar deshabilitación de un plugin. */
export function usePluginToggle(plugin: Plugin) {
  const setState = useSetPluginState();
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);

  const apply = (enabled: boolean) => setState.mutate(
    { id: plugin.id, enabled },
    {
      onSuccess: () => {
        toast.success(enabled ? `${plugin.name} habilitado.` : `${plugin.name} deshabilitado.`);
        setConfirming(false);
      },
      onError: (error) => {
        toast.error(error);
        setConfirming(false);
      },
    },
  );

  return { apply, confirming, setConfirming, isPending: setState.isPending };
}
