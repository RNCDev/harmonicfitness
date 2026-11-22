// What kind of site this is, for the pages whose words depend on it. `hosted`: the site's own key writes and
// speaks and a recording is paid for in minutes, so nothing is said of keys or dollars. `clerk`: sign-in goes
// through Clerk, so there is no password here. The app provides it once the server says who is signed in; a
// site run on its listeners' own keys is the default.
import { createContext, useContext } from "react";

export type Site = { hosted: boolean; clerk: boolean };

export const SiteContext = createContext<Site>({ hosted: false, clerk: false });

export const useSite = () => useContext(SiteContext);

/** "1 minute", "20 minutes". */
export const minutesSaid = (n: number) => `${n} ${n === 1 ? "minute" : "minutes"}`;
