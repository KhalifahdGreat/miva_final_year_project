import type { SVGProps } from "react";

type IconName =
  | "grid" | "book" | "chat" | "persona" | "plug" | "chart" | "play"
  | "plus" | "upload" | "download" | "check" | "x" | "search" | "trash"
  | "copy" | "chevron" | "refresh" | "alert" | "send" | "whatsapp" | "globe"
  | "dot" | "clock" | "language" | "shield" | "external";

const PATHS: Record<IconName, JSX.Element> = {
  grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
  book: <><path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z" /><path d="M19 3v16" /></>,
  chat: <><path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z" /></>,
  persona: <><path d="M12 3l1.9 4.5L19 9l-4 3 1 5-4-2.5L8 17l1-5-4-3 5.1-1.5z" /></>,
  plug: <><path d="M9 7V3M15 7V3M7 7h10v4a5 5 0 0 1-10 0z" /><path d="M12 16v5" /></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-6M22 20H2" /></>,
  play: <><circle cx="12" cy="12" r="9" /><path d="M10 9l5 3-5 3z" /></>,
  plus: <><path d="M12 5v14M5 12h14" /></>,
  upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M5 20h14" /></>,
  download: <><path d="M12 4v12M7 11l5 5 5-5" /><path d="M5 20h14" /></>,
  check: <><path d="M5 12l4.5 4.5L19 7" /></>,
  x: <><path d="M6 6l12 12M18 6L6 18" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></>,
  trash: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></>,
  copy: <><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V5a2 2 0 0 1 2-2h8" /></>,
  chevron: <><path d="M6 9l6 6 6-6" /></>,
  refresh: <><path d="M21 12a9 9 0 1 1-3-6.7L21 8" /><path d="M21 3v5h-5" /></>,
  alert: <><path d="M12 9v4M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></>,
  send: <><path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" /></>,
  whatsapp: <><path d="M3 21l1.7-5A9 9 0 1 1 8 19.3z" /><path d="M8.5 8.5c0 4 3 7 7 7 1 0 1.5-1 1.5-1.5l-2-1-1 1c-1.5-.5-3-2-3.5-3.5l1-1-1-2c-.5 0-1.5.5-1.5 1z" /></>,
  globe: <><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></>,
  dot: <><circle cx="12" cy="12" r="4" fill="currentColor" stroke="none" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  language: <><path d="M3 5h10M8 3v2M5 5c0 5 3 8 7 9M11 9c-1 4-4 6-7 7M14 21l4-9 4 9M15.5 17h5" /></>,
  shield: <><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /></>,
  external: <><path d="M14 5h5v5M19 5l-8 8M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5" /></>,
};

export function Icon({ name, size = 18, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {PATHS[name]}
    </svg>
  );
}

export type { IconName };
