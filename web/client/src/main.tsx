import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/big-shoulders-display";
import "@fontsource/ibm-plex-sans-condensed/400.css";
import "@fontsource/ibm-plex-sans-condensed/500.css";
import "@fontsource/ibm-plex-sans-condensed/600.css";
import "./theme.css";
import { App } from "./App";
import { Boundary } from "./ui/Boundary";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Boundary>
      <App />
    </Boundary>
  </StrictMode>,
);
