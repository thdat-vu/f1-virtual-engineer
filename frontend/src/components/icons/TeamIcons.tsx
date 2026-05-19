/**
 * Team icons rendered from PNG assets in `public/icons/iconsf1/`.
 *
 * The id → filename map handles spelling drift between team ids used in code
 * and the on-disk asset names (`rb` → racingbull, `cadillac` → cadilac).
 */

import Image from "next/image";

const TEAM_ICON_FILES = {
  ferrari:     "ferrari.png",
  redbull:     "redbull.png",
  mercedes:    "mercedes.png",
  mclaren:     "mclaren.png",
  alpine:      "alpine.png",
  astonmartin: "astonmartin.png",
  williams:    "williams.png",
  haas:        "haas.png",
  rb:          "racingbull.png",
  audi:        "audi.png",
  cadillac:    "cadilac.png",
} as const;

export type TeamIconId = keyof typeof TEAM_ICON_FILES;

export function TeamIcon({
  id,
  size = 11,
  className,
}: {
  id: string;
  size?: number;
  className?: string;
}) {
  const file = TEAM_ICON_FILES[id as TeamIconId];
  if (!file) {
    return (
      <div
        aria-hidden
        className={className}
        style={{
          width: size,
          height: size,
          borderRadius: 2,
          background: "rgba(245,245,247,0.12)",
        }}
      />
    );
  }
  return (
    <Image
      src={`/icons/iconsf1/${file}`}
      alt={`${id} logo`}
      width={size}
      height={size}
      className={className}
      // Lock both dimensions in the inline style so a parent flex/grid
      // can't stretch one axis and break the aspect-ratio guard that
      // next/image runs at dev time.
      style={{ width: size, height: size, objectFit: "contain" }}
      unoptimized
    />
  );
}
