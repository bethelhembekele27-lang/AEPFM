import { useState, useEffect } from "react";
import { periodLabels, statusLabels, money } from "../data";
import PeriodDropdown from "../components/PeriodDropdown";
import { apiCall } from "../api";

function RevenueBarList({ title, items, nameKey }) {
  const max = items.length ? Math.max(...items.map((i) => parseFloat(i.total))) : 0;
  return (
    <div className="card">
      <h3 style={{ margin: "0 0 4px" }}>{title}</h3>
      {items.length === 0 ? (
        <div className="locked-note" style={{ marginTop: 10 }}>No paid invoices yet.</div>
      ) : (
        items.map((item, i) => {
          const total = parseFloat(item.total);
          const pct = max ? (total / max) * 100 : 0;
          return (
            <div className="bar-row" key={i}>
              <div className="name" style={{ width: 140 }}>{item[nameKey]}</div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
              <div className="val">{money(total.toFixed(2))}</div>
            </div>
          );
        })
      )}
    </div>
  );
}

export default function Dashboard({ role, token }) {
  const [receivedPeriod, setReceivedPeriod] = useState("today");
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const canView = ["administrator", "auction_manager", "finance_manager", "viewer"].includes(role);

  useEffect(() => {
    if (canView) fetchDashboardData();
    else setLoading(false);
  }, [token]);

  async function fetchDashboardData() {
    try {
      setLoading(true);
      const response = await apiCall('/api/invoices/summary/', {
        method: 'GET',
        headers: token ? { Authorization: `Token ${token}` } : {},
      });

      if (!response.ok) {
        setError('Failed to load dashboard');
        return;
      }

      const data = await response.json();
      setStats(data);
      setError("");
    } catch (err) {
      setError('Network error loading dashboard');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  if (!canView) {
    return (
      <div className="card">
        <h3 style={{ margin: "0 0 6px" }}>Financial dashboard</h3>
        <div className="locked-note">You don't have permission to view the financial dashboard.</div>
      </div>
    );
  }

  if (loading) return <div style={{ padding: 20 }}>Loading dashboard...</div>;
  if (error) return <div style={{ padding: 20, color: 'red' }}>{error}</div>;
  if (!stats) return null;

  const totalCollected = parseFloat(stats.totalCollected || 0);
  const outstanding = parseFloat(stats.totalOutstanding || 0);
  const totalInvoices = stats.totalInvoices || 0;
  const collectionPct = stats.collectionPercentage || "0.00";
  const paidAuctionCount = stats.paidAuctionCount || 0;
  const outstandingCount = stats.outstandingCount || 0;

  const receivedValues = {
    today: stats.paymentsReceivedToday,
    week: stats.paymentsReceivedThisWeek,
    month: stats.paymentsReceivedThisMonth,
    year: stats.paymentsReceivedThisYear,
  };
  const receivedThisPeriod = parseFloat(receivedValues[receivedPeriod] || 0);

  const statusCounts = {
    invoice_generated: stats.invoiceGeneratedCount || 0,
    pending_payment: stats.pendingPaymentCount || 0,
    payment_submitted: stats.paymentSubmittedCount || 0,
    under_verification: stats.underVerificationCount || 0,
    paid: stats.paidCount || 0,
    overdue: stats.overdueCount || 0,
    cancelled: stats.cancelledCount || 0,
    waived: stats.waivedCount || 0,
  };

  return (
    <div>
      <div className="grid grid-4" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="stat-label">Total fees collected</div>
          <div className="stat-value up">{money(totalCollected.toFixed(2))}</div>
          <div className="stat-foot">Across {paidAuctionCount} active auction{paidAuctionCount === 1 ? "" : "s"}</div>
        </div>
        <div className="card">
          <div className="stat-label">Outstanding fees</div>
          <div className="stat-value warn">{money(outstanding.toFixed(2))}</div>
          <div className="stat-foot">{outstandingCount} invoices unpaid</div>
        </div>
        <div className="card">
          <div className="stat-label-row">
            <div className="stat-label">Received — {periodLabels[receivedPeriod].toLowerCase()}</div>
            <PeriodDropdown value={receivedPeriod} onChange={setReceivedPeriod} />
          </div>
          <div className="stat-value">{money(receivedThisPeriod.toFixed(2))}</div>
          <div className="stat-foot">Payments verified in this period</div>
        </div>
        <div className="card">
          <div className="stat-label">Collection percentage</div>
          <div className="stat-value up">{collectionPct}%</div>
          <div className="stat-foot">of invoiced fees collected</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div className="stat-label-row">
          <h3 style={{ margin: 0 }}>Invoices by status</h3>
        </div>
        <div className="status-strip">
          {Object.keys(statusLabels).map((k) => (
            <div className="status-chip" key={k}>
              <div className="n">{statusCounts[k] || 0}</div>
              <div className="l">{statusLabels[k]}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-2">
        <RevenueBarList title="Revenue by auction" items={stats.revenueByAuction || []} nameKey="auctionName" />
        <RevenueBarList title="Revenue by client" items={stats.revenueByClient || []} nameKey="clientName" />
      </div>
    </div>
  );
}