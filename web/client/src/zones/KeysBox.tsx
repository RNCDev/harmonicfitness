// The keys: who writes the workouts (Claude, ChatGPT or Gemini: the listener picks one and adds its key) and the
// voices (optional), one row per service: a service that is both (Gemini) is one key and one row, so picking
// Gemini to write also voices its coach. Add, replace or remove. A key is never shown again.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, NotSignedIn, plainError, type KeyState } from "../api";

/** One row: a service's key, and whether it writes the workouts (model), voices a coach (voice), or both. */
export type KeyRowState = KeyState & { voice: boolean };

/** The listing as rows: one per service, a model row first; a service listed as both is one row. */
export function keyRows(keys: KeyState[]): KeyRowState[] {
  const rows: KeyRowState[] = [];
  for (const k of keys) {
    const same = rows.find((r) => r.service === k.service);
    if (!same) {
      rows.push({ ...k, voice: k.kind === "voice" });
      continue;
    }
    if (k.kind === "model") { same.kind = "model"; same.writer = k.writer; }
    if (k.kind === "voice") same.voice = true;
    same.set = same.set || k.set;
    same.updated_at = same.updated_at ?? k.updated_at;
  }
  return rows;
}

/** Whether a language-model key is set; null until the listing is in. */
export function hasModelKey(keys: KeyState[] | null): boolean | null {
  return keys === null ? null : keys.some((k) => k.kind === "model" && k.set);
}

function setOn(iso: string | null): string {
  if (!iso) return "Set";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Set";
  return `Set ${d.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}

function KeyRow({ k, open, onChanged, onSignedOut, onChoose }: {
  k: KeyRowState; open: number; onChanged: (s: KeyRowState) => void; onSignedOut: () => void;
  /** On a model row: makes it the one that writes the workouts. */
  onChoose?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [asking, setAsking] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { if (open > 0) { setEditing(true); setAsking(false); } }, [open]);
  useEffect(() => { if (editing) input.current?.focus(); }, [editing, open]);

  function fail(e: unknown) {
    if (e instanceof NotSignedIn) return onSignedOut();
    setError(e instanceof ApiError || e instanceof Error ? plainError(e) : "Couldn't reach the server.");
  }

  function close() {
    setEditing(false);
    setValue("");
    setError(null);
  }

  async function save() {
    setBusy(true);
    setError(null);
    try {
      await api.setKey(k.service, value);
      setValue("");
      setEditing(false);
      onChanged({ ...k, set: true, updated_at: new Date().toISOString() });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteKey(k.service);
      setAsking(false);
      onChanged({ ...k, set: false, updated_at: null });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={`keys-row${onChoose ? " writer" : ""}${k.writer ? " on" : ""}`}>
      {onChoose ? (
        <label className="keys-pick">
          <input type="radio" name="writer" checked={!!k.writer} onChange={onChoose} />
          <span className="keys-name">{k.name}</span>
        </label>
      ) : <span className="keys-name">{k.name}</span>}
      <span className="keys-state">{k.set ? setOn(k.updated_at) : "Not set"}</span>
      {!editing && !asking && (
        <span className="keys-actions">
          <button type="button" className="quiet" aria-label={`${k.set ? "Replace" : "Add"} ${k.name} key`}
            onClick={() => { setEditing(true); setError(null); }}>
            {k.set ? "Replace" : "Add"}
          </button>
          {k.set && (
            <button type="button" className="quiet" aria-label={`Remove ${k.name} key`}
              onClick={() => { setAsking(true); setError(null); }}>Remove</button>
          )}
        </span>
      )}
      {k.kind === "model" && k.writer && !k.set && !editing && (
        <p className="cx-s keys-note">Add your {k.name} key to use it.</p>
      )}
      {k.kind === "model" && k.voice && (
        <p className="cx-s keys-note">The same key also voices a coach.</p>
      )}
      {asking && (
        <span className="keys-actions">
          <span className="cx-s">Remove your {k.name} key?</span>
          <button type="button" className="quiet" onClick={remove} disabled={busy}>Remove</button>
          <button type="button" className="quiet" onClick={() => setAsking(false)} disabled={busy}>Keep</button>
        </span>
      )}
      {editing && (
        <form className="keys-edit" autoComplete="off" onSubmit={(e) => { e.preventDefault(); void save(); }}>
          <label className="cx-s" htmlFor={`key-${k.service}`}>{k.name} key</label>
          <input id={`key-${k.service}`} ref={input} type="password" autoComplete="off" spellCheck={false}
            data-1p-ignore data-lpignore="true" data-bwignore data-form-type="other"
            value={value} onChange={(e) => setValue(e.target.value)} />
          <span className="keys-actions">
            <button type="submit" className="go" disabled={busy || value === ""}>Save</button>
            <button type="button" className="quiet" onClick={close} disabled={busy}>Cancel</button>
            <a className="cx-s" href={k.key_page} target="_blank" rel="noopener noreferrer">Get a key</a>
          </span>
        </form>
      )}
      {error && <p className="cx-s err" role="alert" style={{ flexBasis: "100%" }}>{error}</p>}
    </div>
  );
}

type Props = {
  onSignedOut: () => void;
  /** Every listing and change, for the page (the welcome card goes once a model key is set). */
  onKeys?: (keys: KeyState[]) => void;
  /** A row to open for a key: its service, and a count that grows with each ask; `choose` also makes it the writer. */
  openRow?: { service: string; n: number; choose?: boolean } | null;
};

export function KeysBox({ onSignedOut, onKeys, openRow }: Props) {
  const [keys, setKeys] = useState<KeyState[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const report = useRef(onKeys);
  report.current = onKeys;

  useEffect(() => {
    let live = true;
    api.keys().then((k) => { if (live) setKeys(k); }, (e) => {
      if (!live) return;
      if (e instanceof NotSignedIn) return onSignedOut();
      setError("Couldn't load your keys.");
    });
    return () => { live = false; };
  }, [onSignedOut]);

  useEffect(() => { if (keys) report.current?.(keys); }, [keys]);

  const changed = (s: KeyRowState) =>
    setKeys((all) => all && all.map((x) => (x.service === s.service ? { ...x, set: s.set, updated_at: s.updated_at } : x)));

  // the row opened by hand, after choosing a writer with no key yet
  const [opened, setOpened] = useState<{ service: string; n: number } | null>(null);
  async function choose(service: string, open: boolean) {
    setError(null);
    try {
      await api.setWriter(service);
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError(e instanceof ApiError ? plainError(e) : "Couldn't save that. Try again.");
      return;
    }
    const keyless = !keyRows(keys ?? []).find((r) => r.service === service)?.set;
    setKeys((all) => all && all.map((x) => (x.kind === "model" ? { ...x, writer: x.service === service } : x)));
    if (open || keyless) setOpened((o) => ({ service, n: (o?.n ?? 0) + 1 }));
  }
  const asked = useRef(0);
  useEffect(() => {
    if (!openRow?.choose || !keys || openRow.n === asked.current) return;
    asked.current = openRow.n;
    void choose(openRow.service, true);
  }, [openRow, keys]);
  const openFor = (service: string) =>
    (opened?.service === service ? opened.n : 0) + (openRow?.service === service && !openRow.choose ? openRow.n : 0);

  const rows = keys ? keyRows(keys) : [];
  const required = rows.filter((r) => r.kind === "model");
  const optional = rows.filter((r) => r.kind !== "model");
  const group = (title: string, note: string, list: KeyRowState[], writers = false) => list.length > 0 && (
    <section className="keys-group" aria-label={title}>
      <h4 className="keys-h">{title}</h4>
      <p className="cx-s">{note}</p>
      <div role={writers ? "radiogroup" : undefined} aria-label={writers ? title : undefined}>
        {list.map((k) => (
          <KeyRow key={k.service} k={k} open={openFor(k.service)} onSignedOut={onSignedOut} onChanged={changed}
            onChoose={writers ? () => void choose(k.service, false) : undefined} />
        ))}
      </div>
    </section>
  );

  return (
    <div className="cx-box">
      <h3 className="cx-h">Keys</h3>
      {error && <p className="cx-s err" role="alert">{error}</p>}
      {keys === null && !error && <p className="cx-s">Loading…</p>}
      {group("Who writes your workouts", required.length > 1
        ? "Pick one, and add its key. Gemini's key is free, and also voices a coach."
        : "Your workouts are written with this key.", required, required.length > 1)}
      {group("More voices (optional)", "Each key adds its own coach. Fish Audio is the cheapest.", optional)}
      <p className="cx-s">Stored encrypted, never shown again. Each key goes only to its own service, when you use it.</p>
    </div>
  );
}
