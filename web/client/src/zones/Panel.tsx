// The working panel: the open check-in question, else the plan, else an empty state.
import type { AnswerValues, OpenQuestion, Plan } from "../api";
import { PlanTable } from "./PlanTable";
import { Question } from "./Question";

type Props = {
  question?: OpenQuestion | null;
  plan?: Plan | null;
  working?: boolean;
  /** Resolves true when the answer went through; false lets the form send again. */
  onAnswer?: (toolCallId: string, values: AnswerValues) => Promise<boolean> | void;
};

export function Panel({ question = null, plan = null, working = false, onAnswer = () => {} }: Props) {
  if (question) {
    return (
      <section aria-label="Check-in">
        <Question key={question.tool_call_id} ask={question} onSend={onAnswer} disabled={working} />
      </section>
    );
  }
  if (plan) return <PlanTable plan={plan} />;
  return (
    <section className="panel-empty" aria-label="Today's plan">
      <p>Change any underlined word, then start.</p>
    </section>
  );
}
