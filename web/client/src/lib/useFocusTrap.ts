// A panel that holds the keyboard while it's open (the Settings drawer, the body chart): focus moves in, Tab
// stays inside, Escape closes, and focus goes back where it came from. With `inert`, the rest of the page can't be
// reached at all while it's open.
import { useEffect, useRef, type RefObject } from "react";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), "
  + "textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

function focusables(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => !el.closest("[hidden], [inert]"));
}

export function useFocusTrap(ref: RefObject<HTMLElement>, active: boolean, opts: {
  onEscape?: () => void; returnFocus?: RefObject<HTMLElement>; inert?: boolean } = {}) {
  const { inert = false } = opts;
  const latest = useRef(opts);
  latest.current = opts;   // the newest callbacks, without starting the trap over on each render
  useEffect(() => {
    const root = ref.current;
    if (!active || !root) return;
    const before = document.activeElement as HTMLElement | null;
    // focus moves in, unless something inside already has it (a key's box opened from the welcome card)
    if (!root.contains(document.activeElement)) focusables(root)[0]?.focus();
    // the rest of the page sleeps: every sibling but the panel and its scrim
    const slept: Element[] = [];
    if (inert && root.parentElement) {
      for (const el of root.parentElement.children) {
        if (el !== root && !el.hasAttribute("data-scrim") && !el.hasAttribute("inert")) {
          el.setAttribute("inert", "");
          slept.push(el);
        }
      }
    }
    const onKey = (e: KeyboardEvent) => {
      const { onEscape } = latest.current;
      if (e.key === "Escape" && onEscape) { e.preventDefault(); onEscape(); return; }
      if (e.key !== "Tab") return;
      const all = focusables(root);
      if (all.length === 0) return;
      const first = all[0], last = all[all.length - 1];
      const at = document.activeElement;
      if (e.shiftKey && (at === first || !root.contains(at))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && (at === last || !root.contains(at))) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      for (const el of slept) el.removeAttribute("inert");
      const back = latest.current.returnFocus?.current ?? before;
      if (back && document.contains(back) && root.contains(document.activeElement)) back.focus();
    };
  }, [ref, active, inert]);
}
