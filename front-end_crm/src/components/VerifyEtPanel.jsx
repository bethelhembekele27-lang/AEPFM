import { useState, useEffect, useRef } from "react";
import { apiCall } from "../api";
import { verifyEtStatus } from "../verifyEtStatus";

const ShieldIcon = () => (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>);

export { ShieldIcon };

export default function VerifyEtPanel({ payment, token, onUpdated, onPaymentRefreshed }) {
  const [ref, setRef] = useState(payment?.verifyEtCheck?.referenceNumber || payment?.extraction?.bankReferenceNumber || "");
  const [suffix, setSuffix] = useState("");
  const [advanced, setAdvanced] = useState(false);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [check, setCheck] = useState(payment?.verifyEtCheck || null);
  const polls = useRef(0);
  const [reprocessing, setReprocessing] = useState(false);
  const auth = token ? { Authorization: `Token ${token}` } : {};
  const pending = check && check.processingStatus !== "completed" && check.processingStatus !== "failed";

  // pick up a reference/check that finished after the panel opened
  useEffect(() => {
    setCheck((c) => payment?.verifyEtCheck || c);
    setRef((cur) => cur || payment?.verifyEtCheck?.referenceNumber || payment?.extraction?.bankReferenceNumber || "");
  }, [payment?.extraction?.bankReferenceNumber, payment?.verifyEtCheck?.processingStatus]);

  async function reprocess() {
    setReprocessing(true); setError("");
    try {
      const res = await apiCall(`/api/receipts/${payment.id}/reprocess/`, { method: "POST", headers: auth });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Re-run failed"); return; }
      onPaymentRefreshed?.(data);
    } catch (err) { setError("Network error"); console.error(err); } finally { setReprocessing(false); }
  }

  function accept(data) { setCheck(data); onUpdated?.(data); }

  async function run() {
    setChecking(true); setError(""); polls.current = 0;
    try {
      const res = await apiCall(`/api/receipts/${payment.id}/verify-transaction/`, {
        method: "POST", headers: { "Content-Type": "application/json", ...auth },
        body: JSON.stringify({ referenceNumber: ref, accountSuffix: suffix }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Check failed"); return; }
      accept(data);
    } catch (err) { setError("Network error"); console.error(err); } finally { setChecking(false); }
  }

  // A queued check is followed up automatically (every 5s, up to 12 times)
  useEffect(() => {
    if (!pending || polls.current >= 12) return;
    const t = setTimeout(async () => {
      polls.current += 1;
      try {
        const res = await apiCall(`/api/receipts/${payment.id}/verify-transaction/refresh/`, { method: "POST", headers: auth });
        const data = await res.json();
        if (res.ok) accept(data); else setError(data.error || "Refresh failed");
      } catch { /* retry next tick */ }
    }, 5000);
    return () => clearTimeout(t);
  }, [pending, check]);

  const due = payment.amountDue;
  const status = verifyEtStatus(check, due);
  const done = check && check.processingStatus === "completed";

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "var(--paper)", borderBottom: "1px solid var(--border)" }}>
        <span style={{ color: "var(--brass)" }}><ShieldIcon /></span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Verify with Verify.ET</span>
        <span className="badge-note" style={{ marginLeft: "auto" }}>CBE · Auction Ethiopia account</span>
        {payment.autoReviewed && <span className="badge-note" style={{ background: "var(--blue-bg)", color: "var(--blue)" }}>Auto-verified</span>}
      </div>
      {payment.autoProcessNote && (
        <div style={{ padding: "8px 14px", fontSize: 12, color: "var(--text-2)", background: "var(--blue-bg)", display: "flex", gap: 10, alignItems: "center", justifyContent: "space-between" }}>
          <span>{payment.autoProcessNote ? `Auto-processing: ${payment.autoProcessNote}` : "Auto-processing has not reported yet."}</span>
          {payment.verificationStatus === "pending_manager_review" && (
            <button type="button" className="btn btn-sm" onClick={reprocess} disabled={reprocessing}>{reprocessing ? "Running…" : "Re-run"}</button>
          )}
        </div>
      )}
      <div style={{ padding: 16 }}>
        <div className="section-label" style={{ marginTop: 0 }}>Transaction</div>
        <div className="field" style={{ marginBottom: 8 }}>
          <div className="fl">Reference number</div>
          <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. FT26268RZSXN" />
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => setAdvanced((a) => !a)}>{advanced ? "Hide" : "Advanced"}</button>
        {advanced && (
          <div className="field" style={{ margin: "8px 0" }}>
            <div className="fl">Account suffix override <span className="opt">(8 digits, only if the default fails)</span></div>
            <input value={suffix} onChange={(e) => setSuffix(e.target.value)} inputMode="numeric" />
          </div>
        )}
        <div style={{ marginTop: 10 }}>
          <button className="btn btn-sm btn-brass" onClick={run} disabled={checking || !ref.trim()}>{checking ? "Checking..." : "Check with Verify.ET"}</button>
        </div>
        {error && (error === "Verify.ET is not configured on this server."
          ? <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-3)", fontStyle: "italic" }}>Verify.ET isn't set up yet.</div>
          : <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--red)" }}>{error}</div>)}
        {pending && <div style={{ marginTop: 12, fontSize: 12.5, color: "var(--text-3)" }}>Verify.ET is still processing - refreshing automatically…</div>}
        {check?.processingStatus === "failed" && <div style={{ marginTop: 12, fontSize: 12.5, color: "var(--red)" }}>{check.errorMessage || "Verify.ET could not complete this check."}</div>}
        {done && (
          <div style={{ marginTop: 18 }}>
            <div className="section-label" style={{ margin: "0 0 10px" }}>Result</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span className={`stamp ${status.color}`} style={{ fontSize: 12 }}>{status.label}</span>
              {check.amount && <span className="mono amount" style={{ fontSize: 13.5 }}>ETB {check.amount}</span>}
            </div>
            <div style={{ fontSize: 12.5, lineHeight: 1.7, color: "var(--text-2)" }}>
              <div>Amount due: ETB {due}</div>
              <div>Sender: {check.senderName || "—"}</div>
              <div>Receiver: {check.receiverName || "—"}</div>
            </div>
            {payment.amountDiscrepancy === "underpaid" && <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5, fontWeight: 600 }}>Underpaid by ETB {payment.amountDiscrepancyAmount}. If rejected, the bidder is told this is still owed.</div>}
            {payment.amountDiscrepancy === "overpaid" && <div style={{ background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5 }}>Overpaid by ETB {payment.amountDiscrepancyAmount}. Flagged for follow-up; never auto-approved.</div>}
            {check.settlementMatched === false && <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "12px 14px", marginTop: 10, fontSize: 13, fontWeight: 600, border: "1px solid var(--red)" }}>⚠ This transaction did NOT go to Auction Ethiopia's account.</div>}
            {check.possibleDuplicate && <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "12px 14px", marginTop: 10, fontSize: 13, fontWeight: 600, border: "1px solid var(--red)" }}>⚠ This reference was already used and approved (or credited) on another invoice.</div>}
            {check.pendingDuplicate && !check.possibleDuplicate && <div style={{ background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5 }}>This reference also appears on another unreviewed receipt.</div>}
          </div>
        )}
      </div>
    </div>
  );
}
