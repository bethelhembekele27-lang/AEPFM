import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import PublicInvoice from "./pages/PublicInvoice";

function Root() {
  // Minimal path-based routing for the one unauthenticated entry point —
  // a bidder clicking an SMS link lands on /invoice/<token> with no prior
  // app state, so this has to be checked before Login/session logic runs
  // at all, not routed through the internal page-state system App.jsx
  // uses everywhere else.
  const match = window.location.pathname.match(/^\/invoice\/([^/]+)\/?$/);
  if (match) {
    return <PublicInvoice token={match[1]} />;
  }
  return <App />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);