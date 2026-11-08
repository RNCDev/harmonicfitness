// The Settings drawer. On a wide screen, two rows of two: the keys (what's used most) beside the listener's own
// choices (their level, recording, the background behind the page, called the sky in the code, with its credit); then
// their files (download, bring in a folder) beside the account (who is signed in, the password, another device, signing
// out, deleting it). On a phone, one column in the same order. While it's open it holds the keyboard: Tab stays
// inside, Escape closes it, and the page behind can't be reached.
import { useEffect, useRef, useState, type RefObject } from "react";
import QRCode from "qrcode";
import { api, ApiError, NotSignedIn, type DeviceLink, type KeyState, type Level, type LevelState } from "../lib/api";
import { clockAt } from "../lib/format";
import { optimistic, useAction } from "../lib/useAction";
import { useResource } from "../lib/useResource";
import { useFocusTrap } from "../lib/useFocusTrap";
import { SKIES, SkyPreview, type SkyKind } from "../ui/Sky";
import { Button, ChoiceRow } from "../ui/Button";
import { ConfirmInline } from "../ui/ConfirmInline";
import { Field } from "../ui/Field";
import { Loadable, Notice } from "../ui/Notice";
import { PasswordForm } from "../ui/PasswordForm";
import { KeysBox } from "./KeysBox";

/** A QR code must be black on white for a phone's camera, whatever the page's colours. */
const QR_COLOURS = { dark: "#000000", light: "#ffffff" };

function DeviceLinkBox() {
  const [link, setLink] = useState<DeviceLink | null>(null);
  const [drawError, setDrawError] = useState<string | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const make = useAction(async () => { setDrawError(null); setLink(await api.deviceLink()); },
    { fallback: "Couldn't make a link. Try again." });

  useEffect(() => {
    if (link && canvas.current) {
      QRCode.toCanvas(canvas.current, link.url, { width: 200, margin: 2, color: QR_COLOURS })
        .catch(() => setDrawError("Couldn't draw the code; the link below still works."));
    }
  }, [link]);

  const until = link ? clockAt(link.expires_at) : "";
  return (
    <div className="cx-box">
      <Button busy={make.busy} busyLabel="Making a link…" onClick={() => void make.run()}>
        {link ? "Make a new link" : "Sign in another device"}
      </Button>
      <Notice tone="error">{make.error ?? drawError}</Notice>
      {link && (
        <div className="device">
          <p className="cx-s">Scan this code with your phone, or open the link on the other device. It works once, for 10 minutes{until && ` (until ${until})`}.</p>
          <canvas ref={canvas} className="qr" aria-label="QR code of the sign-in link" role="img" />
          <p className="link"><code>{link.url}</code></p>
        </div>
      )}
    </div>
  );
}

function ImportBox() {
  const [note, setNote] = useState<string | null>(null);
  const take = useAction(async (file: File) => {
    setNote(null);
    const r = await api.importFolder(file);
    setNote(`Brought in ${r.imported} files${r.left_out ? ` (left out ${r.left_out}: keys, audio, caches, backups)` : ""}.`);
  }, { fallback: "Couldn't send it. Try again." });

  return (
    <div className="cx-box">
      <label className="act outlined" aria-busy={take.busy || undefined}>
        {take.busy ? "Bringing it in…" : "Bring in a folder"}
        <input type="file" accept=".zip,application/zip" disabled={take.busy} className="sr"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void take.run(f); e.target.value = ""; }} />
      </label>
      <Notice tone="done" className="cx-s">{note}</Notice>
      <Notice tone="error">{take.error}</Notice>
    </div>
  );
}

function ExportBox() {
  return <a className="act outlined" href="/api/export" download>Download your files</a>;
}

function DeleteBox({ onDeleted }: { onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const remove = useAction(async () => { await api.deleteAccount(password); onDeleted(); },
    { fallback: "Couldn't delete it. Try again.", hold: true });

  return (
    <div className="cx-box">
      {!open ? (
        <Button variant="text" danger onClick={() => setOpen(true)}>Delete my account</Button>
      ) : (
        <ConfirmInline question="Delete your account and everything in it?"
          detail="Your files, keys, chats and audio. It can't be undone." confirm="Delete everything" keep="Keep my account"
          canConfirm={!!password} busy={remove.busy} onConfirm={() => void remove.run()}
          onKeep={() => { setOpen(false); setPassword(""); remove.clear(); }}
          field={<Field id="delete-password" label="Your password" error={remove.error}>
            <input className="input" type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </Field>} />
      )}
    </div>
  );
}

function PasswordBox({ username }: { username: string }) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  return (
    <div className="cx-box">
      {open ? (
        <PasswordForm username={username} needsCurrent onDone={() => { setOpen(false); setDone(true); }} />
      ) : (
        <Button onClick={() => { setOpen(true); setDone(false); }}>Change password</Button>
      )}
      <Notice tone="done" className="cx-s">{done && "Password changed."}</Notice>
    </div>
  );
}

type Props = {
  username: string;
  /** The app's version (and build), shown at the foot of Settings. */
  version?: string;
  open: boolean;
  onClose: () => void;
  /** Sign out, at the listener's ask. */
  onSignOut: () => void;
  /** The account is gone: back to the sign-in page. */
  onDeleted?: () => void;
  onKeys?: (keys: KeyState[]) => void;
  /** The background behind the page (the sky), the choice of it, and why the last choice didn't hold. */
  sky?: SkyKind;
  onSky?: (sky: SkyKind) => void;
  skyError?: string | null;
  /** Record without asking: a checked script records at once, with no Record button. */
  autoRecord?: boolean;
  onAutoRecord?: (on: boolean) => void;
  autoRecordError?: string | null;
  /** Where focus goes when the drawer closes (the Settings button). */
  returnFocus?: RefObject<HTMLElement>;
};

function RecordBox({ on, onChange, error }: { on: boolean; onChange: (on: boolean) => void; error?: string | null }) {
  return (
    <section className="cx-box" aria-labelledby="cx-rec-h">
      <h3 className="label cx-h" id="cx-rec-h">Recording</h3>
      <label className="switch">
        <input type="checkbox" checked={on} onChange={(e) => onChange(e.target.checked)} />
        <span className="switch-name">Record without asking</span>
      </label>
      <p className="cx-s switch-note">
        {on
          ? "A checked script records without showing you the price first (usually less than 1 USD)."
          : "Shows you the price first (usually less than 1 USD) and waits for you to press Record."}
      </p>
      <Notice tone="error">{error}</Notice>
    </section>
  );
}

/** The listener's level, picked by the sentence that fits them: it sets the movements, the doses and how much the
 *  coach explains. Novice until one is chosen, as the planning assumes. Chosen at once, then saved; put back if refused. */
function LevelBox() {
  const res = useResource(api.level, "Your level couldn't be loaded.");
  const state = res.data;
  const setState = (s: LevelState | null) => res.set(() => s);
  const [error, setError] = useState<string | null>(null);

  async function choose(level: Level) {
    if (!state || level === state.level) return;
    setError(await optimistic(state, { ...state, level, set: true }, setState, async () => {
      try {
        await api.setLevel(level);
      } catch (e) {
        // a clash says what happened in the server's words; anything else in ours
        throw e instanceof NotSignedIn || (e instanceof ApiError && e.status === 409) ? e : new Error("not saved");
      }
    }, "Your level couldn't be saved. Try again."));
  }

  return (
    <section className="cx-box" aria-labelledby="cx-level-h">
      <h3 className="label cx-h" id="cx-level-h">Your level</h3>
      <Loadable value={state} error={res.error} onRetry={res.reload} what="your level" room={150}>
        {(s) => (
          <>
            <div className="level-opts" role="radiogroup" aria-labelledby="cx-level-h">
              {s.choices.map((c) => (
                <ChoiceRow key={c.level} checked={s.level === c.level} onClick={() => void choose(c.level)}>
                  {c.said}
                </ChoiceRow>
              ))}
            </div>
            <p className="cx-s">
              {!s.set
                ? "Not chosen yet, so workouts are planned for someone new. Pick the one that fits."
                : "Setting your level adjusts your trainer's guidance."}
            </p>
          </>
        )}
      </Loadable>
      <Notice tone="error">{error}</Notice>
    </section>
  );
}

function SkyBox({ sky, onSky, error }: { sky: SkyKind; onSky: (sky: SkyKind) => void; error?: string | null }) {
  return (
    <section className="cx-box" aria-labelledby="cx-sky-h">
      <h3 className="label cx-h" id="cx-sky-h">Background</h3>
      <div className="sky-opts" role="group" aria-labelledby="cx-sky-h">
        {SKIES.map((s) => (
          <Button key={s.kind} variant="tile" className="sky-opt" pressed={sky === s.kind} title={s.about}
            onClick={() => onSky(s.kind)}>
            <SkyPreview kind={s.kind} />
            <span className="sky-opt-name">{s.name}</span>
          </Button>
        ))}
      </div>
      <Notice tone="error">{error}</Notice>
      <p className="cx-s sky-credit">
        Patterns after <a href="https://bookofshapes.com" target="_blank" rel="noopener noreferrer">Book of Shapes</a> by
        Nikolaj Sokolowski.
      </p>
    </section>
  );
}

export function Settings({ username, version, open, onClose, onSignOut, onDeleted = onSignOut, onKeys,
  sky = "flow", onSky, skyError, autoRecord = false, onAutoRecord, autoRecordError, returnFocus }: Props) {
  const drawer = useRef<HTMLElement>(null);
  useFocusTrap(drawer, open, { onEscape: onClose, returnFocus, inert: true });
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" data-scrim="" />
      <aside ref={drawer} className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Settings" role="dialog"
        aria-modal={open || undefined}>
        <div className="ctx-top">
          <h2 className="head">Settings</h2>
          <Button variant="bare" className="ctx-close" onClick={onClose}>Close</Button>
        </div>
        {/* a wide screen: the keys beside your choices, then your files beside the account; a phone: one column */}
        <div className="cx-list">
          <div className="cx-cell cx-keys">
            <KeysBox onKeys={onKeys} />
          </div>
          <div className="cx-cell cx-prefs">
            <LevelBox />
            {onAutoRecord && <RecordBox on={autoRecord} onChange={onAutoRecord} error={autoRecordError} />}
            {onSky && <SkyBox sky={sky} onSky={onSky} error={skyError} />}
          </div>
          <section className="cx-cell cx-files" aria-labelledby="cx-files-h">
            <h3 className="label cx-h" id="cx-files-h">Your files</h3>
            <div className="act-row">
              <ExportBox />
              <ImportBox />
            </div>
            <p className="cx-s">Your profile, log and workouts as a ZIP, or a <code>me</code> folder from
              HarmonicFitness on your computer. Keys are never included.</p>
          </section>
          <section className="cx-cell cx-account" aria-labelledby="cx-account-h">
            <h3 className="label cx-h" id="cx-account-h">Account</h3>
            <p className="cx-s">Signed in as <strong>{username}</strong></p>
            {/* what a button opens (the password form, the sign-in code) comes below its row */}
            <div className="act-row">
              <PasswordBox username={username} />
              <DeviceLinkBox />
            </div>
            <div className="cx-foot">
              <Button variant="text" onClick={onSignOut}>Sign out</Button>
              <DeleteBox onDeleted={onDeleted} />
              {version && <p className="cx-version">Version {version}</p>}
            </div>
          </section>
        </div>
      </aside>
    </>
  );
}

