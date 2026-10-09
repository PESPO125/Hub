import { cn } from "@/lib/utils";

interface Props { checked: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean; busy?: boolean }

export function Switch({ checked, onChange, label, disabled, busy }: Props) {
  return (
    <button
      type="button" role="switch" aria-checked={checked} aria-label={label} disabled={disabled || busy}
      onClick={() => onChange(!checked)}
      className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors disabled:opacity-50", checked ? "bg-primary" : "bg-muted-foreground/40")}
    >
      <span className={cn("absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform", checked && "translate-x-4")} />
    </button>
  );
}
