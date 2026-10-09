import { Loader2, Menu, Search, Settings } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useTasks } from "@/services/queries";

export function Topbar({ onOpenMenu }: { onOpenMenu: () => void }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const { data: tasks } = useTasks(undefined, 1);
  const active = tasks?.active_count ?? 0;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      const typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable);
      if ((e.key === "k" && (e.metaKey || e.ctrlKey)) || (e.key === "/" && !typing)) { e.preventDefault(); input.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const term = q.trim();
    navigate(term ? `/tools?q=${encodeURIComponent(term)}` : "/tools");
  };

  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b bg-card px-3 md:px-5">
      <Button variant="ghost" size="icon" className="md:hidden" onClick={onOpenMenu} aria-label="Abrir menú" aria-controls="sidebar"><Menu className="h-4 w-4" /></Button>
      <form onSubmit={submit} role="search" className="relative max-w-md flex-1">
        <label htmlFor="global-search" className="sr-only">Buscar herramientas</label>
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
        <input id="global-search" ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar herramientas…" autoComplete="off"
          className="h-9 w-full rounded-md border bg-background pl-9 pr-12 text-sm placeholder:text-muted-foreground" />
        <kbd className="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border bg-muted px-1.5 text-[10px] text-muted-foreground sm:block" aria-hidden>/</kbd>
      </form>
      <div className="ml-auto flex items-center gap-1">
        {active > 0 && (
          <Link to="/tasks" className="flex h-8 items-center gap-1.5 rounded-md bg-primary/10 px-2.5 text-xs font-medium text-primary" aria-label={`${active} tareas activas`}>
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />{active} {active === 1 ? "tarea" : "tareas"}
          </Link>
        )}
        <Link to="/settings" aria-label="Configuración" className="inline-flex h-9 w-9 items-center justify-center rounded-md hover:bg-muted"><Settings className="h-4 w-4" /></Link>
      </div>
    </header>
  );
}
