import { useState, useEffect } from "react";
import { apiCall } from "../api";

// Amharic (non-ASCII) SMS is sent as Unicode: 70 characters per single SMS, 67 per part when split.
function smsParts(text) {
  const chars = [...text];
  if (chars.length === 0) return 0;
  const ascii = chars.every((c) => c.charCodeAt(0) < 128);
  const single = ascii ? 160 : 70;
  const multi = ascii ? 153 : 67;
  return chars.length <= single ? 1 : Math.ceil(chars.length / multi);
}

export default function SendSms({ invoiceId, onBack }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [days, setDays] = useState("");
  const [message, setMessage] = useState("");
  const [touched, setTouched] = useState(false); // staff edited the message by hand
  const [step, setStep] = useState(1); // 1 = compose, 2 = review and send, 3 = result
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    loadPreview(null, true);
  }, [invoiceId]);

  async function loadPreview(dueDays, replaceMessage) {
    setError("");
    try {
      const qs = dueDays ? `?dueDays=${encodeURIComponent(dueDays)}` : "";
      const res = await apiCall(`/api/invoices/${invoiceId}/sms/preview/${qs}`, { method: "GET" });
      const body = await res.json();
      if (!res.ok) {
        setError(body.error || body.detail || "Could not prepare the SMS.");
        return;
      }
      setData(body);
      setDays(String(body.dueDays));
      if (replaceMessage) {
        setMessage(body.message);
        setTouched(false);
      }
    } catch (err) {
      setError("Network error while preparing the SMS.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function send() {
    setSending(true);
    setError("");
    try {
      const res = await apiCall(`/api/invoices/${invoiceId}/sms/send/`, {
        method: "POST",
        body: JSON.stringify({ message, dueDays: Number(days) }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(body.error || body.detail || "Sending failed.");
        return;
      }
      setResult(body);
      setStep(3);
    } catch (err) {
      setError("Network error while sending.");
      console.error(err);
    } finally {
      setSending(false);
    }
  }

  if (loading) return <div style={{ padding: 20 }}>Loading...</div>;

  if (!data) {
    return (
      <div className="card">
        <h3 style={{ margin: "0 0 8px" }}>Send SMS</h3>
        <div style={{ color: "var(--red)", fontSize: 13, marginBottom: 14 }}>{error || "Could not load this invoice."}</div>
        <button className="btn" onClick={onBack}>Back to invoices</button>
      </div>
    );
  }

  const daysNum = Number(days);
  const daysValid = Number.isInteger(daysNum) && daysNum >= 1 && daysNum <= 90;
  const daysSynced = String(data.dueDays) === String(days);
  const parts = smsParts(message);
  const linkMissing = !message.includes(data.link);
  const canContinue = Boolean(data.phone) && daysValid && daysSynced && message.trim().length > 0;
  const testMode = data.backend === "console";

  return (
    <div className="card" style={{ maxWidth: 720 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 4 }}>
        <h3 style={{ margin: 0 }}>Send SMS - {data.invoiceNumber}</h3>
        {step < 3 && <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>Step {step} of 2 - {step === 1 ? "Compose" : "Review and send"}</div>}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 14 }}>{data.bidderName}</div>

      {testMode && (
        <div className="login-error" style={{ marginTop: 0, marginBottom: 14 }}>
          TEST MODE: the server is set to SMS_BACKEND=console, so nothing is really sent to the bidder.
        </div>
      )}

      {data.smsSendCount > 0 && step < 3 && (
        <div className="queue-note" style={{ marginBottom: 12 }}>
          An SMS was already sent {data.smsSendCount} time(s); the last one on {new Date(data.smsSentAt).toLocaleString()}.
          Sending again keeps the current deadline unless you change the number of days.
        </div>
      )}

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      {step === 1 && (
        <>
          <div className="field-grid">
            <div className="field">
              <div className="fl">Recipient</div>
              {data.phone ? (
                <div className="fv mono">+{data.phone}</div>
              ) : (
                <div style={{ color: "var(--red)", fontSize: 13 }}>
                  "{data.rawPhone}" is not a valid Ethiopian mobile number. Fix it on the winner record first.
                </div>
              )}
            </div>
            <div className="field">
              <div className="fl">Payment due in (days from today)</div>
              <input
                type="number"
                min="1"
                max="90"
                value={days}
                onChange={(e) => setDays(e.target.value)}
                onBlur={() => daysValid && loadPreview(days, !touched)}
                onKeyDown={(e) => { if (e.key === "Enter" && daysValid) loadPreview(days, !touched); }}
              />
              <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4 }}>
                {daysSynced ? `Deadline: ${data.dueDate}` : "Press Tab or Enter to update the deadline"}
              </div>
            </div>
          </div>

          <div className="fl" style={{ marginBottom: 4 }}>Message (you can edit it)</div>
          <textarea
            value={message}
            onChange={(e) => { setMessage(e.target.value); setTouched(true); }}
            rows={6}
            style={{ width: "100%", fontSize: 14, lineHeight: 1.7, padding: 10, border: "1px solid var(--border)", borderRadius: 6 }}
          />
          <div style={{ fontSize: 12, color: "var(--text-3)", margin: "4px 0 8px" }}>
            {[...message].length} characters, about {parts} SMS part{parts === 1 ? "" : "s"} (Amharic uses 70 characters per SMS)
          </div>
          {touched && (
            <button className="btn btn-sm btn-ghost" onClick={() => loadPreview(days, true)}>Reset to the standard message</button>
          )}
          {linkMissing && (
            <div style={{ color: "var(--amber)", fontSize: 12.5, marginTop: 8 }}>
              Warning: the bidder's invoice link is not in this message, so they will not be able to open their invoice.
            </div>
          )}

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-brass" disabled={!canContinue} onClick={() => setStep(2)}>Next: review</button>
            <button className="btn btn-ghost" onClick={onBack}>Cancel</button>
          </div>
        </>
      )}

      {step === 2 && (
        <>
          <div className="field-grid">
            <div className="field"><div className="fl">To</div><div className="fv mono">+{data.phone}</div></div>
            <div className="field"><div className="fl">Payment deadline</div><div className="fv mono">{data.dueDate} ({days} days)</div></div>
          </div>
          <div className="fl" style={{ marginBottom: 4 }}>This exact text will be sent</div>
          <div style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", background: "var(--paper)", border: "1px solid var(--border)", borderRadius: 6, padding: 12, fontSize: 14, lineHeight: 1.7 }}>
            {message}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6 }}>
            About {parts} SMS part{parts === 1 ? "" : "s"}. Sending sets the invoice's due date to {data.dueDate}.
          </div>
          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-brass" onClick={send} disabled={sending}>{sending ? "Sending..." : "Send SMS"}</button>
            <button className="btn" onClick={() => setStep(1)} disabled={sending}>Back to edit</button>
          </div>
        </>
      )}

      {step === 3 && result && (
        <>
          <div className="login-success" style={{ marginBottom: 14 }}>
            SMS handed to the gateway. Payment deadline set to {result.dueDate}.
          </div>
          <div className="locked-note" style={{ marginTop: 0, marginBottom: 14 }}>
            "Handed to the gateway" means the SMS service accepted it. It is not a delivery confirmation.
          </div>
          <button className="btn btn-brass" onClick={onBack}>Back to invoices</button>
        </>
      )}
    </div>
  );
}
