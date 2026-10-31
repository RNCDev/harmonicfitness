// The keys: who writes the workouts (Claude, ChatGPT or Gemini: the listener picks one and adds its key) and the
// voices (optional), one row per service: a service that is both (Gemini) is one key and one row, so picking
// Gemini to write also voices its coach. Add, replace or remove. A key is never shown again. A set key shows what's
// left on its account where the service says (Fish Audio, ElevenLabs), else a link to its billing page.
import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, checkBalances, NotSignedIn, plainError, type Balance, type KeyState } from "../api";

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
    same.reports = same.reports || k.reports;
    same.billing_page = same.billing_page ?? k.billing_page;
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

/** A balance check's state for one row: still asking, its answer, or nothing to say. */
export type BalanceState = "checking" | Balance | null;

/** What's left, in a few words: dollars of credit, or this period's credits. Null when there's nothing to show. */
export function balanceText(b: Balance): { text: string; title: string } | null {
  if (!b.ok) return null;
  if (typeof b.usd === "number") {
    return { text: `$${b.usd.toLocaleString([], { minimumFractionDigits: 2, maximumFractionDigits: 2 })} left`,
      title: "API credit left" };
  }
  if (typeof b.used === "number" && typeof b.limit === "number") {
    const left = Math.max(0, b.limit - b.used);
    const resets = typeof b.resets === "number"
      ? `, resets ${new Date(b.resets * 1000).toLocaleDateString([], { month: "short", day: "numeric" })}` : "";
    return { text: `${left.toLocaleString()} credits left`,
      title: `${b.used.toLocaleString()} of ${b.limit.toLocaleString()} credits used this period${resets}` };
  }
  return null;
}

function BillingIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M9 2.5h4.5V7M13.5 2.5 7 9M11.5 9.5v3a1 1 0 0 1-1 1h-7a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1h3" />
    </svg>
  );
}

/** The balance where the service says it, else a link icon to its billing page. */
function BalanceTag({ k, balance }: { k: KeyRowState; balance: BalanceState }) {
  if (!k.set || !k.billing_page) return null;
  const link = { href: k.billing_page, target: "_blank", rel: "noopener noreferrer" };
  if (k.reports && balance === "checking") return <span className="keys-bal cx-s">Checking balance…</span>;
  const shown = k.reports && balance && balance !== "checking" ? balanceText(balance) : null;
  if (shown) return <a className="keys-bal" {...link} title={`${shown.title}. Open ${k.name} billing`}>{shown.text}</a>;
  return (
    <a className="keys-bill" {...link} aria-label={`${k.name} billing`} title={`See your balance on ${k.name}`}>
      <BillingIcon />
    </a>
  );
}

function KeyRow({ k, open, balance, onChanged, onSignedOut, onChoose }: {
  k: KeyRowState; open: number; balance: BalanceState; onChanged: (s: KeyRowState) => void; onSignedOut: () => void;
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
      <span className="keys-state">
        <span className="keys-when">{k.set ? setOn(k.updated_at) : "Not set"}</span>
        <BalanceTag k={k} balance={balance} />
      </span>
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

  // what's left on each account that can say: asked again whenever the set of such keys changes
  const asking = useMemo(() => keyRows(keys ?? []).filter((r) => r.set && r.reports)
    .map((r) => `${r.service}@${r.updated_at ?? ""}`).join(" "), [keys]);
  const [balances, setBalances] = useState<Record<string, Balance> | "checking" | null>(null);
  useEffect(() => {
    if (!asking) { setBalances(null); return; }
    let live = true;
    setBalances("checking");
    checkBalances({ live: () => live }).then((b) => { if (live) setBalances(b); }, (e) => {
      if (!live) return;
      if (e instanceof NotSignedIn) return onSignedOut();
      setBalances(null);   // the rows fall back to their billing links
    });
    return () => { live = false; };
  }, [asking, onSignedOut]);
  const balanceOf = (service: string): BalanceState =>
    balances === "checking" ? "checking" : balances?.[service] ?? null;

  const rows = keys ? keyRows(keys) : [];
  const required = rows.filter((r) => r.kind === "model");
  const optional = rows.filter((r) => r.kind !== "model");
  const group = (title: string, note: string, list: KeyRowState[], writers = false) => list.length > 0 && (
    <section className="keys-group" aria-label={title}>
      <h4 className="keys-h">{title}</h4>
      <p className="cx-s">{note}</p>
      <div role={writers ? "radiogroup" : undefined} aria-label={writers ? title : undefined}>
        {list.map((k) => (
          <KeyRow key={k.service} k={k} open={openFor(k.service)} balance={balanceOf(k.service)}
            onSignedOut={onSignedOut} onChanged={changed}
            onChoose={writers ? () => void choose(k.service, false) : undefined} />
        ))}
      </div>
    </section>
  );

  return (
    <section className="cx-box" aria-labelledby="cx-keys-h">
      <h3 className="cx-h" id="cx-keys-h">Keys</h3>
      {error && <p className="cx-s err" role="alert">{error}</p>}
      {keys === null && !error && <p className="cx-s">Loading…</p>}
      {group("Who writes your workouts", required.length > 1
        ? "Pick one, and add its key. Gemini's key is free, and also voices a coach."
        : "This key writes every workout.", required, required.length > 1)}
      {group("More voices (optional)", "Each key adds a coach with its own voice. Fish Audio costs the least.", optional)}
      <p className="cx-s keys-foot">Keys are stored encrypted and never shown again. Each one goes only to its own service, and only when it's used.</p>
    </section>
  );
}
