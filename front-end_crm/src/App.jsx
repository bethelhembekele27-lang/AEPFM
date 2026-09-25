import { useState, useEffect } from "react";
import { canAccessPage, getDefaultPage } from "./data";
import "./styles.css";
import Login from "./components/Login";
import Header from "./components/Header";
import InvoiceDetailModal from "./components/InvoiceDetailModal";
import AccountSettingsModal from "./components/AccountSettingsModal";

import Dashboard from "./pages/Dashboard";
import ImportBatches from "./pages/ImportBatches";
import Operations from "./pages/Operations";
import Queues from "./pages/Queues";
import Reports from "./pages/Reports";
import AuditTrail from "./pages/AuditTrail";
import CallCenter from "./pages/CallCenter";
import Employees from "./pages/Employees";
import SendSms from "./pages/SendSms";
import ManagerReview from "./pages/ManagerReview";

export default function App() {
  const [page, setPage] = useState("dashboard");
  const [session, setSession] = useState(() => {
    const sessionToken = sessionStorage.getItem("authToken");
    const localToken = localStorage.getItem("authToken");
    const localUser = localStorage.getItem("authUser");

    // sessionStorage always wins — it reflects the most recent login in
    // this tab. localStorage is only a fallback for "remember me" across
    // fresh sessions/reloads when sessionStorage is empty.
    if (sessionToken && localToken === sessionToken && localUser) {
      try {
        const parsed = JSON.parse(localUser);
        return { ...parsed, token: sessionToken };
      } catch {
        return null;
      }
    }

    if (localToken && localUser) {
      try {
        const parsed = JSON.parse(localUser);
        return { ...parsed, token: localToken };
      } catch {
        return null;
      }
    }

    return null;
  });
  const [theme, setTheme] = useState("light");
  const [showAccountSettings, setShowAccountSettings] = useState(false);
  const [detailInvoiceId, setDetailInvoiceId] = useState(null);
  const [smsInvoiceId, setSmsInvoiceId] = useState(null);

  useEffect(() => {
    if (session && !canAccessPage(page, session.privileges)) {
      setPage(getDefaultPage(session.privileges));
    }
  }, [session]);

  function handleLogout() {
    sessionStorage.removeItem("authToken");
    localStorage.removeItem("authToken");
    localStorage.removeItem("authUser");

    setSession(null);
    setPage("dashboard");
    setDetailInvoiceId(null);
  }

  function handleLogin(role, username, token, remember, privileges) {
    sessionStorage.setItem("authToken", token);
    setSession({ role, username, token, privileges: privileges || [] });
    setPage(getDefaultPage(privileges || []));
  }
  function handleSaveProfile(newUsername) {
    setSession((s) => ({ ...s, username: newUsername }));
  }

  if (!session) {
    return <Login onLogin={handleLogin} />;
  }

  return (
    <div className="app" data-theme={theme}>
      <Header
        page={page}
        setPage={(p) => { setSmsInvoiceId(null); setPage(p); }}
        role={session.role}
        privileges={session.privileges}
        username={session.username}
        theme={theme}
        setTheme={setTheme}
        onLogout={handleLogout}
        onOpenAccountSettings={() => setShowAccountSettings(true)}
      />
      <div className="main">
        <div className="page active">
          
          {page === "import" && (
            <ImportBatches
              role={session.role}
              token={session.token}
            />
            )}
          {page === "operations" && !smsInvoiceId && (
            <Operations
              role={session.role}
              privileges={session.privileges}
              token={session.token}
              onOpenDetail={setDetailInvoiceId}
              onOpenSms={setSmsInvoiceId}
            />
          )}
          {page === "operations" && smsInvoiceId && (
            <SendSms invoiceId={smsInvoiceId} onBack={() => setSmsInvoiceId(null)} />
          )}
          {page === "dashboard" && <Dashboard role={session.role} token={session.token} />}
          {page === "queues" && <Queues role={session.role} privileges={session.privileges} token={session.token} />}
          {page === "reports" && <Reports role={session.role} privileges={session.privileges} token={session.token} />}
          {page === "callcenter" && <CallCenter role={session.role} token={session.token} />}
          {page === "receipts" && <ManagerReview role={session.role} privileges={session.privileges} token={session.token} />}
          {page === "audit" && <AuditTrail role={session.role} token={session.token} />}
          {page === "employees" && <Employees role={session.role} token={session.token} />}
        </div>  
      </div>
      <InvoiceDetailModal
          invoiceId={detailInvoiceId}
          role={session.role}
          token={session.token}
          privileges={session.privileges}
          onClose={() => setDetailInvoiceId(null)}
        />
      {showAccountSettings && (
        <AccountSettingsModal
          username={session.username}
          token={session.token}
          onSave={handleSaveProfile}
          onClose={() => setShowAccountSettings(false)}
        />
      )}
    </div>
  );
}
