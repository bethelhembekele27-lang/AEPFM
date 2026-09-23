import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall, API_BASE } from "../api";

function fileUrl(path) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

const EyeIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const CheckIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M20 6L9 17l-5-5" />
  </svg>
);

const XIcon = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const TABS = [
  { key: "pending_manager_review", label: "Pending" },
  { key: "manager_approved", label: "Approved" },
  { key: "manager_rejected", label: "Rejected" },
];

export default function ManagerReview({ role, token }) {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({ pending_manager_review: null, manager_approved: null, manager_rejected: null });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState([]);
  const [tab, setTab] = useState("pending_manager_review");
  const [reviewing, setReviewing] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const canManage = role === "administrator" || role === "auction_manager";

  useEffect(() => { if (canManage) { fetchRows(tab); fetchCounts(); } else setLoading(false); }, [tab]);

  async function fetchRows(status) {
    setLoading(true);
    setError("");
    try {
      const res = await apiCall(`/api/receipts/?verificationStatus=${status}`, { headers: token ? { Authorization: `Token ${token}` } : {} });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Failed to load receipts"); return; }
      setRows(data);
    } catch (err) {
      setError("Network error loading receipts");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchCounts() {
    try {
      const results = await Promise.all(TABS.map((t) =>
        apiCall(`/api/receipts/?verificationStatus=${t.key}`, { headers: token ? { Authorization: `Token ${token}` } : {} }).then((r) => r.json())
      ));
      setCounts({
        pending_manager_review: results[0]?.length ?? 0,
        manager_approved: results[1]?.length ?? 0,
        manager_rejected: results[2]?.length ?? 0,
      });
    } catch (err) {
      console.error("Failed to load counts", err);
    }
  }

  function switchTab(t) {
    setTab(t);
    setSelected([]);
  }

  function toggleRow(id) {
    setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  }
  function toggleAll() {
    setSelected(selected.length === rows.length ? [] : rows.map((r) => r.id));
  }

  function openReview(decision) {
    if (selected.length === 0) return;
    setReviewing(decision);
    setNote("");
  }

  async function submitReview() {
    if (reviewing === "reject" && !note.trim()) return;
    setSaving(true);
    try {
      for (const id of selected) {
        const res = await apiCall(`/api/receipts/${id}/review/`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
          body: JSON.stringify({ decision: reviewing, note }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          window.alert(`Failed on payment #${id}: ${data.error || "unknown error"}`);
        }
      }
      setReviewing(null);
      setSelected([]);
      await fetchRows(tab);
      await fetchCounts();
    } catch (err) {
      window.alert("Network error submitting review");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  if (!canManage) {
    return (
      <div className="card">
        <h3 style={{ margin: "0 0 6px" }}>Receipt verification</h3>
        <div className="locked-note">Only Administrators and Auction Managers can review bidder-submitted receipts.</div>
      </div>
    );
  }

  const selectedRow = selected.length === 1 ? rows.find((r) => r.id === selected[0]) : null;

  return (
    <div>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ margin: "0 0 4px" }}>Receipt verification</h2>
        <div style={{ fontSize: 13, color: "var(--text-2)" }}>
          Receipts bidders submitted through their public invoice link, reviewed here before Finance sees them.
        </div>
      </div>

      <div className="status-strip" style={{ margin: "0 0 20px" }}>
        {TABS.map((t) => (
          <div
            key={t.key}
            className="status-chip"
            style={{ cursor: "pointer", borderColor: tab === t.key ? "var(--brass)" : "var(--border)", boxShadow: tab === t.key ? "0 0 0 1px var(--brass) inset" : "none" }}
            onClick={() => switchTab(t.key)}
          >
            <div className="n">{counts[t.key] ?? "—"}</div>
            <div className="l">{t.label}</div>
          </div>
        ))}
      </div>

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>
          {selected.length > 0 ? `${selected.length} selected` : loading ? "Loading..." : `${rows.length} record(s)`}
        </div>
        {tab === "pending_manager_review" && (
          <div style={{ display: "flex", gap: 8 }}>
            {selectedRow?.receiptUrl && (
              <a href={fileUrl(selectedRow.receiptUrl)} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-icon-only" title="View receipt">
                <EyeIcon />
              </a>
            )}
            <button className="btn btn-sm btn-brass" onClick={() => openReview("approve")} disabled={selected.length === 0}>Approve</button>
            <button className="btn btn-sm btn-danger" onClick={() => openReview("reject")} disabled={selected.length === 0}>Reject</button>
          </div>
        )}
        {tab !== "pending_manager_review" && selectedRow?.receiptUrl && (
          <a href={fileUrl(selectedRow.receiptUrl)} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-icon-only" title="View receipt">
            <EyeIcon />
          </a>
        )}
      </div>

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}><input type="checkbox" checked={rows.length > 0 && selected.length === rows.length} onChange={toggleAll} /></th>
                <th>Invoice #</th><th>Bidder</th><th>Phone</th><th>Amount</th><th>{tab === "pending_manager_review" ? "Submitted" : "Reviewed"}</th>
                {tab !== "pending_manager_review" && <th>Note</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--text-3)", padding: 24 }}>Loading...</td></tr>
              ) : rows.length === 0 ? (
                <tr><td colSpan={7} style={{ textAlign: "center", color: "var(--text-3)", padding: 24 }}>Nothing here</td></tr>
              ) : rows.map((p) => (
                <tr key={p.id} onClick={() => toggleRow(p.id)} style={{ cursor: "pointer" }}>
                  <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleRow(p.id)} /></td>
                  <td className="mono">{p.invoiceNumber}</td>
                  <td>{p.bidderName}</td>
                  <td className="mono">{p.winnerPhone}</td>
                  <td className="amount">{money(p.amountPaid)}</td>
                  <td className="mono">{new Date(tab === "pending_manager_review" ? p.uploadedAt : p.managerVerifiedDate).toLocaleString()}</td>
                  {tab !== "pending_manager_review" && (
                    <td style={{ fontSize: 12.5, color: "var(--text-3)", maxWidth: 200 }}>{p.managerNote || "—"}</td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {reviewing && (
        <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) setReviewing(null); }}>
          <div className="modal" style={{ maxWidth: 440 }}>
            <div style={{ padding: "32px 28px 24px", textAlign: "center", borderBottom: "1px solid var(--border)" }}>
              <div style={{
                width: 56, height: 56, borderRadius: "50%", margin: "0 auto 16px",
                display: "flex", alignItems: "center", justifyContent: "center",
                background: reviewing === "approve" ? "var(--green-bg)" : "var(--red-bg)",
                color: reviewing === "approve" ? "var(--green)" : "var(--red)",
              }}>
                {reviewing === "approve" ? <CheckIcon /> : <XIcon />}
              </div>
              <h3 style={{ margin: "0 0 6px", fontSize: 17 }}>
                {reviewing === "approve" ? "Approve" : "Reject"} {selected.length} receipt{selected.length === 1 ? "" : "s"}?
              </h3>
              <div style={{ fontSize: 13, color: "var(--text-2)", lineHeight: 1.5 }}>
                {reviewing === "approve"
                  ? `This immediately marks ${selected.length === 1 ? "this invoice" : "these invoices"} as Paid.`
                  : "The bidder will be notified by SMS and asked to resubmit a receipt."}
              </div>
            </div>
            <div style={{ padding: "20px 28px 28px" }}>
              <label style={{ display: "block", fontSize: 11.5, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-3)", marginBottom: 6 }}>
                Note {reviewing === "reject" ? <span className="req">(required)</span> : <span className="opt">(optional)</span>}
              </label>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                autoFocus
                placeholder={reviewing === "reject" ? "e.g. amount doesn't match, receipt is blurry, wrong account..." : "Internal note, visible in the audit trail"}
                style={{ width: "100%", fontFamily: "'Inter'", fontSize: 13.5, padding: 10, border: "1px solid var(--border)", borderRadius: 8, marginBottom: 18, resize: "vertical" }}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className={`btn ${reviewing === "approve" ? "btn-brass" : "btn-danger"}`}
                  style={{ flex: 1 }}
                  onClick={submitReview}
                  disabled={saving || (reviewing === "reject" && !note.trim())}
                >
                  {saving ? "Saving..." : reviewing === "approve" ? "Confirm approve" : "Confirm reject"}
                </button>
                <button className="btn btn-ghost" onClick={() => setReviewing(null)} disabled={saving}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
