import { useState, useEffect } from "react";
import { invoicesSeed, canAccessPage, getDefaultPage } from "./data";
import "./styles.css";
import PublicInvoice from "./pages/PublicInvoice";
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

export default function App() {
  const publicInvoiceMatch = window.location.pathname.match(/^\/invoice\/([^/]+)\/?$/);
  if (publicInvoiceMatch) {
    return <PublicInvoice token={publicInvoiceMatch[1]} />;
  }    
  const [page, setPage] = useState("dashboard");
  // ...rest of your existing code stays exactly the same below this
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
  const [invoices, setInvoices] = useState(invoicesSeed);
  const [detailInvNumber, setDetailInvNumber] = useState(null);
  const [smsInvoiceId, setSmsInvoiceId] = useState(null);
  const detailInvoice = invoices.find((inv) => inv.inv === detailInvNumber) || null;

  useEffect(() => {
    if (session && !canAccessPage(page, session.role)) {
      setPage(getDefaultPage(session.role));
    }
  }, [session]);

  function generateInvoicePdfs(percentagesByInv) {
    setInvoices((prev) => prev.map((inv) => {
      if (!(inv.inv in percentagesByInv)) return inv;
      const pct = parseFloat(percentagesByInv[inv.inv]);
      if (isNaN(pct)) return inv;
      const lots = inv.lots.map((l) => ({
        ...l,
        feePercentage: pct.toFixed(2),
        lotFee: (parseFloat(l.winningAmount) * pct / 100).toFixed(2),
      }));
      const totalAmount = lots.reduce((s, l) => s + parseFloat(l.lotFee), 0).toFixed(2);
      return {
        ...inv,
        lots,
        feePercentage: pct.toFixed(2),
        totalAmount,
        status: inv.status === "invoice_generated" ? "pending_payment" : inv.status,
      };
    }));
  }

  function handleLogout() {
    sessionStorage.removeItem("authToken");
    localStorage.removeItem("authToken");
    localStorage.removeItem("authUser");

    setSession(null);
    setPage("dashboard");
    setDetailInvNumber(null);
  }

  function handleLogin(role, username, token, remember) {
    sessionStorage.setItem("authToken", token);
    setSession({ role, username, token });
    setPage(getDefaultPage(role));
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
              token={session.token}
              onOpenDetail={setDetailInvNumber}
              onOpenSms={setSmsInvoiceId}
            />
          )}
          {page === "operations" && smsInvoiceId && (
            <SendSms invoiceId={smsInvoiceId} onBack={() => setSmsInvoiceId(null)} />
          )}
          {page === "dashboard" && <Dashboard role={session.role} token={session.token} />}
          {page === "queues" && <Queues role={session.role} token={session.token} />}
          {page === "reports" && <Reports role={session.role} token={session.token} />}
          {page === "callcenter" && <CallCenter role={session.role} token={session.token} />} 
          {page === "audit" && <AuditTrail role={session.role} token={session.token} />}
          {page === "employees" && <Employees role={session.role} token={session.token} />}
        </div>  
      </div>
      <InvoiceDetailModal
          invoice={detailInvoice}
          role={session.role}
          token={session.token}
          onClose={() => setDetailInvNumber(null)}
          onGeneratePdf={generateInvoicePdfs}
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
