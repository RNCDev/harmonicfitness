// The chat zone: the lines so far, a "Thinking…" line while a turn runs, and the box to write in.
import { useState } from "react";
import type { ChatLine } from "../api";

type Props = {
  lines: ChatLine[];
  working: boolean;
  error: string | null;
  noKey: boolean;
  onSend: (line: string) => void;
  onOpenKeys: () => void;
};

export function Chat({ lines, working, error, noKey, onSend, onOpenKeys }: Props) {
  const [text, setText] = useState("");

  function send() {
    const line = text.trim();
    if (!line || working) return;
    setText("");
    onSend(line);
  }

  return (
    <aside className="chat" aria-label="Chat">
      <div className="chat-log" role="log" aria-live="polite">
        {lines.length === 0 && !working && (
          <p className="m a">Hi. Tap an underlined word to change it, then start. Or just tell me what you want.</p>
        )}
        {lines.map((l, i) => (
          <p key={i} className={`m ${l.role === "user" ? "u" : "a"}`}>{l.text}</p>
        ))}
        {working && <p className="m a thinking">Thinking…</p>}
      </div>
      {error && (
        <div className="chat-error" role="alert">
          <p>{error}</p>
          {noKey && <button type="button" className="go alt" onClick={onOpenKeys}>Open Keys</button>}
        </div>
      )}
      <form className="chat-form" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="sr" htmlFor="chat-box">Message</label>
        <textarea id="chat-box" rows={2} value={text} disabled={working}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              send();
            }
          }} />
        <button type="submit" className="go alt" disabled={working || !text.trim()}>Send</button>
      </form>
    </aside>
  );
}
