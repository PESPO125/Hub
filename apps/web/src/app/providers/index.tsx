import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { ThemeProvider } from "@/app/providers/theme-provider";
import { ToastProvider } from "@/components/ui/toast";
import { ApiError } from "@/services/api";

export function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5_000,
        refetchOnWindowFocus: false,
        // No reintentar errores 4xx: no van a cambiar solos.
        retry: (count, err) => !(err instanceof ApiError && err.status >= 400 && err.status < 500) && count < 2,
      },
    },
  });
}

export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [qc] = useState(() => client ?? makeQueryClient());
  return (
    <QueryClientProvider client={qc}>
      <ToastProvider><ThemeProvider>{children}</ThemeProvider></ToastProvider>
    </QueryClientProvider>
  );
}
