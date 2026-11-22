// The account, at the foot of the Settings drawer: who is signed in and the version, then one row of worded
// actions (the password, another device, signing out, deleting it; what one opens comes below the row), then what
// another device means. Where sign-in goes through Clerk there is no password here: none to change, and deleting
// the account is proved with Clerk's own session instead (a fresh token, lib/useClerkSession.ts).
import { useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { api, type DeviceLink } from "../../lib/api";
import { clockAt } from "../../lib/format";
import { SAID } from "../../lib/messages";
import { useSite } from "../../lib/site";
import { Quiet, useAction } from "../../lib/useAction";
import { useFreshToken } from "../../lib/useClerkSession";
import { useResource } from "../../lib/useResource";
import { Button } from "../../ui/Button";
import { ClerkGate } from "../../ui/ClerkGate";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Field } from "../../ui/Field";
import { Loadable, Notice } from "../../ui/Notice";
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

/** Deleting an account that signs in through Clerk: Clerk says who is asking. Its provider is loaded only once
 * the question is open, since nothing else on the signed-in page needs it. */
function ClerkDeleteBox({ onDeleted }: { onDeleted: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="cx-box">
      {!open ? <Button variant="text" danger onClick={() => setOpen(true)}>Delete my account</Button>
        : <ProvedByClerk onDeleted={onDeleted} onKeep={() => setOpen(false)} />}
    </div>
  );
}

function ProvedByClerk({ onDeleted, onKeep }: { onDeleted: () => void; onKeep: () => void }) {
  const info = useResource(api.authInfo, SAID.unreachable);
  return (
    <Loadable value={info.data} error={info.error} onRetry={info.reload} what="the question">
      {(i) => i.clerk
        ? <ClerkGate publishableKey={i.clerk}><ClerkDelete onDeleted={onDeleted} onKeep={onKeep} /></ClerkGate>
        : <Notice tone="error">{SAID.deleteAccount}</Notice>}
    </Loadable>
  );
}

function ClerkDelete({ onDeleted, onKeep }: { onDeleted: () => void; onKeep: () => void }) {
  const fresh = useFreshToken();
  /** Clerk's session on this browser has ended, though this site's hasn't: signing in again brings it back. */
  const [stale, setStale] = useState(false);
  const remove = useAction(async () => {
    const token = await fresh.get();
    if (!token) { setStale(true); throw new Quiet(); }
    await api.deleteAccountAs(token);
    onDeleted();
  }, { fallback: SAID.deleteAccount, hold: true });
  return (
    <>
      <ConfirmInline question="Delete your account and everything in it? It can't be undone."
        confirm="Delete everything" keep="Keep my account" canConfirm={fresh.ready && !stale} busy={remove.busy}
        onConfirm={() => void remove.run()} onKeep={onKeep} />
      <Notice tone="error">{stale ? "To delete your account, sign out and sign in again first, then come back here."
        : remove.error}</Notice>
    </>
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

export function Account({ username, version, onSignOut, onDeleted, clerkLinked = false }: {
  username: string; version?: string; onSignOut: () => void; onDeleted: () => void;
  /** This account signs in through Clerk. */
  clerkLinked?: boolean;
}) {
  const { clerk } = useSite();
  return (
    <section className="cx-foot" aria-labelledby="cx-account-h">
      <h3 className="head cx-h" id="cx-account-h">Account</h3>
      <div className="cx-foot-who">
        <p className="cx-s">Signed in as <strong>{username}</strong></p>
        {version && <p className="cx-version">Version {version}</p>}
      </div>
      <div className="act-row cx-foot-acts">
        {!clerk && <PasswordBox username={username} />}
        <DeviceLinkBox />
        <Button variant="text" onClick={onSignOut}>Sign out</Button>
        {clerkLinked ? <ClerkDeleteBox onDeleted={onDeleted} /> : <DeleteBox onDeleted={onDeleted} />}
      </div>
      <p className="cx-s cx-foot-note">Sign in another device shows a code to scan with your phone: it signs you in
        there, {clerk ? "with nothing to type" : "no password needed"}.</p>
    </section>
  );
}
