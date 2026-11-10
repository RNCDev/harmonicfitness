// The private podcast feed: a link a podcast app follows, so each new workout lands on the phone by itself. Off
// until turned on; a new link stops the old one, as turning it off does.
import { useRef, useState } from "react";
import { api } from "../../lib/api";
import { SAID } from "../../lib/messages";
import { useAction } from "../../lib/useAction";
import { useResource } from "../../lib/useResource";
import { Button } from "../../ui/Button";
import { ConfirmInline } from "../../ui/ConfirmInline";
import { Loadable, Notice } from "../../ui/Notice";
import { Section } from "../../ui/Section";

export function FeedBox() {
  const res = useResource(api.feed, SAID.feed);
  const url = res.data?.url ?? null;
  /** null until Copy is pressed; then whether the clipboard took it. */
  const [copied, setCopied] = useState<boolean | null>(null);
  const shownLink = useRef<HTMLElement>(null);
  const [confirm, setConfirm] = useState<"new" | "off" | null>(null);
  const make = useAction(async () => {
    const r = await api.makeFeed();
    res.set(() => r);
    setConfirm(null);
    setCopied(null);
  }, { fallback: SAID.link });
  const stop = useAction(async () => {
    await api.stopFeed();
    res.set(() => ({ url: null }));
    setConfirm(null);
  }, { fallback: SAID.feedOff });

  async function copy(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // no clipboard here: the link is selected, to copy by hand
      setCopied(false);
      const el = shownLink.current;
      const sel = window.getSelection?.();
      if (el && sel) { const r = document.createRange(); r.selectNodeContents(el); sel.removeAllRanges(); sel.addRange(r); }
    }
  }

  return (
    <Section id="cx-feed" title="Podcast">
      <p className="cx-s">Follow your workouts in a podcast app, and each new one arrives on your phone by itself, ready to play
        offline. The feed holds your three newest workouts; your app keeps the ones it has downloaded.</p>
      <Loadable value={res.data} error={res.error} onRetry={res.reload} what="your podcast link" room={90}>
        {() => url ? (
          <>
            <p className="link"><code ref={shownLink}>{url}</code></p>
            <div className="act-row">
              <Button variant="secondary" onClick={() => void copy(url)}>{copied ? "Copied" : "Copy the link"}</Button>
              <Button variant="text" onClick={() => setConfirm("new")}>Make a new link</Button>
              <Button variant="text" danger onClick={() => setConfirm("off")}>Turn it off</Button>
            </div>
            {confirm && (<>
              <ConfirmInline question={confirm === "new" ? "Make a new link?" : "Turn the podcast off?"}
                confirm={confirm === "new" ? "Make a new link" : "Turn it off"} keep="Keep this link"
                busy={make.busy || stop.busy}
                onConfirm={() => void (confirm === "new" ? make.run() : stop.run())}
                onKeep={() => { setConfirm(null); make.clear(); stop.clear(); }} />
              <p className="cx-s">The link you have now stops working, in every app that follows it.</p>
            </>)}
            <p className="cx-s">In your podcast app, choose to follow a show by its link (in Apple Podcasts: Library, then
              Follow a Show by URL) and paste it. Keep it to yourself: anyone with the link can hear your workouts.</p>
          </>
        ) : (
          <div className="act-row">
            <Button variant="secondary" busy={make.busy} busyLabel="Making a link…" onClick={() => void make.run()}>
              Make my podcast link
            </Button>
          </div>
        )}
      </Loadable>
      <Notice className="cx-s">{copied === false && "This browser didn't let the page copy. The link is selected: copy it from there."}</Notice>
      <Notice tone="error">{make.error ?? stop.error}</Notice>
    </Section>
  );
}
