// The keys: who writes the workouts (OpenRouter, Gemini, Claude or ChatGPT: the listener picks one and adds its key)
// and the voices (optional), one row per service. A service that is both (OpenRouter, Gemini) is one key and one row,
// listed first since it's all a listener needs; picking it to write also voices its coaches, and the other voice
// keys wait behind a link. Add, replace or remove. A key is never shown again. A set key shows what's left on its
// account where the service says, else a link to its billing page, beside its name.
import { useEffect, useMemo, useRef, useState } from "react";
import { api, NotSignedIn, plainError, type Balance, type KeyState } from "../lib/api";
import { balance, count, shortDay } from "../lib/format";
import { useKeyAsk } from "../lib/keyAsk";
import { keyRows, writerRank, type KeyRowState } from "../lib/keys";
import { useAction } from "../lib/useAction";
import { useBalances } from "../lib/useBalances";
import { useResource } from "../lib/useResource";
import { Button } from "../ui/Button";
import { ConfirmInline } from "../ui/ConfirmInline";
import { Field } from "../ui/Field";
import { Icon } from "../ui/icons";
import { Loadable, Notice } from "../ui/Notice";

const setOn = (iso: string | null) => (shortDay(iso) ? `Key added ${shortDay(iso)}` : "Key added");

/** A balance check's state for one row: still asking, its answer, or nothing to say. */
export type BalanceState = "checking" | Balance | null;

/** What's left, in a few words: dollars of credit, or this period's credits. Null when there's nothing to show. */
export function balanceText(b: Balance): { text: string; title: string } | null {
  if (!b.ok) return null;
  if (typeof b.usd === "number") {
    return { text: `${balance(b.usd)} left`,
      title: "API credit left" };
  }
  if (typeof b.used === "number" && typeof b.limit === "number") {
    const left = Math.max(0, b.limit - b.used);
    const resets = typeof b.resets === "number"
      ? `, resets ${shortDay(new Date(b.resets * 1000))}` : "";
    return { text: `${count(left)} credits left`,
      title: `${count(b.used)} of ${count(b.limit)} credits used this period${resets}` };
  }
  return null;
}

/** The balance where the service says it, else a link icon to its billing page. */
function BalanceTag({ k, balance }: { k: KeyRowState; balance: BalanceState }) {
  if (!k.set || !k.billing_page) return null;
  const link = { href: k.billing_page, target: "_blank", rel: "noopener noreferrer" };
  if (k.reports && balance === "checking") return <span className="keys-bal">Checking balance…</span>;
  const shown = k.reports && balance && balance !== "checking" ? balanceText(balance) : null;
  if (shown) return <a className="keys-bal" {...link} title={`${shown.title}. Open ${k.name} billing`}>{shown.text}</a>;
  return (
    <a className="keys-bill" {...link} aria-label={`${k.name} billing`} title={`See your balance on ${k.name}`}>
      <Icon name="billing" size={15} weight={2.25} />
    </a>
  );
}

function KeyRow({ k, open, balance, onChanged, onChoose }: {
  k: KeyRowState; open: number; balance: BalanceState; onChanged: (s: KeyRowState) => void;
  /** On a model row: makes it the one that writes the workouts. */
  onChoose?: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [asking, setAsking] = useState(false);
  const [value, setValue] = useState("");
  const [saved, setSaved] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const row = useRef<HTMLDivElement>(null);

  useEffect(() => { if (open > 0) { setEditing(true); setAsking(false); } }, [open]);
  useEffect(() => { if (editing) input.current?.focus(); }, [editing, open]);

  const save = useAction(async () => {
    await api.setKey(k.service, value);
    setValue("");
    setEditing(false);
    setSaved(`${k.name} key saved.`);
    onChanged({ ...k, set: true, updated_at: new Date().toISOString() });
  });
  const remove = useAction(async () => {
    await api.deleteKey(k.service);
    setAsking(false);
    setSaved(`${k.name} key removed.`);
    onChanged({ ...k, set: false, updated_at: null });
  });

  function close() {
    setEditing(false);
    setValue("");
    save.clear();
  }
  // an open key box closes on a click anywhere outside its row, unless it's saving
  const closeRef = useRef(close);
  closeRef.current = close;
  useEffect(() => {
    if (!editing || save.busy) return;
    const away = (e: PointerEvent) => { if (!row.current?.contains(e.target as Node)) closeRef.current(); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [editing, save.busy]);

  return (
    <div ref={row} className={`keys-row${onChoose ? " writer" : ""}${k.writer ? " on" : ""}`}>
      {/* one line: the name, its tag and what's left on the left, its buttons on the right (when it was set is the
          name's tooltip); anything opened goes below, across the row */}
      <span className="keys-id">
        <span className="keys-label" title={k.set ? setOn(k.updated_at) : undefined}>
          {/* a writer not in use: its name is a button whose area covers the row, so a click anywhere picks it */}
          {onChoose && !k.writer
            ? <Button variant="bare" className="keys-name keys-pick" aria-label={`Use ${k.name} to write your workouts`}
                onClick={onChoose}>{k.name}</Button>
            : <span className="keys-name">{k.name}</span>}
          {k.kind === "model" && k.voice && <span className="keys-tag" title="This key also voices your coaches">+ voices</span>}
          {onChoose && k.writer && <span className="keys-use">In use</span>}
          {k.set && <BalanceTag k={k} balance={balance} />}
        </span>
      </span>
      {!editing && !asking && (
        <span className="keys-actions">
          <Button variant="text" aria-label={`${k.set ? "Replace" : "Add"} ${k.name} key`}
            onClick={() => { setEditing(true); setSaved(null); save.clear(); }}>
            {k.set ? "Replace" : "Add"}
          </Button>
          {k.set && (
            <Button variant="text" aria-label={`Remove ${k.name} key`}
              onClick={() => { setAsking(true); setSaved(null); remove.clear(); }}>Remove</Button>
          )}
        </span>
      )}
      {k.kind === "model" && k.writer && !k.set && !editing && (
        <p className="cx-s keys-note">Add your {k.name} key to use it.</p>
      )}
      {asking && (
        <ConfirmInline className="keys-actions" question={`Remove your ${k.name} key?`} confirm="Remove" keep="Keep"
          busy={remove.busy} onConfirm={() => void remove.run()} onKeep={() => setAsking(false)} />
      )}
      {editing && (
        <form className="keys-edit" autoComplete="off" onSubmit={(e) => { e.preventDefault(); void save.run(); }}>
          <Field id={`key-${k.service}`} label={`${k.name} key`} error={save.error}>
            <input ref={input} className="input" type="password" autoComplete="off" spellCheck={false}
              data-1p-ignore data-lpignore="true" data-bwignore data-form-type="other"
              value={value} onChange={(e) => setValue(e.target.value)} />
          </Field>
          <span className="keys-actions">
            <Button type="submit" variant="primary" busy={save.busy} disabled={value === ""}>Save</Button>
            <Button variant="outline" onClick={close} disabled={save.busy}>Cancel</Button>
            <a className="keys-get" href={k.key_page} target="_blank" rel="noopener noreferrer">
              Get a key <Icon name="billing" size={14} weight={2.25} />
            </a>
          </span>
        </form>
      )}
      <Notice tone="error">{remove.error}</Notice>
      {!editing && !asking && <Notice tone="done" className="cx-s">{saved}</Notice>}
    </div>
  );
}

type Props = {
  /** Every listing and change, for the page (the welcome card goes once a model key is set). */
  onKeys?: (keys: KeyState[]) => void;
};

export function KeysBox({ onKeys }: Props) {
  // a row asked for from elsewhere (lib/keyAsk.ts): its service, and `choose` also makes it the writer
  const openRow = useKeyAsk();
  const res = useResource(api.keys, "Couldn't load your keys.");
  const keys = res.data, setKeys = res.set;
  const [error, setError] = useState<string | null>(null);
  const report = useRef(onKeys);
  report.current = onKeys;

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
      if (!(e instanceof NotSignedIn)) setError(plainError(e, "Couldn't save that. Try again."));
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
  const balances = useBalances(asking);
  const balanceOf = (service: string): BalanceState =>
    balances === "checking" ? "checking" : balances?.[service] ?? null;

  const rows = keys ? keyRows(keys) : [];
  // the keys that write and voice come first: one of them is all a listener needs
  const required = rows.filter((r) => r.kind === "model").sort((a, b) => writerRank(a.service, true) - writerRank(b.service, true));
  const optional = rows.filter((r) => r.kind !== "model");
  // One key that writes and voices (Gemini, OpenRouter) needs nothing more: the voice keys wait behind a link,
  // unless one is set already or a row was asked for.
  const [moreVoices, setMoreVoices] = useState(false);
  const writer = required.find((r) => r.writer);
  const oneKey = !!writer?.set && writer.voice;
  const voicesShown = !oneKey || moreVoices || optional.some((r) => r.set)
    || optional.some((r) => r.service === openRow?.service || r.service === opened?.service);
  const group = (title: string, note: string, list: KeyRowState[], writers = false) => list.length > 0 && (
    <section className="keys-group" aria-label={title}>
      <h4 className="keys-h">{title}</h4>
      <p className="cx-s">{note}</p>
      <div>
        {list.map((k) => (
          <KeyRow key={k.service} k={k} open={openFor(k.service)} balance={balanceOf(k.service)} onChanged={changed}
            onChoose={writers ? () => void choose(k.service, false) : undefined} />
        ))}
      </div>
    </section>
  );

  return (
    <section className="cx-box cx-sec" id="cx-keys" aria-labelledby="cx-keys-h">
      <h3 className="head cx-h" id="cx-keys-h">Keys</h3>
      <p className="cx-s">Keys are encrypted, never shown again, and sent only to their own service.</p>
      <Notice tone="error">{error}</Notice>
      <Loadable value={keys} error={res.error} onRetry={res.reload} what="your keys" room={180}>
        {() => (
          <>
            {group("Who writes your workouts", required.length > 1
              ? "Pick one. A key marked + voices also voices your coaches, so it's all you need."
              : "This key writes every workout.", required, required.length > 1)}
            {voicesShown
              ? group("More voices (optional)", "Each adds coaches of its own.", optional)
              : optional.length > 0 && (
                <section className="keys-group keys-more" aria-label="More voices (optional)">
                  <p className="cx-s">Your {writer?.name} key voices your coaches too. Nothing else to add.</p>
                  <Button variant="text" onClick={() => setMoreVoices(true)}>Add another voice (optional)</Button>
                </section>
              )}
          </>
        )}
      </Loadable>
    </section>
  );
}
