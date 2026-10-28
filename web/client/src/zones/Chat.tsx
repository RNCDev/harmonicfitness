// The chat zone. In this slice it holds one line; the agent comes later.
export function Chat() {
  return (
    <aside className="chat" aria-label="Chat">
      <div className="chat-log">
        <p className="m a">Hi. Tap an underlined word to change it. Chat arrives in a later version.</p>
      </div>
    </aside>
  );
}
