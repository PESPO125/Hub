import { resolveIcon } from "@/lib/icons";
import { formatBytes } from "@/lib/utils";
import { Puzzle } from "lucide-react";

it("formatBytes", () => { expect(formatBytes(512)).toBe("512 B"); expect(formatBytes(2048)).toBe("2.0 KB"); });
it("iconos desconocidos o maliciosos caen en el predeterminado", () => {
  expect(resolveIcon("../../evil")).toBe(Puzzle);
  expect(resolveIcon(undefined)).toBe(Puzzle);
});
