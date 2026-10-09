import { FileArchive, Home, LayoutGrid, ListChecks, PanelLeftClose, PanelLeftOpen, Settings, Star, X } from "lucide-react";
import { NavLink, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { resolveIcon } from "@/lib/icons";
import { cn } from "@/lib/utils";
import { useAppInfo, useCatalog } from "@/services/queries";

const NAV = [
  { to: "/", label: "Inicio", icon: Home, end: true },
  { to: "/tools", label: "Todas las herramientas", icon: LayoutGrid, end: true },
  { to: "/favorites", label: "Favoritos", icon: Star, end: true },
  { to: "/tasks", label: "Tareas", icon: ListChecks, end: true },
  { to: "/files", label: "Archivos y resultados", icon: FileArchive, end: true },
  { to: "/settings", label: "Configuración", icon: Settings, end: false },
];

interface Props { collapsed: boolean; onToggle: () => void; mobileOpen: boolean; onCloseMobile: () => void }

export function Sidebar({ collapsed, onToggle, mobileOpen, onCloseMobile }: Props) {
  const { data: favs } = useCatalog({ favoritesOnly: true });
  const { data: info } = useAppInfo();
  const slim = collapsed && !mobileOpen; // en móvil el cajón siempre va expandido

  return (
    <>
      {mobileOpen && <div className="fixed inset-0 z-30 bg-black/40 md:hidden" onClick={onCloseMobile} aria-hidden />}
      <aside
        id="sidebar" aria-label="Barra lateral"
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-card transition-[width,transform] duration-150 md:static md:translate-x-0",
          mobileOpen ? "w-64 translate-x-0" : "-translate-x-full",
          slim ? "md:w-16" : "md:w-64",
        )}
      >
        <div className={cn("flex h-14 items-center border-b px-3", slim ? "justify-center" : "justify-between")}>
          <Link to="/" onClick={onCloseMobile} className="flex items-center gap-2 font-semibold">
            <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-primary-foreground" aria-hidden><LayoutGrid className="h-4 w-4" /></span>
            {!slim && <span>Hub</span>}
          </Link>
          <Button variant="ghost" size="icon" className="md:hidden" onClick={onCloseMobile} aria-label="Cerrar menú"><X className="h-4 w-4" /></Button>
        </div>

        <nav aria-label="Navegación principal" className="flex-1 space-y-1 overflow-y-auto p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={onCloseMobile} title={slim ? label : undefined} aria-label={slim ? label : undefined}
              className={({ isActive }) => cn("flex h-9 items-center gap-3 rounded-md px-2.5 text-sm font-medium text-muted-foreground hover:bg-muted hover:text-foreground", isActive && "bg-primary/10 text-primary hover:bg-primary/10 hover:text-primary", slim && "justify-center")}>
              <Icon className="h-4 w-4 shrink-0" aria-hidden />
              {!slim && <span className="truncate">{label}</span>}
            </NavLink>
          ))}

          {!slim && favs && favs.items.length > 0 && (
            <div className="pt-4">
              <p className="px-2.5 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Favoritas</p>
              {favs.items.map((p) => {
                const Icon = resolveIcon(p.icon);
                return (
                  <NavLink key={p.id} to={`/tools/${encodeURIComponent(p.id)}`} onClick={onCloseMobile}
                    className={({ isActive }) => cn("flex h-8 items-center gap-3 rounded-md px-2.5 text-sm text-muted-foreground hover:bg-muted hover:text-foreground", isActive && "text-primary")}>
                    <Icon className="h-4 w-4 shrink-0" aria-hidden /><span className="truncate">{p.name}</span>
                  </NavLink>
                );
              })}
            </div>
          )}
        </nav>

        <div className={cn("flex items-center border-t p-2", slim ? "justify-center" : "justify-between")}>
          {!slim && <span className="px-2 text-xs text-muted-foreground">{info ? `v${info.version}` : ""}</span>}
          <Button variant="ghost" size="icon" className="hidden md:inline-flex" onClick={onToggle}
            aria-label={collapsed ? "Expandir barra lateral" : "Contraer barra lateral"} aria-expanded={!collapsed} aria-controls="sidebar">
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </Button>
        </div>
      </aside>
    </>
  );
}
