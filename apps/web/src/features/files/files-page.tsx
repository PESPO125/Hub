import { Download, FileArchive } from "lucide-react";
import { EmptyState, ErrorState, PageHeader, Skeleton } from "@/components/ui/states";
import { buttonClass } from "@/components/ui/button-link";
import { formatBytes, formatDate } from "@/lib/utils";
import { useFiles } from "@/services/queries";

export function FilesPage() {
  const { data, isPending, isError, error, refetch } = useFiles();
  return (
    <>
      <PageHeader title="Archivos y resultados" description="Lo que generaron tus herramientas." />
      {isPending ? <div className="space-y-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div>
        : isError ? <ErrorState error={error} onRetry={() => refetch()} />
        : data.items.length === 0 ? (
          <EmptyState icon={FileArchive} title="Todavía no hay resultados">Los archivos que produzcan tus herramientas van a aparecer acá, con su tamaño y fecha de expiración.</EmptyState>
        ) : (
          <ul className="divide-y rounded-lg border bg-card shadow-card">
            {data.items.map((f) => (
              <li key={f.id} className="flex flex-wrap items-center justify-between gap-2 p-4">
                <div className="min-w-0"><p className="truncate text-sm font-medium">{f.display_name}</p><p className="text-xs text-muted-foreground">{formatDate(f.created_at)}{f.expires_at && ` · expira ${formatDate(f.expires_at)}`}</p></div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
                  <a
                    href={`/api/v1/files/${encodeURIComponent(f.id)}/download`}
                    download
                    aria-label={`Descargar ${f.display_name}`}
                    className={buttonClass("outline", "px-3")}
                  >
                    <Download className="h-4 w-4" aria-hidden />
                    Descargar
                  </a>
                </div>
              </li>
            ))}
          </ul>
        )}
    </>
  );
}
