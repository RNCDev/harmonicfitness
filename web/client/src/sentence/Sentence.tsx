// The sentence: plain words and tappable tokens; a changed token rolls in.
import { useCallback, useEffect, useRef, useState } from "react";
import { TokenPopover } from "./TokenPopover";
import { shown, TOKEN_NAMES, type SentenceModel, type Token } from "./model";

function spoken(t: Token): string {
  const words = t.key === "minutes" ? `${t.value} minutes` : shown(t);
  return `${TOKEN_NAMES[t.key] ?? t.key}: ${words}`;
}

type Props = {
  model: SentenceModel;
  onChange: (key: string, value: string | number) => void;
  disabled?: boolean;
};

export function Sentence({ model, onChange, disabled }: Props) {
  const [open, setOpen] = useState<{ key: string; el: HTMLButtonElement } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const timer = useRef<number>();
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const openRef = useRef(open);
  openRef.current = open;
  const close = useCallback((refocus: boolean) => {
    if (refocus) openRef.current?.el.focus();
    setOpen(null);
  }, []);

  function pick(t: Token, value: string | number) {
    const el = open?.el;
    setOpen(null);
    el?.focus();
    if (value === t.value) return;
    onChange(t.key, value);
    setFlash(t.key);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setFlash(null), 900);
  }

  const openToken = open ? model.parts.find((p): p is Token => typeof p !== "string" && p.key === open.key) : undefined;

  return (
    <>
      <p className="sentence">
        {model.parts.map((p, i) =>
          typeof p === "string" ? (
            <span key={i}>{p}</span>
          ) : (
            <button key={p.key} type="button" disabled={disabled}
              className={`tok${open?.key === p.key ? " open" : ""}${flash === p.key ? " flash" : ""}`}
              aria-haspopup="listbox" aria-expanded={open?.key === p.key}
              aria-controls={open?.key === p.key ? `pop-${p.key}` : undefined}
              aria-label={spoken(p)}
              onClick={(e) => {
                const el = e.currentTarget;
                setOpen((o) => (o?.key === p.key ? null : { key: p.key, el }));
              }}>
              <span className="v" key={String(p.value)}>{shown(p)}</span>
            </button>
          ),
        )}
      </p>
      {open && openToken && (
        <TokenPopover token={openToken} anchor={open.el} onPick={(v) => pick(openToken, v)} onClose={close} />
      )}
    </>
  );
}
