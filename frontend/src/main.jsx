import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// fonty serwowane lokalnie (on-premise, bez CDN): groteska + krój monospace do danych
import "@fontsource-variable/inter-tight";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import App from "./App.jsx";
import ErrorBoundary from "./components/ErrorBoundary.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);
