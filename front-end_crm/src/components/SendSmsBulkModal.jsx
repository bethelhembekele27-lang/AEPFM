import { useState } from "react";
import { apiCall } from "../api";

export default function SendSmsBulkModal({ invoices, onClose, onDone, token }) {
  const [dueDays, setDueDays] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState(1); // 1 = configure, 2 = preview, 3 = result
  const [previews, setPreviews] = useState([]);
  const [loadingPreviews, setLoadingPreviews] = useState(false);

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
      setStep(3);
    } catch (err) {
      setError('Network error sending SMS');
      console.error(err);
    } finally {
      setSending(false);
    }
  }

  async function loadPreviews() {
    setLoadingPreviews(true);
    setError("");
    try {
      const results = await Promise.all(
        invoices.map(async (inv) => {
          const qs = dueDays ? `?dueDays=${encodeURIComponent(dueDays)}` : "";
          const res = await apiCall(`/api/invoices/${inv.id}/sms/preview/${qs}`, {
            headers: token ? { Authorization: `Token ${token}` } : {},
          });
          const data = await res.json();
          return { invoiceId: inv.id, invoiceNumber: inv.invoiceNumber, ok: res.ok, ...data };
        })
      );
      setPreviews(results);
      setStep(2);
    } catch (err) {
      setError("Failed to load message previews");
      console.error(err);
    } finally {
      setLoadingPreviews(false);
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
          {step === 1 && (
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
                <button className="btn btn-brass" onClick={loadPreviews} disabled={loadingPreviews}>
                  {loadingPreviews ? "Loading previews..." : "Preview messages"}
                </button>
                <button className="btn btn-ghost" onClick={onClose} disabled={sending}>Cancel</button>
              </div>
            </>
          )}
          {step === 2 && !result && (
            <>
              <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 10 }}>
                Review each message below, then confirm send.
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10, maxHeight: 320, overflowY: "auto", marginBottom: 14 }}>
                {previews.map((p) => (
                  <div key={p.invoiceId} className="card" style={{ padding: 12, background: p.ok ? "var(--paper)" : "var(--red-bg)" }}>
                    <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{p.invoiceNumber}</div>
                    {p.ok ? (
                      <div style={{ fontSize: 12.5, whiteSpace: "pre-wrap" }}>{p.message}</div>
                    ) : (
                      <div style={{ fontSize: 12.5, color: "var(--red)" }}>{p.error || "Cannot preview this invoice"}</div>
                    )}
                  </div>
                ))}
              </div>
              {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-brass" onClick={handleSend} disabled={sending}>
                  {sending ? "Sending..." : `Confirm send to ${previews.filter(p => p.ok).length} invoice(s)`}
                </button>
                <button className="btn" onClick={() => setStep(1)} disabled={sending}>Back</button>
              </div>
            </>
          )}
          {result && (
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
