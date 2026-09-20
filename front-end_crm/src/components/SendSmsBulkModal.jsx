import { useState } from "react";
import { apiCall } from "../api";

export default function SendSmsBulkModal({ invoices, onClose, onDone, token }) {
  const [dueDays, setDueDays] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleSend() {
    setSending(true);
    setError("");
    try {
      const body = { invoiceIds: invoices.map((i) => i.id) };
      if (dueDays) body.dueDays = Number(dueDays);
      const res = await apiCall('/api/invoices/sms/bulk-send/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || 'Bulk send failed'); return; }
      setResult(data);
    } catch (err) {
      setError('Network error sending SMS');
      console.error(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 560 }}>
        <div className="modal-head">
          <h2 style={{ margin: 0 }}>Send SMS to {invoices.length} invoice{invoices.length === 1 ? "" : "s"}</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          {!result ? (
            <>
              <div className="tbl-wrap" style={{ marginBottom: 14, maxHeight: 220, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Invoice #</th><th>Bidder</th><th>Phone</th></tr></thead>
                  <tbody>
                    {invoices.map((inv) => (
                      <tr key={inv.id}>
                        <td className="mono">{inv.invoiceNumber}</td>
                        <td>{inv.bidderName}</td>
                        <td className="mono">{inv.winnerPhone}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="field" style={{ maxWidth: 220, marginBottom: 14 }}>
                <div className="fl">Days until due <span className="opt">(optional — defaults per invoice)</span></div>
                <input type="number" min="1" max="90" value={dueDays} onChange={(e) => setDueDays(e.target.value)} />
              </div>
              <div className="locked-note" style={{ marginBottom: 14 }}>
                Each invoice gets its own auto-generated message. Invoices with an invalid phone, a closed/unready status, or a very recent send are skipped automatically and reported below.
              </div>
              {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-brass" onClick={handleSend} disabled={sending}>
                  {sending ? "Sending..." : `Send ${invoices.length} SMS`}
                </button>
                <button className="btn btn-ghost" onClick={onClose} disabled={sending}>Cancel</button>
              </div>
            </>
          ) : (
            <>
              <div className="login-success" style={{ marginBottom: 14 }}>
                Sent: {result.sent.length}. Skipped: {result.skipped.length}.
              </div>
              {result.skipped.length > 0 && (
                <div className="tbl-wrap" style={{ marginBottom: 14 }}>
                  <table>
                    <thead><tr><th>Invoice #</th><th>Reason skipped</th></tr></thead>
                    <tbody>
                      {result.skipped.map((s, i) => (
                        <tr key={i}><td className="mono">{s.invoiceNumber || s.invoiceId}</td><td style={{ color: "var(--red)" }}>{s.reason}</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <button className="btn btn-brass" onClick={() => { onDone(); onClose(); }}>Done</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
