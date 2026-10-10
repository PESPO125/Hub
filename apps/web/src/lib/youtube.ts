import type { YoutubeDownloaderSettings } from "@/types/api";

type Format = YoutubeDownloaderSettings["output_format"];
type Quality = YoutubeDownloaderSettings["quality"];
export interface QualityOption { value: Quality; label: string }

export const VIDEO_QUALITY_OPTIONS: QualityOption[] = [
  { value: "best", label: "Máxima disponible" },
  { value: "2160", label: "2160p (4K)" },
  { value: "1440", label: "1440p" },
  { value: "1080", label: "1080p" },
  { value: "720", label: "720p" },
  { value: "480", label: "480p" },
];
export const AUDIO_QUALITY_OPTIONS: QualityOption[] = [
  { value: "best", label: "Máxima disponible" },
  { value: "320", label: "320 kbps" },
  { value: "256", label: "256 kbps" },
  { value: "192", label: "192 kbps" },
  { value: "128", label: "128 kbps" },
];

export const isAudioFormat = (format: Format | undefined) => format === "mp3" || format === "wav";
export const qualityOptionsFor = (format: Format | undefined) =>
  isAudioFormat(format) ? AUDIO_QUALITY_OPTIONS : VIDEO_QUALITY_OPTIONS;

/** Si la calidad guardada no aplica al formato actual, vuelve a "best". */
export const normalizeQuality = (s: YoutubeDownloaderSettings): YoutubeDownloaderSettings =>
  qualityOptionsFor(s.output_format).some((o) => o.value === s.quality) ? s : { ...s, quality: "best" };