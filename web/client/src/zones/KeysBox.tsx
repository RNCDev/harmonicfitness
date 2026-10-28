// The keys, language model and voice: which services have one, add, replace or remove. A key is never shown again.
import { useEffect, useRef, useState } from "react";
import { api, ApiError, NotSignedIn, plainError, type KeyState } from "../api";

function setOn(iso: string | null): string {
  if (!iso) return "Set";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "Set";
  return `Set ${d.toLocaleDateString([], { month: "short", day: "numeric" })}`;
}

function KeyRow({ k, onChanged, onSignedOut }: {
  k: KeyState; onChanged: (s: KeyState) => void; onSignedOut: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [asking, setAsking] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { if (editing) input.current?.focus(); }, [editing]);

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
    <div className="keys-row">
      <span className="keys-name">{k.name}</span>
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
            <button type="submit" disabled={busy || value === ""}>Save</button>
            <button type="button" className="quiet" onClick={close} disabled={busy}>Cancel</button>
            <a className="cx-s" href={k.key_page} target="_blank" rel="noopener noreferrer">Get a key</a>
          </span>
        </form>
      )}
      {error && <p className="cx-s err" role="alert" style={{ flexBasis: "100%" }}>{error}</p>}
    </div>
  );
}

export function KeysBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [keys, setKeys] = useState<KeyState[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    api.keys().then((k) => { if (live) setKeys(k); }, (e) => {
      if (!live) return;
      if (e instanceof NotSignedIn) return onSignedOut();
      setError("Couldn't load your keys.");
    });
    return () => { live = false; };
  }, [onSignedOut]);

  return (
    <div className="cx-box">
      <h3 className="cx-s" style={{ fontWeight: 600, margin: 0 }}>Keys</h3>
      {error && <p className="cx-s err" role="alert">{error}</p>}
      {keys === null && !error && <p className="cx-s">Loading…</p>}
      {(["model", "voice"] as const).map((kind) => {
        const rows = keys?.filter((k) => k.kind === kind) ?? [];
        if (rows.length === 0) return null;
        return (
          <div key={kind}>
            <h4 className="cx-s" style={{ fontWeight: 600, margin: "8px 0 0" }}>
              {kind === "model" ? "Language model" : "Voice"}
            </h4>
            {rows.map((k) => (
              <KeyRow key={k.service} k={k} onSignedOut={onSignedOut}
                onChanged={(s) => setKeys((all) => all && all.map((x) => (x.service === s.service ? s : x)))} />
            ))}
          </div>
        );
      })}
      <p className="cx-s">Stored encrypted, never shown again. Each key goes only to its own service, when you use it.</p>
    </div>
  );
}
