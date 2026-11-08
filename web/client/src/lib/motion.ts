// The system's settings the page follows: less motion, and the theme's own colours for what's drawn in script.

/** Whether the system asks for less motion. False where matchMedia is missing or refuses. */
export function prefersReducedMotion(): boolean {
  try {
    return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/** A colour token's value (tokens.css), for canvas drawing; `fallback` where styles aren't loaded (tests). */
export function token(name: string, fallback: string): string {
  try {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  } catch {
    return fallback;
  }
}
