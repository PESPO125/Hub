import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, downloadYoutubeVideo } from "@/services/api";
import type { AppInfo, Catalog, Diagnostics, Page, Plugin, StoredFile, TaskPage, TaskStatus, Theme, YoutubeDownloaderSettings } from "@/types/api";

export const keys = {
  catalog: (p: object) => ["catalog", p] as const,
  plugins: ["plugins"] as const,
  plugin: (id: string) => ["plugins", id] as const,
  tasks: (p: object) => ["tasks", p] as const,
  files: ["files"] as const,
  settings: ["settings"] as const,
  info: ["app-info"] as const,
  diagnostics: ["diagnostics"] as const,
  youtubeDownloaderSettings: ["plugins", "youtube-dl", "config"] as const,
};

export const useCatalog = (params: { q?: string; category?: string; favoritesOnly?: boolean } = {}) =>
  useQuery({
    queryKey: keys.catalog(params),
    placeholderData: keepPreviousData,
    queryFn: () => {
      const sp = new URLSearchParams();
      if (params.q) sp.set("q", params.q);
      if (params.category) sp.set("category", params.category);
      if (params.favoritesOnly) sp.set("favorites_only", "true");
      return api<Catalog>(`/catalog?${sp}`);
    },
  });

export const usePlugins = () => useQuery({ queryKey: keys.plugins, queryFn: () => api<Page<Plugin>>("/plugins") });
export const usePlugin = (id: string) =>
  useQuery({ queryKey: keys.plugin(id), queryFn: () => api<Plugin>(`/plugins/${encodeURIComponent(id)}`) });

/** Polling adaptativo: rápido si hay tareas activas, lento si no. */
export const useTasks = (status?: TaskStatus, limit = 50, forceFastPolling = false) =>
  useQuery({
    queryKey: keys.tasks({ status, limit }),
    queryFn: () => api<TaskPage>(`/tasks?limit=${limit}${status ? `&status=${status}` : ""}`),
    refetchInterval: (q) => (forceFastPolling ? 500 : (q.state.data?.active_count ?? 0) > 0 ? 1000 : 15000),
  });

export const useFiles = () => useQuery({ queryKey: keys.files, queryFn: () => api<Page<StoredFile>>("/files?limit=50") });
export const useAppInfo = () => useQuery({ queryKey: keys.info, queryFn: () => api<AppInfo>("/app/info"), staleTime: 60_000 });
export const useDiagnostics = () => useQuery({ queryKey: keys.diagnostics, queryFn: () => api<Diagnostics>("/diagnostics") });
export const useSettings = () => useQuery({ queryKey: keys.settings, queryFn: () => api<{ theme: Theme }>("/settings") });
export const useYoutubeDownloaderSettings = () =>
  useQuery({
    queryKey: keys.youtubeDownloaderSettings,
    queryFn: () => api<YoutubeDownloaderSettings>("/plugins/youtube-dl/config"),
  });

export const useSaveYoutubeDownloaderSettings = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (value: YoutubeDownloaderSettings) =>
      api<YoutubeDownloaderSettings>("/plugins/youtube-dl/config", { method: "PUT", json: value }),
    onSuccess: (value) => qc.setQueryData(keys.youtubeDownloaderSettings, value),
  });
};

function useInvalidate() {
  const qc = useQueryClient();
  return () => Promise.all(["catalog", "plugins", "diagnostics"].map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

export const useToggleFavorite = () => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, favorite }: { id: string; favorite: boolean }) =>
      api(`/favorites/${encodeURIComponent(id)}`, { method: favorite ? "PUT" : "DELETE" }),
    onSuccess: invalidate,
  });
};

export const useSetPluginState = () => {
  const invalidate = useInvalidate();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api<Plugin>(`/plugins/${encodeURIComponent(id)}/state`, { method: "PATCH", json: { enabled } }),
    onSuccess: invalidate,
  });
};

export const useDownloadYoutubeVideo = () =>
  useMutation({ mutationFn: (url: string) => downloadYoutubeVideo(url) });

export const useRefreshPlugins = () => {
  const invalidate = useInvalidate();
  return useMutation({ mutationFn: () => api<{ total: number }>("/plugins/refresh", { method: "POST" }), onSuccess: invalidate });
};

export const useSaveTheme = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (theme: Theme) => api<{ theme: Theme }>("/settings", { method: "PUT", json: { theme } }),
    onSuccess: (d) => qc.setQueryData(keys.settings, d),
  });
};

export const useCancelTask = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/tasks/${id}/cancel`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
};
