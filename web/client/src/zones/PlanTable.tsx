// The plan the agent showed: a row per block, then the format, equipment, total and what was left out.
import type { Plan } from "../api";

export function clock(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function PlanTable({ plan }: { plan: Plan }) {
  return (
    <section className="plan" aria-label="Today's plan">
      <table>
        <thead>
          <tr><th scope="col">Block</th><th scope="col">Movements</th><th scope="col">Dose</th><th scope="col">Time</th></tr>
        </thead>
        <tbody>
          {plan.rows.map((r, i) => (
            <tr key={i}>
              <th scope="row">{r.block}</th>
              <td>{r.movements.join(", ")}</td>
              <td>{r.dose}</td>
              <td>{clock(r.seconds)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="meta">{plan.format} · {plan.equipment} · Total {clock(plan.total_seconds)}</p>
      {plan.left_out && <p className="meta">{plan.left_out}</p>}
    </section>
  );
}
