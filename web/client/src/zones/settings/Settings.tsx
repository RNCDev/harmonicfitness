// The Settings drawer, in three parts: tabs at the top, one per section (the keys, what's used most; the listener's
// level; recording; the private podcast feed; the background behind the page, called the sky in the code, with its
// credit; their files); the chosen section alone; and the account at the foot (Account.tsx). While it's open it
// holds the keyboard: Tab stays inside, Escape closes it, and the page behind can't be reached. Each section is a
// file of its own beside this one.
import { useEffect, useRef, useState, type RefObject } from "react";
import type { KeyState } from "../../lib/api";
import { useFocusTrap } from "../../lib/useFocusTrap";
import { useKeyAsk } from "../../lib/keyAsk";
import type { SkyKind } from "../../ui/Sky";
import { Button } from "../../ui/Button";
import { Account } from "./Account";
import { FeedBox } from "./FeedBox";
import { FilesBox } from "./FilesBox";
import { KeysBox } from "./KeysBox";
import { LevelBox } from "./LevelBox";
import { RecordBox } from "./RecordBox";
import { SkyBox } from "./SkyBox";

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

export function Settings({ username, version, open, onClose, onSignOut, onDeleted = onSignOut, onKeys,
  sky = "flow", onSky, skyError, autoRecord = false, onAutoRecord, autoRecordError, returnFocus }: Props) {
  const drawer = useRef<HTMLElement>(null);
  useFocusTrap(drawer, open, { onEscape: onClose, returnFocus, inert: true });
  // the tabs: one per section, and only the chosen section shows (a button, not a link: the page's own address
  // already says which page is open)
  const sections = [
    { id: "cx-keys", name: "Keys" },
    { id: "cx-level", name: "Level" },
    ...(onAutoRecord ? [{ id: "cx-rec", name: "Recording" }] : []),
    { id: "cx-feed", name: "Podcast" },
    ...(onSky ? [{ id: "cx-sky", name: "Background" }] : []),
    { id: "cx-files", name: "Files" },
  ];
  const [shown, setShown] = useState("cx-keys");
  // a key's row asked for from elsewhere (the welcome card, a coach that needs a key) is in Keys
  const keyAsk = useKeyAsk();
  useEffect(() => { if (keyAsk) setShown("cx-keys"); }, [keyAsk]);
  return (
    <>
      <div className={`ctx-scrim${open ? " show" : ""}`} onClick={onClose} aria-hidden="true" data-scrim="" />
      <aside ref={drawer} className={`ctx${open ? " open" : ""}`} id="ctx" aria-label="Settings" role="dialog"
        aria-modal={open || undefined}>
        <div className="ctx-top">
          <h2 className="head">Settings</h2>
          <Button variant="bare" className="ctx-close" onClick={onClose}>Close</Button>
        </div>
        <nav className="cx-tabs" aria-label="Settings sections">
          {sections.map((s) => (
            <Button key={s.id} variant="bare" aria-current={shown === s.id || undefined} onClick={() => setShown(s.id)}>
              {s.name}
            </Button>
          ))}
        </nav>
        <div className="cx-main" data-shown={shown}>
          <KeysBox onKeys={onKeys} />
          <LevelBox />
          {onAutoRecord && <RecordBox on={autoRecord} onChange={onAutoRecord} error={autoRecordError} />}
          {shown === "cx-feed" && <FeedBox />}{/* loaded when opened: most visits to Settings never need it */}
          {onSky && <SkyBox sky={sky} onSky={onSky} error={skyError} />}
          <FilesBox />
        </div>
        <Account username={username} version={version} onSignOut={onSignOut} onDeleted={onDeleted} />
      </aside>
    </>
  );
}
