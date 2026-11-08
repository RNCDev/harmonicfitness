// The cards that wait on the listener's approval in the chat: a priced recording (Record it), a workout for later
// (Schedule it), and one scheduled (Cancel).
import type { Later, Offer, Plan } from "../../lib/api";
import { count, dollars, mss, timeOfDay } from "../../lib/format";
import { serviceName } from "../../lib/keys";
import { Quiet, useAction } from "../../lib/useAction";
import { ahead } from "../../lib/when";
import { Button } from "../../ui/Button";

/** An approval button: busy from the tap until its screen goes; a refusal (false) gives it back. */
function useApproval(act?: () => Promise<boolean> | void) {
  return useAction(async () => { if ((await act?.()) === false) throw new Quiet(); }, { hold: true });
}

/** The plan, from the draft's own segments: each movement's sets and time, then the rests and the talk. */
function PlanTable({ plan }: { plan: Plan }) {
  return (
    <table className="plan">
      <thead><tr><th scope="col">Part</th><th scope="col">Sets</th><th scope="col">Time</th></tr></thead>
      <tbody>
        {plan.rows.map((r) => (
          <tr key={r.what}><td>{r.what}</td><td>{r.kind === "talk" ? "" : r.segments}</td><td>{mss(r.seconds)}</td></tr>
        ))}
      </tbody>
      <tfoot><tr><th scope="row">Total</th><td /><td>{mss(plan.seconds)}</td></tr></tfoot>
    </table>
  );
}

/** Said once, on the card before the first recording: where the script goes, and what that means. */
function privacyNote(service: string): string {
  const name = serviceName(service);
  return `Recording sends the script to ${name}, and it can mention your injuries ("easy on that left knee").`
    + (service === "gemini"
      ? " On Gemini's free tier, Google may use what it's sent to improve its models, with human review; a paid key doesn't."
      : "")
    + " Your key is stored encrypted on this site, never shown again, and removed in Settings.";
}

export function RecordOffer({ offer, onRecord }: { offer: Offer; onRecord?: () => Promise<boolean> | void }) {
  const rec = useApproval(onRecord);
  const price = offer.usd < 0.01 ? dollars(offer.usd) : `about ${dollars(offer.usd)}`;
  return (
    <div className="m a offer">
      <p><strong>{offer.name}</strong> is ready to record with {offer.coach}.</p>
      {offer.plan && offer.plan.rows.length > 0 && <PlanTable plan={offer.plan} />}
      <p className="cx-s">{count(offer.chars)} characters on {serviceName(offer.service)}, {price}
        {offer.design ? ", including designing the coach's voice" : ""}. It's charged to your own key.</p>
      {offer.first && <p className="cx-s privacy">{privacyNote(offer.service)}</p>}
      <Button variant="primary" busy={rec.busy} busyLabel="Starting…" onClick={() => void rec.run()}>
        {`Record it (${price})`}
      </Button>
    </div>
  );
}

/** The check-in is done for a workout at a later time: what it costs, the most it may, and Schedule it. */
export function LaterOffer({ later, onSchedule }: { later: Later; onSchedule?: () => Promise<boolean> | void }) {
  const go = useApproval(onSchedule);
  const at = new Date(later.at);
  const cap = dollars(later.ceiling_usd ?? 0);
  return (
    <div className="m a offer">
      <p>Your {later.minutes}-minute workout with {later.coach} is planned for <strong>{ahead(at)}</strong>.</p>
      <p className="cx-s">About {dollars(later.usd ?? 0)}, and never more than {cap}, charged to your own key.
        {" "}{later.coach ?? "Your coach"} writes and records it fifteen minutes before, with that hour's news and weather, so it's ready when you are.</p>
      <Button variant="primary" busy={go.busy} busyLabel="Scheduling…" onClick={() => void go.run()}>
        {`Schedule it (up to ${cap})`}
      </Button>
    </div>
  );
}

/** A scheduled workout, waiting for its time; Cancel takes it back before the writing begins. */
export function Scheduled({ later, onCancel }: { later: Later; onCancel?: () => Promise<boolean> | void }) {
  const stop = useApproval(onCancel);
  const at = new Date(later.at);
  const due = later.due ? new Date(later.due) : null;
  return (
    <div className="m a offer">
      <p>Scheduled for <strong>{ahead(at)}</strong>{later.coach ? ` with ${later.coach}` : ""}.</p>
      <p className="cx-s">{due ? `Writing starts at ${timeOfDay(due)}` : "Writing starts fifteen minutes before"}, on
        our side, so you can close this page. The workout appears here, ready to play, by {timeOfDay(at)}.</p>
      <Button variant="outline" busy={stop.busy} busyLabel="Cancelling…" onClick={() => void stop.run()}>Cancel</Button>
    </div>
  );
}
