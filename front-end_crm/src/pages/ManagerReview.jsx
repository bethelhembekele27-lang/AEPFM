import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall } from "../api";

export default function ManagerReview({ role, token }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewing, setReviewing] = useState(null); // { payment, decision } | null
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
    } catch (err) {
      setError("Network error loading receipts");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function openReview(payment, decision) {
    setReviewing({ payment, decision });
    setNote("");
  }

  async function submitReview() {
    if (reviewing.decision === "reject" && !note.trim()) {
      window.alert("A note is required when rejecting a receipt.");
      return;
    }
    setSaving(true);
    try {
      const res = await apiCall(`/api/receipts/${reviewing.payment.id}/review/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ decision: reviewing.decision, note }),
      });
      const data = await res.json();
      if (!res.ok) { window.alert(data.error || "Review failed"); return; }
      setReviewing(null);
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

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Bidder</th>
                <th>Phone</th>
                <th>Amount</th>
                <th>Submitted</th>
                <th>Receipt</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "var(--text-3)", padding: 24 }}>
                    Nothing pending review
                  </td>
                </tr>
              ) : rows.map((p) => (
                <tr key={p.id}>
                  <td className="mono">{p.invoiceNumber}</td>
                  <td>{p.bidderName}</td>
                  <td className="mono">{p.winnerPhone}</td>
                  <td className="amount">{money(p.amountPaid)}</td>
                  <td className="mono">{new Date(p.uploadedAt).toLocaleString()}</td>
                  <td>
                    {p.receiptUrl
                      ? <a href={p.receiptUrl} target="_blank" rel="noopener noreferrer" className="btn btn-sm">View</a>
                      : <span style={{ color: "var(--text-3)" }}>—</span>
                    }
                  </td>
                  <td className="row-actions">
                    <button className="btn btn-sm btn-brass" onClick={() => openReview(p, "approve")}>
                      Approve
                    </button>
                    <button className="btn btn-sm btn-danger" onClick={() => openReview(p, "reject")}>
                      Reject
                    </button>
                  </td>
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
                {reviewing.decision === "approve" ? "Approve" : "Reject"} receipt — {reviewing.payment.invoiceNumber}
              </h2>
              <button className="modal-close" onClick={() => setReviewing(null)}>&times;</button>
            </div>
            <div className="modal-body">
              {reviewing.decision === "reject" && (
                <div className="locked-note" style={{ marginBottom: 10 }}>
                  The bidder will be sent an SMS with this note and a link to resubmit.
                </div>
              )}
              <div className="field" style={{ marginBottom: 14 }}>
                <div className="fl">
                  Note {reviewing.decision === "reject" && <span className="req">*</span>}
                </div>
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  style={{
                    width: "100%",
                    fontFamily: "'Inter'",
                    fontSize: 14,
                    padding: 10,
                    border: "1px solid var(--border)",
                    borderRadius: 6,
                  }}
                />
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  className={`btn ${reviewing.decision === "approve" ? "btn-brass" : "btn-danger"}`}
                  onClick={submitReview}
                  disabled={saving}
                >
                  {saving
                    ? "Saving…"
                    : reviewing.decision === "approve" ? "Confirm approve" : "Confirm reject"
                  }
                </button>
                <button className="btn btn-ghost" onClick={() => setReviewing(null)} disabled={saving}>
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
