import type { LucideIcon } from "lucide-react";
import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/services/api";
import { cn } from "@/lib/utils";

export const Skeleton = ({ className }: { className?: string }) => (
  <div aria-hidden className={cn("animate-pulse rounded-md bg-muted", className)} />
);

export function EmptyState({ icon: Icon, title, children, action }: { icon: LucideIcon; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed px-6 py-12 text-center">
      <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-muted text-muted-foreground"><Icon className="h-6 w-6" aria-hidden /></div>
      <h2 className="text-base font-semibold">{title}</h2>
      {children && <div className="mt-1.5 max-w-md text-sm text-muted-foreground">{children}</div>}
      {action && <div className="mt-5 flex flex-wrap justify-center gap-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const api = error instanceof ApiError ? error : null;
  const Icon = api?.isNetwork ? WifiOff : AlertTriangle;
  return (
    <div role="alert" className="flex flex-col items-center rounded-lg border border-destructive/40 bg-destructive/5 px-6 py-10 text-center">
      <Icon className="mb-3 h-8 w-8 text-destructive" aria-hidden />
      <h2 className="text-base font-semibold">{api?.isNetwork ? "Sin conexión con el backend" : "Algo salió mal"}</h2>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{api?.message ?? "Ocurrió un error inesperado."}</p>
      {api?.requestId && <p className="mt-1 text-xs text-muted-foreground">ID de solicitud: {api.requestId}</p>}
      {onRetry && <Button variant="outline" className="mt-4" onClick={onRetry}><RefreshCw className="h-4 w-4" aria-hidden />Reintentar</Button>}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex gap-2">{actions}</div>}
    </div>
  );
}
