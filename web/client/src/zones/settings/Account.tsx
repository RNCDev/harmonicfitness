// The account, at the foot of the Settings drawer: who is signed in and the version, then one row of worded
// actions (the password, another device, signing out, deleting it; what one opens comes below the row), then what
// another device means.
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, type DeviceLink } from "../../lib/api";
import { clockAt } from "../../lib/format";
import { SAID } from "../../lib/messages";
import { useAction } from "../../lib/useAction";
import { Button } from "../../ui/Button";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Field } from "../../ui/Field";
import { Notice } from "../../ui/Notice";
import { PasswordForm } from "../../ui/PasswordForm";

/** A QR code must be black on white for a phone's camera, whatever the page's colours. */
const QR_COLOURS = { dark: "#000000", light: "#ffffff" };

function DeviceLinkBox() {
  const [link, setLink] = useState<DeviceLink | null>(null);
  const [drawError, setDrawError] = useState<string | null>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const make = useAction(async () => { setDrawError(null); setLink(await api.deviceLink()); }, { fallback: SAID.link });

  useEffect(() => {
    if (link && canvas.current) {
      QRCode.toCanvas(canvas.current, link.url, { width: 200, margin: 2, color: QR_COLOURS })
        .catch(() => setDrawError(SAID.qr));
    }
  }, [link]);

  const until = link ? clockAt(link.expires_at) : "";
  return (
    <div className="cx-box">
      <Button variant="text" busy={make.busy} busyLabel="Making a link…" onClick={() => void make.run()}>
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

function DeleteBox({ onDeleted }: { onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const remove = useAction(async () => { await api.deleteAccount(password); onDeleted(); },
    { fallback: SAID.deleteAccount, hold: true });

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
        <Button variant="text" onClick={() => { setOpen(true); setDone(false); }}>Change password</Button>
      )}
      <Notice tone="done" className="cx-s">{done && "Password changed."}</Notice>
    </div>
  );
}

export function Account({ username, version, onSignOut, onDeleted }: {
  username: string; version?: string; onSignOut: () => void; onDeleted: () => void;
}) {
  return (
    <section className="cx-foot" aria-labelledby="cx-account-h">
      <h3 className="head cx-h" id="cx-account-h">Account</h3>
      <div className="cx-foot-who">
        <p className="cx-s">Signed in as <strong>{username}</strong></p>
        {version && <p className="cx-version">Version {version}</p>}
      </div>
      <div className="act-row cx-foot-acts">
        <PasswordBox username={username} />
        <DeviceLinkBox />
        <Button variant="text" onClick={onSignOut}>Sign out</Button>
        <DeleteBox onDeleted={onDeleted} />
      </div>
      <p className="cx-s cx-foot-note">Sign in another device shows a code to scan with your phone: it signs you in
        there, no password needed.</p>
    </section>
  );
}
