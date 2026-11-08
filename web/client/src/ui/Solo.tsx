// A page with the sky behind one short task: signing in, choosing a password, a server that can't be reached.
// `beside` (the sign-in page's demos) takes the wide column, saying what the app is, and the task sits next to it.
import type { ReactNode } from "react";
import { Mark } from "./Mark";
import { Sky } from "./Sky";

export function Solo({ version, children, beside }: { version?: string; children: ReactNode; beside?: ReactNode }) {
  return (
    <div className="app solo-app">
      <Sky />
      <div className="work">
        <header className="work-top"><Mark version={version} /></header>
        {beside ? (
          <main className="solo solo-pair">
            {beside}
            <div className="solo-task">{children}</div>
          </main>
        ) : (
          <main className="solo">
            <p className="label eyebrow">Workouts for your earbuds, written and voiced fresh each time you ask</p>
            {children}
          </main>
        )}
      </div>
    </div>
  );
}
