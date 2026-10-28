// The choices for one token: a listbox under it (a sheet from the bottom on a phone).
import { useEffect, useLayoutEffect, useRef, type KeyboardEvent } from "react";
import { TOKEN_NAMES, type Token } from "./model";

type Props = {
  token: Token;
  anchor: HTMLElement;
  onPick: (value: string | number) => void;
  onClose: (refocus: boolean) => void;
};

export function TokenPopover({ token, anchor, onPick, onClose }: Props) {
  const box = useRef<HTMLDivElement>(null);
  const id = `pop-${token.key}`;

  // Place it under the token (above when there's no room), inside the window's 16 px gutters.
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    if (window.matchMedia?.("(max-width: 820px)").matches) {
      el.style.left = "";
      el.style.top = "";
    } else {
      const r = anchor.getBoundingClientRect();
      el.style.left = `${Math.max(16, Math.min(r.left, window.innerWidth - el.offsetWidth - 16))}px`;
      const below = r.bottom + 8;
      const h = el.offsetHeight;
      el.style.top = `${below + h > window.innerHeight - 8 ? Math.max(8, r.top - h - 8) : below}px`;
    }
    const opts = [...el.querySelectorAll<HTMLButtonElement>("[role=option]")];
    (opts.find((o) => o.getAttribute("aria-selected") === "true") ?? opts[0])?.focus();
  }, [anchor]);

  // A click anywhere else closes it, leaving focus where the click put it.
  useEffect(() => {
    const away = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!box.current?.contains(t) && !anchor.contains(t)) onClose(false);
    };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [anchor, onClose]);

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const opts = [...(box.current?.querySelectorAll<HTMLButtonElement>("[role=option]") ?? [])];
    const at = opts.indexOf(document.activeElement as HTMLButtonElement);
    const go = (i: number) => {
      e.preventDefault();
      opts[(i + opts.length) % opts.length]?.focus();
    };
    if (e.key === "Escape") {
      e.preventDefault();
      onClose(true);
    } else if (e.key === "ArrowDown") go(at + 1);
    else if (e.key === "ArrowUp") go(at - 1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(opts.length - 1);
    else if (e.key === "Tab") {
      e.preventDefault();
      onClose(true);
    }
  }

  const name = TOKEN_NAMES[token.key] ?? token.key;
  return (
    <>
      <div className="scrim" aria-hidden="true" />
      <div ref={box} className="pop" id={id} onKeyDown={onKey}>
        <div className="why" id={`${id}-why`}>{token.why}</div>
        <div role="listbox" aria-label={name} aria-describedby={`${id}-why`}>
          {token.options.map((o) => {
            const cur = o.value === token.value;
            return (
              <button key={String(o.value)} type="button" role="option" aria-selected={cur}
                className={`opt${cur ? " cur" : ""}`} onClick={() => onPick(o.value)}>
                {o.label}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
