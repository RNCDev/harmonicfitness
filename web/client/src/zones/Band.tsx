// The band: the wordmark, the sentence and the button that starts the conversation.
import { APP_NAME } from "../api";
import { Sentence } from "../sentence/Sentence";
import type { SentenceModel } from "../sentence/model";

type Props = {
  model: SentenceModel | null;
  onChange: (key: string, value: string | number) => void;
  onGo: () => void;
  busy: boolean;
  onFiles: () => void;
  filesOpen: boolean;
  version?: string;
};

export function Band({ model, onChange, onGo, busy, onFiles, filesOpen, version }: Props) {
  return (
    <header className="band">
      <div className="band-left">
        <div className="mark">{APP_NAME}{version && <span className="ver">{version}</span>}</div>
        <button type="button" className="ctx-toggle" aria-expanded={filesOpen} aria-controls="ctx"
          onClick={onFiles}>
          Your files
        </button>
      </div>
      <div className="band-main">
        <div className="band-sent">
          {model ? <Sentence model={model} onChange={onChange} disabled={busy} /> : (
            <p className="sentence loading">Loading…</p>
          )}
        </div>
        <div className="band-go">
          <button type="button" className="go" onClick={onGo} disabled={!model || busy}>
            {busy ? "Working…" : "Start"}
          </button>
        </div>
      </div>
    </header>
  );
}
