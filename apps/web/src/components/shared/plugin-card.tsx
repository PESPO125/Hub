import { Star } from "lucide-react";
import { Link } from "react-router-dom";
import { PluginStatusBadge } from "@/components/shared/status-badges";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { resolveIcon } from "@/lib/icons";
import { cn } from "@/lib/utils";
import { useToggleFavorite } from "@/services/queries";
import type { Plugin } from "@/types/api";

export function FavoriteButton({ plugin, className }: { plugin: Plugin; className?: string }) {
  const toggle = useToggleFavorite();
  const toast = useToast();
  return (
    <button
      type="button" aria-pressed={plugin.favorite} disabled={toggle.isPending}
      aria-label={plugin.favorite ? `Quitar ${plugin.name} de favoritos` : `Agregar ${plugin.name} a favoritos`}
      onClick={() => toggle.mutate({ id: plugin.id, favorite: !plugin.favorite }, { onError: toast.error })}
      className={cn("rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50", className)}
    >
      <Star className={cn("h-4 w-4", plugin.favorite && "fill-warning text-warning")} aria-hidden />
    </button>
  );
}

export function PluginCard({ plugin }: { plugin: Plugin }) {
  const Icon = resolveIcon(plugin.icon);
  return (
    <div className="group relative flex flex-col rounded-lg border bg-card p-4 shadow-card transition-colors hover:border-primary/50">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Icon className="h-5 w-5" aria-hidden /></div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate font-medium">
            <Link to={`/tools/${encodeURIComponent(plugin.id)}`} className="after:absolute after:inset-0 after:content-[''] focus-visible:after:rounded-lg">{plugin.name}</Link>
          </h3>
          <p className="text-xs text-muted-foreground">v{plugin.version}</p>
        </div>
        <FavoriteButton plugin={plugin} className="relative z-10 -mr-1 -mt-1" />
      </div>
      <p className="mt-3 line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">{plugin.description || "Sin descripción."}</p>
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <PluginStatusBadge plugin={plugin} />
        {plugin.categories.map((c) => <Badge key={c}>{c}</Badge>)}
      </div>
    </div>
  );
}
