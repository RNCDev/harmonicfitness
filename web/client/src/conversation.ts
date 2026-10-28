// The conversation with the agent: load the latest, start or continue it, follow each turn's job.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api, ApiError, NotSignedIn, plainError, useJob, type AnswerValues, type Conversation,
} from "./api";
import { localDate, localNow } from "./sentence/model";

const when = () => ({ today: localDate(), now: localNow() });

export function useConversation(onSignedOut: () => void) {
  const [conv, setConv] = useState<Conversation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [noKey, setNoKey] = useState(false);
  const [posting, setPosting] = useState(false);
  const { job, watch, stop } = useJob(onSignedOut);
  const watched = useRef(0);

  const follow = useCallback((jobId: number) => {
    watched.current = jobId;
    watch(jobId);
  }, [watch]);

  const fail = useCallback((e: unknown) => {
    if (e instanceof NotSignedIn) return onSignedOut();
    setNoKey(e instanceof ApiError && e.status === 409 && /key/i.test(e.message));
    setError(plainError(e));
  }, [onSignedOut]);

  const adopt = useCallback((c: Conversation | undefined) => {
    setConv(c ?? null);
    if (c?.state === "working" && c.job_id && c.job_id !== watched.current) follow(c.job_id);
  }, [follow]);

  // The page opens on the latest conversation.
  useEffect(() => {
    api.latestConversation().then(adopt, fail);
  }, [adopt, fail]);

  // A turn's job ended: read the conversation again.
  const id = conv?.id;
  useEffect(() => {
    if (!job || id === undefined) return;
    if (job.state === "failed" && job.error) setError(plainError(new ApiError(0, job.error)));
    if (job.state === "done" || job.state === "failed") {
      api.conversation(id).then((c) => setConv(c), fail);
    }
  }, [job?.id, job?.state]); // eslint-disable-line react-hooks/exhaustive-deps

  const turn = useCallback(async (run: () => Promise<{ job_id: number }>, show: (c: Conversation) => Conversation) => {
    setError(null);
    setNoKey(false);
    setPosting(true);
    try {
      const { job_id } = await run();
      setConv((c) => (c ? show(c) : c));
      follow(job_id);
    } catch (e) {
      fail(e);
    } finally {
      setPosting(false);
    }
  }, [fail, follow]);

  const working = posting || conv?.state === "working" || job?.state === "queued" || job?.state === "running";

  const send = useCallback(async (line: string) => {
    if (conv) {
      await turn(() => api.sendMessage(conv.id, line, when()), (c) => ({
        ...c, state: "working", question: null, lines: [...c.lines, { role: "user", text: line }],
      }));
      return;
    }
    setError(null);
    setNoKey(false);
    setPosting(true);
    try {
      const { id: cid, job_id } = await api.startConversation(line, when());
      setConv({ id: cid, state: "working", job_id, lines: [{ role: "user", text: line }], question: null, plan: null });
      follow(job_id);
    } catch (e) {
      fail(e);
    } finally {
      setPosting(false);
    }
  }, [conv, fail, follow, turn]);

  const answer = useCallback(async (toolCallId: string, values: AnswerValues) => {
    if (!conv) return;
    await turn(() => api.answer(conv.id, toolCallId, values, when()),
      (c) => ({ ...c, state: "working", question: null }));
  }, [conv, turn]);

  return { conv, working, error, noKey, send, answer, job, stop };
}
