// The Settings drawer, in two columns on a wide screen: the coaches and the keys (what's used most); then the
// background behind the page (called the sky in the code), the listener's files (download, bring in a folder) and
// last the account (who is signed in, the password, another device, signing out, deleting it). On a phone, one
// column in the same order.
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, ApiError, NotSignedIn, type DeviceLink, type KeyState, type StartCoach } from "../api";
import { PasswordForm } from "../SignIn";
import { SKIES, SkyPreview, type SkyKind } from "../Sky";
import { KeysBox } from "./KeysBox";

function until(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function DeviceLinkBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [link, setLink] = useState<DeviceLink | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (link && canvas.current) {
      QRCode.toCanvas(canvas.current, link.url, {
        width: 200, margin: 2, color: { dark: "#000000", light: "#ffffff" },
      }).catch(() => setError("Couldn't draw the code; the link below still works."));
    }
  }, [link]);

  async function make() {
    setBusy(true);
    setError(null);
    try {
      setLink(await api.deviceLink());
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError("Couldn't make a link. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      <button type="button" className="act" onClick={make} disabled={busy}>
        {link ? "Make a new link" : "Sign in another device"}
      </button>
      {error && <p className="cx-s err" role="alert">{error}</p>}
      {link && (
        <div className="device">
          <p className="cx-s">Scan this code with your phone, or open the link on the other device. It works once, for 10 minutes{until(link.expires_at) && ` (until ${until(link.expires_at)})`}.</p>
          <canvas ref={canvas} className="qr" aria-label="QR code of the sign-in link" role="img" />
          <p className="link"><code>{link.url}</code></p>
        </div>
      )}
    </div>
  );
}

function ImportBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function take(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setNote(null);
    setError(null);
    try {
      const r = await api.importFolder(file);
      setNote(`Brought in ${r.imported} files${r.left_out ? ` (left out ${r.left_out}: keys, audio, caches, backups)` : ""}.`);
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError(e instanceof ApiError ? e.message : "Couldn't send it. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      <label className="act">
        {busy ? "Bringing it in…" : "Bring in a folder"}
        <input type="file" accept=".zip,application/zip" disabled={busy} className="sr"
          onChange={(e) => { void take(e.target.files?.[0]); e.target.value = ""; }} />
      </label>
      <p className="cx-s">Already use HarmonicFitness on your computer? Choose a ZIP of its <code>me</code> folder. Its files replace the starter ones here; key files are left out.</p>
      {note && <p className="cx-s" role="status">{note}</p>}
      {error && <p className="cx-s err" role="alert">{error}</p>}
    </div>
  );
}

function ExportBox() {
  return (
    <div className="cx-box">
      <a className="act" href="/api/export" download>Download your files</a>
      <p className="cx-s">A ZIP of your profile, log and workouts, ready to use as the <code>me</code> folder on your computer. Keys are never in it.</p>
    </div>
  );
}

function DeleteBox({ onSignedOut }: { onSignedOut: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function remove() {
    setBusy(true);
    setError(null);
    try {
      await api.deleteAccount(password);
      onSignedOut();
    } catch (e) {
      if (e instanceof NotSignedIn) return onSignedOut();
      setError(e instanceof ApiError ? e.message : "Couldn't delete it. Try again.");
      setBusy(false);
    }
  }

  return (
    <div className="cx-box">
      {!open ? (
        <button type="button" className="act danger" onClick={() => setOpen(true)}>Delete my account</button>
      ) : (
        <form className="auth" onSubmit={(e) => { e.preventDefault(); void remove(); }}>
          <p className="cx-s err">This deletes your account and everything in it: your files, keys, chats and audio. It can't be undone.</p>
          <label>
            Your password
            <input type="password" autoComplete="current-password" value={password}
              onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error && <p className="err" role="alert">{error}</p>}
          <div className="keys-actions">
            <button type="submit" className="go danger" disabled={busy || !password}>
              {busy ? "Deleting…" : "Delete everything"}
            </button>
            <button type="button" className="quiet" onClick={() => { setOpen(false); setPassword(""); setError(null); }}>Cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}

function PasswordBox({ username, onSignedOut }: { username: string; onSignedOut: () => void }) {
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState(false);
  return (
    <div className="cx-box">
      <p className="cx-s">Signed in as <strong>{username}</strong></p>
      {open ? (
        <PasswordForm username={username} needsCurrent onSignedOut={onSignedOut}
          onDone={() => { setOpen(false); setDone(true); }} />
      ) : (
        <button type="button" className="act" onClick={() => { setOpen(true); setDone(false); }}>
          Change password
        </button>
      )}
      {done && <p className="cx-s" role="status">Password changed.</p>}
    </div>
  );
}

type Props = {
  username: string;
  open: boolean;
  onClose: () => void;
  onSignedOut: () => void;
  onSignOut: () => void;
  onKeys?: (keys: KeyState[]) => void;
  /** A key row to open in edit mode (the welcome card's "Add your key"). */
  openRow?: { service: string; n: number; choose?: boolean } | null;
  /** The coaches that can speak here, and those waiting on a key. */
  coaches?: StartCoach[];
  /** Makes a coach that can speak the current one (and the first screen's). */
  onCoach?: (slug: string) => void;
  /** The background behind the page (the sky), and the choice of it. */
  sky?: SkyKind;
  onSky?: (sky: SkyKind) => void;
};

function an(word: string): string {
  return /^[aeiou]/i.test(word) ? "an" : "a";
}

function CoachesBox({ coaches, onCoach }: { coaches: StartCoach[]; onCoach?: (slug: string) => void }) {
  if (coaches.length === 0) return null;
  return (
    <section className="cx-box" aria-labelledby="cx-coaches-h">
      <h3 className="cx-h" id="cx-coaches-h">Your coaches</h3>
      <ul className="coach-list">
        {coaches.map((c, i) => {
          const about = c.ready ? `${c.own ? "Yours, " : ""}${c.service_name}` : `Needs ${an(c.service_name)} ${c.service_name} key`;
          const row = <>
            <span className={`lane-num${c.current ? " on" : ""}`} aria-hidden="true">{i + 1}</span>
            <b>{c.first}</b>
            <small>{c.current ? `Coaching you · ${about}` : about}</small>
          </>;
          return (
            <li key={c.slug} className={`${c.ready ? "" : "off"}${c.current ? " cur" : ""}`}>
              {c.ready && onCoach ? (
                <button type="button" className="coach-pick" aria-pressed={c.current}
                  aria-label={`Coach ${c.first}, ${about}`} onClick={() => onCoach(c.slug)}>{row}</button>
              ) : row}
            </li>
          );
        })}
      </ul>
      <p className="cx-s">{onCoach && coaches.some((c) => c.ready) ? "Tap one to switch. To make your own, ask in the chat."
        : "To switch coach, or make one of your own, ask in the chat."}</p>
    </section>
  );
}

function SkyBox({ sky, onSky }: { sky: SkyKind; onSky: (sky: SkyKind) => void }) {
  return (
    <section className="cx-box" aria-labelledby="cx-sky-h">
      <h3 className="cx-h" id="cx-sky-h">Background</h3>
      <div className="sky-opts" role="group" aria-labelledby="cx-sky-h">
        {SKIES.map((s) => (
          <button key={s.kind} type="button" className={`sky-opt${sky === s.kind ? " on" : ""}`}
            aria-pressed={sky === s.kind} title={s.about} onClick={() => onSky(s.kind)}>
            <SkyPreview kind={s.kind} />
            <span className="sky-opt-name">{s.name}</span>
            <span className="sky-opt-note">{s.about}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

export function ContextColumn({ username, open, onClose, onSignedOut, onSignOut, onKeys, openRow, coaches = [],
  onCoach, sky = "flow", onSky }: Props) {
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Settings">
        <div className="ctx-top">
          <h2>Settings</h2>
          <button type="button" className="ctx-close" onClick={onClose}>Close</button>
        </div>
        {/* two columns on a wide screen, one below the other on a phone: what's used most comes first */}
        <div className="cx-list">
          <div className="cx-col">
            <CoachesBox coaches={coaches} onCoach={onCoach} />
            <KeysBox onSignedOut={onSignedOut} onKeys={onKeys} openRow={openRow} />
          </div>
          <div className="cx-col">
            {onSky && <SkyBox sky={sky} onSky={onSky} />}
            <section className="cx-account" aria-labelledby="cx-files-h">
              <h3 className="cx-h" id="cx-files-h">Your files</h3>
              <ExportBox />
              <ImportBox onSignedOut={onSignedOut} />
            </section>
            <section className="cx-account" aria-labelledby="cx-account-h">
              <h3 className="cx-h" id="cx-account-h">Account</h3>
              {/* who is signed in; a row to change the account, a row to leave it; what one opens comes below its row */}
              <div className="act-row">
                <PasswordBox username={username} onSignedOut={onSignedOut} />
                <DeviceLinkBox onSignedOut={onSignedOut} />
              </div>
              <div className="act-row">
                <button type="button" className="act" onClick={onSignOut}>Sign out</button>
                <DeleteBox onSignedOut={onSignedOut} />
              </div>
            </section>
          </div>
        </div>
      </aside>
    </>
  );
}
