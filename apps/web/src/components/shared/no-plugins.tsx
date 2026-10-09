import { FolderOpen, Settings } from "lucide-react";
import { Link } from "react-router-dom";
import { EmptyState } from "@/components/ui/states";
import { buttonClass } from "@/components/ui/button-link";

export function NoPluginsState() {
  return (
    <EmptyState icon={FolderOpen} title="Todavía no hay herramientas instaladas"
      action={<Link to="/settings?tab=plugins" className={buttonClass("default")}><Settings className="h-4 w-4" aria-hidden />Administrar plugins</Link>}>
      <p>Cada herramienta es un plugin: una carpeta dentro de <code className="rounded bg-muted px-1">plugins/</code> con su <code className="rounded bg-muted px-1">plugin.json</code>. Al agregarla, Hub la detecta, la valida y aparece acá automáticamente.</p>
    </EmptyState>
  );
}
