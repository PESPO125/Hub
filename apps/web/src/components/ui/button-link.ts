import { cn } from "@/lib/utils";

const variants = {
  default: "bg-primary text-primary-foreground hover:opacity-90",
  outline: "border bg-card hover:bg-muted",
  ghost: "hover:bg-muted",
} as const;

/** Estilo de botón para <Link>, sin anidar <button> dentro de <a>. */
export const buttonClass = (variant: keyof typeof variants = "default", extra?: string) =>
  cn("inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition-colors", variants[variant], extra);
