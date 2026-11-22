// Minutes, in Settings, on a site that sells them: what's left, the packs to buy (each opens the checkout page,
// which comes back here), and what was added and used. A workout takes its planned length when it's recorded.
import { useState } from "react";
import { api, type Pack } from "../../lib/api";
import { price, shortDay } from "../../lib/format";
import { SAID } from "../../lib/messages";
import { useAction } from "../../lib/useAction";
import type { Minutes } from "../../lib/useMinutes";
import { Button } from "../../ui/Button";
import { Loadable, Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

/** "4.2¢ a minute": what a pack comes to, to a tenth of a cent. */
const each = (p: Pack) => `${(Math.round((p.cents / p.minutes) * 10) / 10).toFixed(1)}¢ a minute`;

/** "+60", "−25": minutes added or used, with a true minus sign. */
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0");

/** What a pack saves on the smallest one's price a minute, in whole percent; 0 for the smallest itself. */
const saving = (p: Pack, base: Pack) => Math.max(0, Math.round((1 - (p.cents / p.minutes) / (base.cents / base.minutes)) * 100));

function Packs({ packs }: { packs: Pack[] }) {
  /** The pack whose checkout page is being opened. */
  const [going, setGoing] = useState<string | null>(null);
  const buy = useAction(async (pack: string) => {
    setGoing(pack);
    const { url } = await api.checkout(pack);
    window.location.assign(url);
  }, { fallback: SAID.checkout, hold: true });
  const base = packs.reduce((a, b) => (b.cents / b.minutes > a.cents / a.minutes ? b : a));
  const best = packs.reduce((a, b) => (b.cents / b.minutes < a.cents / a.minutes ? b : a));
  return (
    <>
      <ul className="min-packs" aria-label="Minutes to buy">
        {packs.map((p) => {
          const off = saving(p, base);
          const top = packs.length > 1 && p.id === best.id;
          const workouts = Math.floor(p.minutes / 30);
          return (
            <li key={p.id} className="min-pack" data-best={top || undefined}>
              {top && <span className="min-pack-tag">Best value</span>}
              <span className="min-pack-n"><strong>{p.minutes}</strong> minutes</span>
              {workouts > 0 && <span className="min-pack-use">{workouts} half-hour {workouts === 1 ? "workout" : "workouts"}</span>}
              <span className="min-pack-price">{price(p.cents)}</span>
              <span className="min-pack-each">{each(p)}{off > 0 && <> · <em>save {off}%</em></>}</span>
              <Button busy={buy.busy && going === p.id}
                busyLabel="Opening…" disabled={buy.busy} onClick={() => void buy.run(p.id)}>
                {`Buy for ${price(p.cents)}`}</Button>
            </li>
          );
        })}
      </ul>
      <Notice tone="error">{buy.error}</Notice>
      <p className="cx-s">Paid securely on Stripe. Minutes never expire.</p>
    </>
  );
}

export function MinutesBox({ minutes, back = null }: {
  minutes: Minutes;
  /** How the listener just came back from the checkout page, if they did. */
  back?: "bought" | "cancelled" | null;
}) {
  return (
    <Section id="cx-minutes" title="Minutes">
      <Notice tone="done">{back === "bought"
        && "Thanks! Your minutes appear here in a few seconds."}</Notice>
      <Notice>{back === "cancelled" && "Checkout closed. Nothing was charged."}</Notice>
      <Loadable value={minutes.state} error={minutes.error} onRetry={minutes.reload} what="your minutes" room={160}>
        {(m) => (
          <>
            <p className="min-left"><strong>{m.minutes}</strong> {m.minutes === 1 ? "minute" : "minutes"} left</p>
            <p className="cx-s">A recording uses its length in minutes. Planning with your coach is free, so is
              one re-record, and a failed recording gives its minutes back.</p>
            {m.can_buy && m.packs.length > 0 ? <Packs packs={m.packs} />
              : <p className="cx-s">Minutes aren't on sale here just now.</p>}
            {m.history.length > 0 && (
              <>
                <h4 className="label min-h">Added and used</h4>
                <ul className="min-log">
                  {m.history.map((h, i) => (
                    <li key={`${h.at}:${i}`}>
                      <span className="min-day">{shortDay(h.at)}</span>
                      <span className="min-what">{h.what}</span>
                      <span className="min-n">{signed(h.minutes)}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Loadable>
    </Section>
  );
}
