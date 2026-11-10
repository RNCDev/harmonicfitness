// What the page shows if something in it breaks while drawing: the reason in words and a way back, where React
// would otherwise leave a blank sky. Around the whole app (main.tsx) and around each signed-in page (App.tsx), so
// a broken page leaves the chat and a running workout on screen. The client's one class component: React catches
// a render's error only in one.
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "./Button";
import { Notice } from "./Notice";
import { Solo } from "./Solo";

type Props = {
  children: ReactNode;
  /** What broke, as the listener knows it ("The Logs page"); left out, the whole page. */
  what?: string;
};

export class Boundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // the browser's console is where a maintainer looks; the listener gets words
    console.error(error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    const reload = () => window.location.reload();
    if (!this.props.what) {
      return (
        <Solo>
          <h1>Something went wrong</h1>
          <Notice tone="error">The page hit a problem it couldn't draw. Reloading usually puts it right.</Notice>
          <Button variant="primary" onClick={reload}>Reload the page</Button>
        </Solo>
      );
    }
    return (
      <section className="page">
        <div className="failed">
          <Notice tone="error">{`${this.props.what} hit a problem it couldn't draw.`}</Notice>
          <Button onClick={reload}>Reload the page</Button>
        </div>
      </section>
    );
  }
}
