import { PluginCard } from "@/components/shared/plugin-card";
import type { Plugin } from "@/types/api";

export const PluginGrid = ({ plugins }: { plugins: Plugin[] }) => (
  <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
    {plugins.map((p) => <li key={p.id}><PluginCard plugin={p} /></li>)}
  </ul>
);
