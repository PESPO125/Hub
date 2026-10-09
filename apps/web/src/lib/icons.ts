import {
  Code, Download, FileArchive, FileText, Folder, Globe, Image, Music, Puzzle, QrCode, Scissors,
  Sparkles, Terminal, Video, Wrench, type LucideIcon,
} from "lucide-react";

// Solo identificadores de la allowlist del manifiesto. Cualquier otro valor cae en "puzzle".
const ICONS: Record<string, LucideIcon> = {
  wrench: Wrench, download: Download, "file-text": FileText, image: Image, music: Music, video: Video,
  "qr-code": QrCode, code: Code, sparkles: Sparkles, folder: Folder, scissors: Scissors,
  "file-archive": FileArchive, terminal: Terminal, globe: Globe, puzzle: Puzzle,
};

export const resolveIcon = (name: string | null | undefined): LucideIcon => ICONS[name ?? ""] ?? Puzzle;
