// The stylesheet's breakpoints, for the script that must ask the same question (a media query can't read a token,
// so these are written twice: here and in styles/; theme.test.ts holds them to tokens.css's four).

/** A tablet or narrower: where Coaches puts its stage above the tiles. */
export const NARROW = "(max-width: 760px)";

/** Whether the window is that narrow now (false where the browser can't say). */
export const isNarrow = () => window.matchMedia?.(NARROW).matches ?? false;
