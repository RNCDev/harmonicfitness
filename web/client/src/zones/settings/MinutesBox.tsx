// Minutes, in Settings, on a site that sells them: what's left, the packs to buy (each opens the checkout page,
// which comes back here), and what was added and used. A workout takes its planned length when it's recorded.
import { useState } from "react";
import { api, type Pack } from "../../lib/api";
import { price, shortDay } from "../../lib/format";
import { SAID } from "../../lib/messages";
import { minutesSaid } from "../../lib/site";
import { useAction } from "../../lib/useAction";
import type { Minutes } from "../../lib/useMinutes";
import { Button } from "../../ui/Button";
import { Loadable, Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

/** "8¢ a minute": what a pack comes to, rounded to the cent. */
const each = (p: Pack) => `${Math.round(p.cents / p.minutes)}¢ a minute`;

/** "+60", "−25": minutes added or used, with a true minus sign. */
const signed = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0");

function Packs({ packs }: { packs: Pack[] }) {
  /** The pack whose checkout page is being opened. */
  const [going, setGoing] = useState<string | null>(null);
  const buy = useAction(async (pack: string) => {
    setGoing(pack);
    const { url } = await api.checkout(pack);
    window.location.assign(url);
  }, { fallback: SAID.checkout, hold: true });
  return (
    <>
      <ul className="min-packs" aria-label="Minutes to buy">
        {packs.map((p) => (
          <li key={p.id} className="min-pack">
            <span className="min-pack-n">{minutesSaid(p.minutes)}</span>
            <span className="min-pack-each">{each(p)}</span>
            <Button busy={buy.busy && going === p.id} busyLabel="Opening checkout…" disabled={buy.busy}
              onClick={() => void buy.run(p.id)}>{`Buy for ${price(p.cents)}`}</Button>
          </li>
        ))}
      </ul>
      <Notice tone="error">{buy.error}</Notice>
      <p className="cx-s">You pay on Stripe's page, and come back here. Your card never reaches this site.</p>
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
        && "Thank you. Your minutes show here once the payment clears, usually within a few seconds."}</Notice>
      <Notice>{back === "cancelled" && "The checkout was closed, and nothing was charged."}</Notice>
      <Loadable value={minutes.state} error={minutes.error} onRetry={minutes.reload} what="your minutes" room={160}>
        {(m) => (
          <>
            <p className="min-left"><strong>{m.minutes}</strong> {m.minutes === 1 ? "minute" : "minutes"} left</p>
            <p className="cx-s">A workout takes its length in minutes when it's recorded: thirty for a thirty-minute
              workout. Talking a workout over with your coach is free, a second take of the same script is free, and
              the minutes come back if a recording fails.</p>
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
