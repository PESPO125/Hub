import { Compass } from "lucide-react";
import { createBrowserRouter, createMemoryRouter, Link, type RouteObject } from "react-router-dom";
import { AppLayout } from "@/app/layouts/app-layout";
import { CatalogPage } from "@/features/catalog/catalog-page";
import { DashboardPage } from "@/features/dashboard/dashboard-page";
import { FilesPage } from "@/features/files/files-page";
import { PluginDetailsPage } from "@/features/plugin-details/plugin-details-page";
import { SettingsPage } from "@/features/settings/settings-page";
import { TasksPage } from "@/features/tasks/tasks-page";
import { buttonClass } from "@/components/ui/button-link";
import { EmptyState } from "@/components/ui/states";

function NotFound() {
  return <EmptyState icon={Compass} title="Página no encontrada" action={<Link to="/" className={buttonClass("default")}>Ir al inicio</Link>}>La dirección no existe.</EmptyState>;
}

export const routes: RouteObject[] = [
  {
    element: <AppLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "tools", element: <CatalogPage /> },
      { path: "tools/:pluginId", element: <PluginDetailsPage /> },
      { path: "favorites", element: <CatalogPage favoritesOnly /> },
      { path: "tasks", element: <TasksPage /> },
      { path: "files", element: <FilesPage /> },
      { path: "settings", element: <SettingsPage /> },
      { path: "*", element: <NotFound /> },
    ],
  },
];

export const createRouter = () => createBrowserRouter(routes);
export const createTestRouter = (path = "/") => createMemoryRouter(routes, { initialEntries: [path] });
