import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall, API_BASE } from "../api";

function fileUrl(path) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export default function ManagerReview({ role, token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState([]);
  const [reviewing, setReviewing] = useState(null); // "approve" | "reject" | null
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);

  const canManage = role === "administrator" || role === "auction_manager";

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { if (canManage) fetchRows(); else setLoading(false); }, []);

  async function fetchRows() {
    setLoading(true);
    setError("");
    try {
      const res = await apiCall("/api/receipts/", {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Failed to load receipts"); return; }
      setRows(data);
      setSelected([]);
    } catch (err) {
      setError("Network error loading receipts");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function toggleRow(id) {
    setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  }
  function toggleAll() {
    setSelected(selected.length === rows.length ? [] : rows.map((r) => r.id));
  }

  function openReview(decision) {
    if (selected.length === 0) { window.alert("Select at least one receipt first."); return; }
    setReviewing(decision);
    setNote("");
  }

  async function submitReview() {
    if (reviewing === "reject" && !note.trim()) {
      window.alert("A note is required when rejecting a receipt.");
      return;
    }
    setSaving(true);
    try {
      for (const id of selected) {
        const res = await apiCall(`/api/receipts/${id}/review/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Token ${token}` } : {}),
          },
          body: JSON.stringify({ decision: reviewing, note }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          window.alert(`Failed on payment #${id}: ${data.error || "unknown error"}`);
        }
      }
      setReviewing(null);
      setSelected([]);
      await fetchRows();
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
        <div className="locked-note">
          Only Administrators and Auction Managers can review bidder-submitted receipts.
        </div>
      </div>
    );
  }

  if (loading) return <div style={{ padding: 20 }}>Loading receipts…</div>;
  if (error) return <div style={{ padding: 20, color: "red" }}>{error}</div>;

  return (
    <div>
      <div className="queue-note" style={{ marginBottom: 14 }}>
        Receipts bidders submitted through their public invoice link, waiting for review before Finance sees them.
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 12, alignItems: "center" }}>
        {selected.length > 0 && (
          <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>{selected.length} selected</span>
        )}
        {selected.length === 1 && (() => {
          const row = rows.find((r) => r.id === selected[0]);
          return row?.receiptUrl ? (
            <a href={fileUrl(row.receiptUrl)} target="_blank" rel="noopener noreferrer" className="btn btn-sm" style={{ display: "inline-flex", alignItems: "center", gap: 6 }} title="View receipt">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              View receipt
            </a>
          ) : null;
        })()}
        <button className="btn btn-brass" onClick={() => openReview("approve")} disabled={selected.length === 0}>
          Approve selected
        </button>
        <button className="btn btn-danger" onClick={() => openReview("reject")} disabled={selected.length === 0}>
          Reject selected
        </button>
      </div>

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}>
                  <input
                    type="checkbox"
                    checked={rows.length > 0 && selected.length === rows.length}
                    onChange={toggleAll}
                    aria-label="Select all"
                  />
                </th>
                <th>Invoice #</th>
                <th>Bidder</th>
                <th>Phone</th>
                <th>Amount</th>
                <th>Submitted</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", color: "var(--text-3)", padding: 24 }}>
                    Nothing pending review
                  </td>
                </tr>
              ) : rows.map((p) => (
                <tr key={p.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.includes(p.id)}
                      onChange={() => toggleRow(p.id)}
                      aria-label={`Select payment ${p.invoiceNumber}`}
                    />
                  </td>
                  <td className="mono">{p.invoiceNumber}</td>
                  <td>{p.bidderName}</td>
                  <td className="mono">{p.winnerPhone}</td>
                  <td className="amount">{money(p.amountPaid)}</td>
                  <td className="mono">{new Date(p.uploadedAt).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {reviewing && (
        <div
          className="overlay active"
          onClick={(e) => { if (e.target === e.currentTarget) setReviewing(null); }}
        >
          <div className="modal" style={{ maxWidth: 480 }}>
            <div className="modal-head">
              <h2 style={{ margin: 0 }}>
                {reviewing === "approve" ? "Approve" : "Reject"} {selected.length} receipt{selected.length !== 1 ? "s" : ""}
              </h2>
              <button className="modal-close" onClick={() => setReviewing(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14, padding: 12, borderRadius: 8, background: reviewing === "approve" ? "var(--green-bg)" : "var(--red-bg)" }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={reviewing === "approve" ? "var(--green)" : "var(--red)"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                  {reviewing === "approve" ? <path d="M20 6L9 17l-5-5" /> : <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>}
                </svg>
                <div style={{ fontSize: 13, color: reviewing === "approve" ? "var(--green)" : "var(--red)" }}>
                  {reviewing === "approve"
                    ? `This will mark ${selected.length} invoice(s) as Paid immediately.`
                    : `The bidder will be notified by SMS and asked to resubmit.`}
                </div>
              </div>
              <div className="field" style={{ marginBottom: 14 }}>
                <div className="fl">Note {reviewing === "reject" && <span className="req">*</span>}
                  {reviewing === "approve" && <span className="opt"> (optional)</span>}
                </div>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder={reviewing === "reject" ? "e.g. Amount doesn't match, receipt is blurry, wrong bank account..." : "Any internal note about this approval"}
                  style={{ width: "100%", fontFamily: "'Inter'", fontSize: 14, padding: 10, border: "1px solid var(--border)", borderRadius: 6 }}
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className={`btn ${reviewing === "approve" ? "btn-brass" : "btn-danger"}`} onClick={submitReview} disabled={saving}>
                  {saving ? "Saving..." : reviewing === "approve" ? `Mark ${selected.length} invoice(s) as Paid` : `Reject & notify bidder`}
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
