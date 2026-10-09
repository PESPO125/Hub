import { SearchX, Star } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { NoPluginsState } from "@/components/shared/no-plugins";
import { PluginGrid } from "@/components/shared/plugin-grid";
import { Button } from "@/components/ui/button";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { cn } from "@/lib/utils";
import { useCatalog } from "@/services/queries";

export function CatalogPage({ favoritesOnly = false }: { favoritesOnly?: boolean }) {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category") ?? "";
  const { data, isPending, isError, error, refetch, isFetching } = useCatalog({ q, category, favoritesOnly });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    setParams(next, { replace: true });
  };
  const filtered = Boolean(q || category);

  return (
    <>
      <PageHeader title={favoritesOnly ? "Favoritos" : "Todas las herramientas"}
        description={favoritesOnly ? "Las herramientas que marcaste con una estrella." : "Explorá y abrí las herramientas disponibles."} />

      <div className="mb-5 space-y-3">
        <div>
          <label htmlFor="catalog-q" className="sr-only">Filtrar herramientas</label>
          <input id="catalog-q" value={q} onChange={(e) => update("q", e.target.value)} placeholder="Filtrar por nombre o descripción…"
            className="h-9 w-full max-w-sm rounded-md border bg-card px-3 text-sm placeholder:text-muted-foreground" />
        </div>
        {data && data.categories.length > 0 && (
          <div className="flex flex-wrap gap-2" role="group" aria-label="Categorías">
            {["", ...data.categories].map((c) => (
              <button key={c || "all"} type="button" aria-pressed={category === c} onClick={() => update("category", c)}
                className={cn("rounded-full border px-3 py-1 text-xs font-medium transition-colors", category === c ? "border-primary bg-primary text-primary-foreground" : "bg-card text-muted-foreground hover:bg-muted")}>
                {c || "Todas"}
              </button>
            ))}
          </div>
        )}
      </div>

      <div aria-busy={isFetching}>
        {isPending ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-36" />)}</div>
        ) : isError ? (
          <ErrorState error={error} onRetry={() => refetch()} />
        ) : data.installed_total === 0 ? (
          <NoPluginsState />
        ) : data.items.length === 0 ? (
          filtered ? (
            <EmptyState icon={SearchX} title="Sin resultados" action={<Button variant="outline" onClick={() => setParams({}, { replace: true })}>Limpiar filtros</Button>}>
              Ninguna herramienta coincide con tu búsqueda.
            </EmptyState>
          ) : (
            <EmptyState icon={Star} title="Todavía no tenés favoritos">Marcá una herramienta con la estrella para tenerla siempre a mano.</EmptyState>
          )
        ) : (
          <PluginGrid plugins={data.items} />
        )}
      </div>
    </>
  );
}
