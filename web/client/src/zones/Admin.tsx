// The Admin page (0.87.0), for the accounts HARMONICFITNESS_ADMINS names: the site's books for a range of days.
// What it earned (minute packs through Stripe), what it cost (OpenRouter for writing and voices, Fly for the
// machines), the profit and margin, a day-by-day chart, what a minute sells for and costs, how the site is used, and
// each listener. A cost that isn't tracked says so and the profit is marked incomplete: never a silent $0.
import { useState } from "react";
import { api, type Books, type BooksDay } from "../lib/api";
import { count, pct, usd } from "../lib/format";
import { SAID } from "../lib/messages";
import { useResource } from "../lib/useResource";
import { Button } from "../ui/Button";
import { Loadable } from "../ui/Notice";
import { PageHeader } from "../ui/PageHeader";

const RANGES: { days: number; label: string }[] = [
  { days: 7, label: "7 days" }, { days: 30, label: "30 days" }, { days: 90, label: "90 days" }, { days: 0, label: "All time" },
];

export function AdminPage({ onClose }: { onClose: () => void }) {
  const [days, setDays] = useState(30);
  const res = useResource(() => api.books(days), SAID.books, [days]);
  return (
    <section className="page wide" aria-labelledby="admin-title">
      <PageHeader id="admin-title" title="Admin" onClose={onClose}>
        <p className="page-note">How HarmonicFitness is used, and what it earns and costs. Every day is a UTC day.</p>
      </PageHeader>
      <div className="ad-range" role="group" aria-label="Range">
        {RANGES.map((r) => (
          <Button key={r.days} variant="secondary" pressed={days === r.days} onClick={() => setDays(r.days)}>{r.label}</Button>
        ))}
      </div>
      <Loadable value={res.data} error={res.error} onRetry={res.reload} what="the books">
        {(b) => <BooksView b={b} />}
      </Loadable>
    </section>
  );
}

function BooksView({ b }: { b: Books }) {
  const m = b.money;
  const costs = [m.write, m.voice, m.unattributed, m.fly].reduce<number>((s, v) => s + (v ?? 0), 0) + m.fees;
  return (
    <div className="ad">
      <p className="ad-span">{b.from === b.to ? b.from : `${b.from} to ${b.to}`}</p>

      <section className="ad-heads" aria-label="Profit">
        <Head label="Net revenue" value={usd(m.net)} note={`${count(b.units.sales)} ${b.units.sales === 1 ? "pack" : "packs"} sold`} />
        <Head label="Costs" value={usd(costs)} note={m.missing.length ? "Incomplete" : "Stripe, OpenRouter, Fly"} warn={m.missing.length > 0} />
        <Head label={m.missing.length ? "Profit so far" : "Profit"} value={usd(m.profit)} note={m.missing.length ? `Leaves out ${m.missing.join(", ")}` : "After every cost"} warn={m.missing.length > 0} />
        <Head label="Margin" value={pct(m.margin)} note="Of net revenue" />
      </section>

      <section className="ad-block" aria-labelledby="ad-pl">
        <h2 className="ad-h" id="ad-pl">Profit and loss</h2>
        <table className="ad-table ad-pl">
          <tbody>
            <Row k="Packs sold" v={usd(m.sales)} />
            <Row k="Refunds" v={usd(-m.refunds)} />
            <Row k="Net revenue" v={usd(m.net)} strong />
            <Row k="Stripe fees" v={usd(-m.fees)} note="estimated at 2.9% + 30¢ a payment" />
            <Row k="OpenRouter: writing" v={cost(m.write)} note={m.write === null ? tracking(m) : undefined} />
            <Row k="OpenRouter: voices" v={cost(m.voice)} note={m.voice === null ? tracking(m) : m.voice_estimated ? "partly estimated" : undefined} />
            <Row k="OpenRouter: not claimed by a turn" v={cost(m.unattributed)}
              note={m.unattributed === null ? "starts when OpenRouter's daily count is read" : "OpenRouter's own count, less what turns reported"} />
            <Row k="Fly" v={cost(m.fly)} note={m.fly === null ? b.fly.why ?? undefined : "estimated from what runs"} />
            <Row k={m.missing.length ? "Profit so far" : "Gross profit"} v={usd(m.profit)} strong />
            <Row k="Margin" v={pct(m.margin)} />
          </tbody>
        </table>
      </section>

      <section className="ad-block" aria-labelledby="ad-days">
        <h2 className="ad-h" id="ad-days">Day by day</h2>
        <DayChart days={b.daily} />
      </section>

      <section className="ad-block" aria-labelledby="ad-units">
        <h2 className="ad-h" id="ad-units">A minute, sold and made</h2>
        <div className="ad-scroll">
          <table className="ad-table">
            <thead><tr><th>Pack</th><th>Price</th><th>A minute</th><th>After Stripe</th><th>Cost to make</th><th>Margin a minute</th></tr></thead>
            <tbody>
              {b.units.packs.map((p) => {
                const c = b.units.cost_per_minute;
                return (
                  <tr key={p.id}>
                    <th scope="row">{p.minutes} minutes</th><td>{usd(p.price)}</td><td>{usd(p.per_minute, true)}</td>
                    <td>{usd(p.after_fee, true)}</td><td>{c === null ? "Not tracked" : usd(c, true)}</td>
                    <td>{c === null ? "—" : pct((p.after_fee - c) / p.after_fee)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <dl className="ad-facts">
          <Fact k="Minutes sold" v={count(b.units.minutes_sold)} note={b.units.per_minute_sold === null ? undefined : `${usd(b.units.per_minute_sold, true)} a minute on average`} />
          <Fact k="Minutes recorded" v={count(b.units.minutes_recorded)} note={`${count(b.units.recordings)} ${b.units.recordings === 1 ? "recording" : "recordings"}`} />
          <Fact k="Minutes given away" v={count(b.units.minutes_given)} note="to start with, and by hand" />
          <Fact k="Writing a workout" v={b.units.write_per_recording === null ? "Not tracked" : usd(b.units.write_per_recording, true)} note="OpenRouter, per recording" />
          <Fact k="Voicing a minute" v={b.units.voice_per_minute === null ? "Not tracked" : usd(b.units.voice_per_minute, true)} note="OpenRouter" />
        </dl>
      </section>

      <section className="ad-block" aria-labelledby="ad-usage">
        <h2 className="ad-h" id="ad-usage">Who's using it</h2>
        <dl className="ad-facts">
          <Fact k="Accounts" v={count(b.usage.accounts)} note={`${count(b.usage.new_accounts)} new in this range`} />
          <Fact k="Active" v={count(b.usage.active)} note="talked to a coach or recorded" />
          <Fact k="Conversations" v={count(b.usage.turns)} note={`${count(b.usage.talking)} ${b.usage.talking === 1 ? "person" : "people"}, last ${b.usage.turn_days} days (kept no longer)`} />
          <Fact k="Paying" v={count(b.usage.payers)} note={`${count(b.usage.payers_ever)} ever, ${count(b.usage.repeat_payers)} more than once`} />
          <Fact k="Ever paid" v={pct(b.usage.paid_share)} note="of all accounts" />
          <Fact k="Ever recorded" v={pct(b.usage.recorded_share)} note="of all accounts" />
        </dl>
      </section>

      <section className="ad-block" aria-labelledby="ad-people">
        <h2 className="ad-h" id="ad-people">Listeners</h2>
        {b.listeners.length === 0 ? <p className="ad-none">No one did anything in this range.</p> : (
          <div className="ad-scroll">
            <table className="ad-table ad-people">
              <thead><tr><th>Listener</th><th>Joined</th><th>Paid</th><th>Bought</th><th>Recorded</th><th>Left</th><th>Cost</th><th>Profit</th></tr></thead>
              <tbody>
                {b.listeners.map((p) => (
                  <tr key={p.username}>
                    <th scope="row">{p.username}</th><td>{p.joined}</td><td>{usd(p.paid)}</td>
                    <td>{p.bought ? `${count(p.bought)} min` : "—"}</td>
                    <td>{p.recorded ? `${count(p.recorded)} min (${p.recordings})` : "—"}</td>
                    <td>{count(p.balance)} min</td><td>{p.cost === null ? "Not tracked" : usd(p.cost)}</td>
                    <td className={p.profit < 0 ? "ad-neg" : undefined}>{usd(p.profit)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {b.fly.monthly !== null && (
        <section className="ad-block" aria-labelledby="ad-fly">
          <h2 className="ad-h" id="ad-fly">Fly, a month</h2>
          <table className="ad-table ad-pl">
            <tbody>
              {b.fly.lines.map((l, i) => <Row key={i} k={l.what} v={usd(l.monthly)} />)}
              <Row k="Estimated" v={usd(b.fly.monthly)} strong />
            </tbody>
          </table>
          <p className="ad-none">Leaves out {b.fly.left_out.join(", ")}.</p>
        </section>
      )}
    </div>
  );
}

const cost = (v: number | null) => (v === null ? "Not tracked" : usd(-v));
const tracking = (m: Books["money"]) => (m.costs_since ? `tracked since ${m.costs_since}` : "tracked from this release on");

function Head({ label, value, note, warn = false }: { label: string; value: string; note: string; warn?: boolean }) {
  return (
    <div className="ad-head">
      <p className="ad-head-k">{label}</p>
      <p className="ad-head-v">{value}</p>
      <p className={`ad-head-n${warn ? " warn" : ""}`}>{note}</p>
    </div>
  );
}

function Row({ k, v, note, strong = false }: { k: string; v: string; note?: string; strong?: boolean }) {
  return (
    <tr className={strong ? "strong" : undefined}>
      <th scope="row">{k}{note && <span className="ad-note">{note}</span>}</th>
      <td>{v}</td>
    </tr>
  );
}

function Fact({ k, v, note }: { k: string; v: string; note?: string }) {
  return (
    <div className="ad-fact">
      <dt>{k}</dt>
      <dd><span className="ad-fact-v">{v}</span>{note && <span className="ad-note">{note}</span>}</dd>
    </div>
  );
}

/** Money in against money out, a pair of bars a day (a week a pair past 45 days), with each bar's numbers on hover
 * and the same numbers in a table under it. */
function DayChart({ days }: { days: BooksDay[] }) {
  const weekly = days.length > 45;
  const groups: { label: string; inn: number; out: number; known: boolean }[] = [];
  days.forEach((d, i) => {
    const out = (d.write ?? 0) + (d.voice ?? 0) + (d.unattributed ?? 0) + (d.fly ?? 0) + d.fees;
    const known = d.write !== null && d.voice !== null && d.fly !== null;
    if (!weekly || i % 7 === 0) groups.push({ label: weekly ? `Week of ${d.day}` : d.day, inn: 0, out: 0, known: true });
    const g = groups[groups.length - 1];
    g.inn += d.sales - d.refunds;
    g.out += out;
    g.known = g.known && known;
  });
  const top = Math.max(1, ...groups.map((g) => Math.max(g.inn, g.out)));
  const W = 720, H = 200, pad = 28, gw = (W - pad) / groups.length, bw = Math.max(2, Math.min(14, gw / 2 - 2));
  const y = (v: number) => H - 20 - (Math.max(0, v) / top) * (H - 36);
  const [show, setShow] = useState(false);
  return (
    <div className="ad-chart">
      <div className="ad-legend" aria-hidden="true">
        <span><i className="ad-key in" />Money in (net)</span>
        <span><i className="ad-key out" />Money out{groups.some((g) => !g.known) ? " (what's tracked)" : ""}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Money in and money out, ${weekly ? "week" : "day"} by ${weekly ? "week" : "day"}`}>
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line className="ad-grid" x1={pad} x2={W} y1={y(top * f)} y2={y(top * f)} />
            <text className="ad-axis" x={pad - 4} y={y(top * f) + 4} textAnchor="end">{top * f >= 10 ? `$${Math.round(top * f)}` : `$${(top * f).toFixed(1)}`}</text>
          </g>
        ))}
        {groups.map((g, i) => {
          const x = pad + i * gw + gw / 2;
          return (
            <g key={g.label} className="ad-bar">
              <title>{`${g.label}: in ${usd(g.inn)}, out ${usd(g.out)}${g.known ? "" : " (some costs not tracked)"}`}</title>
              <rect className="ad-hit" x={pad + i * gw} y={0} width={gw} height={H - 20} />
              <rect className="in" x={x - bw - 1} y={y(g.inn)} width={bw} height={Math.max(0, H - 20 - y(g.inn))} rx={2} />
              <rect className="out" x={x + 1} y={y(g.out)} width={bw} height={Math.max(0, H - 20 - y(g.out))} rx={2} />
            </g>
          );
        })}
        <line className="ad-base" x1={pad} x2={W} y1={H - 20} y2={H - 20} />
        <text className="ad-axis" x={pad} y={H - 4}>{groups[0]?.label.replace("Week of ", "")}</text>
        <text className="ad-axis" x={W} y={H - 4} textAnchor="end">{groups[groups.length - 1]?.label.replace("Week of ", "")}</text>
      </svg>
      <Button variant="text" onClick={() => setShow((s) => !s)} aria-expanded={show}>{show ? "Hide the table" : "Show as a table"}</Button>
      {show && (
        <div className="ad-scroll">
          <table className="ad-table">
            <thead><tr><th>{weekly ? "Week of" : "Day"}</th><th>Money in</th><th>Money out</th><th>Difference</th></tr></thead>
            <tbody>{groups.map((g) => (
              <tr key={g.label}><th scope="row">{g.label.replace("Week of ", "")}</th><td>{usd(g.inn)}</td>
                <td>{usd(g.out)}{g.known ? "" : " *"}</td><td>{usd(g.inn - g.out)}</td></tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
