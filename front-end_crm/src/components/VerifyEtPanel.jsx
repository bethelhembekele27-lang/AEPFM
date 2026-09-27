import { useState } from "react";
import { apiCall } from "../api";
import { verifyEtStatus } from "../verifyEtStatus";

const VERIFY_ET_BANKS = [
  { v: "", l: "Let Verify.ET detect it" },
  { v: "cbe", l: "CBE" }, { v: "telebirr", l: "Telebirr" }, { v: "boa", l: "Bank of Abyssinia" },
  { v: "dashen", l: "Dashen Bank" }, { v: "awash", l: "Awash Bank" }, { v: "cbebirr", l: "CBE Birr" },
  { v: "mpesa", l: "MPESA" }, { v: "siinqee", l: "Siinqee Bank" }, { v: "kaafiebirr", l: "Kaafi Ebirr" },
];
const SUFFIX_BANKS = ["cbe", "boa"];
const PHONE_BANKS = ["cbebirr"];

export const ShieldIcon = () => (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>);

export default function VerifyEtPanel({ payment, token, onUpdated }) {
  // What the bidder typed beats what the AI guessed: a masked receipt can
  // never yield a CBE/BoA account suffix, so OCR loses to a human here.
  const detectedBank = payment?.bidderBank || payment?.extraction?.detectedBank || "";
  const [bank, setBank] = useState(detectedBank);
  const [ref, setRef] = useState(payment?.bidderReferenceNumber || payment?.extraction?.bankReferenceNumber || "");
  const [suffix, setSuffix] = useState(payment?.bidderAccountSuffix || "");
  const [phone, setPhone] = useState(payment?.bidderPhoneNumber || payment?.extraction?.detectedPhoneNumber || "");
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [check, setCheck] = useState(payment?.verifyEtCheck || null);

  async function run() {
    setChecking(true);
    setError("");
    try {
      const res = await apiCall(`/api/receipts/${payment.id}/verify-transaction/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ bank, referenceNumber: ref, accountSuffix: suffix, phoneNumber: phone }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Check failed"); return; }
      setCheck(data);
      onUpdated?.(data);
    } catch (err) {
      setError("Network error");
      console.error(err);
    } finally {
      setChecking(false);
    }
  }

  const amountMismatch = check?.amount && Number(check.amount) !== Number(payment.amountPaid);
  const settlementFailed = check?.settlementMatched === false;
  const status = verifyEtStatus(check, payment.amountPaid);

  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", background: "var(--paper)", borderBottom: "1px solid var(--border)" }}>
        <span style={{ color: "var(--brass)" }}><ShieldIcon /></span>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Verify with Verify.ET</span>
        {payment.autoReviewed && (
          <span className="badge-note" style={{ marginLeft: "auto", background: "var(--blue-bg)", color: "var(--blue)" }}>Auto-verified</span>
        )}
      </div>

      <div style={{ padding: 16 }}>
        <div className="section-label" style={{ marginTop: 0, marginBottom: 10 }}>Payment details</div>
        <div className="field-grid" style={{ marginBottom: 10, gap: "10px 20px" }}>
          <div className="field">
            <div className="fl">Bank</div>
            <select value={bank} onChange={(e) => setBank(e.target.value)}>
              {VERIFY_ET_BANKS.map((b) => <option key={b.v} value={b.v}>{b.l}</option>)}
            </select>
            {detectedBank && bank === detectedBank && (
              <div style={{ fontSize: 11, color: "var(--blue)", marginTop: 4 }}>
                {payment?.bidderBank ? "From the bidder's payment details." : "AI detected this bank from the receipt."}
              </div>
            )}
            {!bank && (
              <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 4 }}>
                Auto-detect can fail for banks that require an account suffix (CBE, BOA) — pick the bank explicitly if the check errors out.
              </div>
            )}
          </div>
          <div className="field">
            <div className="fl">Reference number</div>
            <input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="e.g. FT1234567890" />
          </div>
          {SUFFIX_BANKS.includes(bank) && (
            <div className="field"><div className="fl">Account suffix</div><input value={suffix} onChange={(e) => setSuffix(e.target.value)} /></div>
          )}
          {PHONE_BANKS.includes(bank) && (
            <div className="field"><div className="fl">Phone</div><input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="251911234567" /></div>
          )}
        </div>

        <button className="btn btn-sm btn-brass" onClick={run} disabled={checking || !ref.trim()}>
          {checking ? "Checking..." : "Check with Verify.ET"}
        </button>

        {error && (
          error === "Verify.ET is not configured on this server." ? (
            <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-3)", fontStyle: "italic" }}>Verify.ET isn't set up yet.</div>
          ) : (
            <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--red)" }}>{error}</div>
          )
        )}

        {check && check.processingStatus === "completed" && (
          <div style={{ marginTop: 18 }}>
            <div className="section-label" style={{ margin: "0 0 10px" }}>Result</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <span className={`stamp ${status.color}`} style={{ fontSize: 12 }}>{status.label}</span>
              {check.amount && <span className="mono amount" style={{ fontSize: 13.5 }}>ETB {check.amount}</span>}
            </div>
            {check.verified && (
              <div style={{ fontSize: 12.5, lineHeight: 1.7, color: "var(--text-2)" }}>
                <div>Sender: {check.senderName || "—"}</div>
                <div>Receiver: {check.receiverName || "—"}</div>
              </div>
            )}
            {amountMismatch && (
              <div style={{ background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5 }}>
                Verify.ET's amount ({check.amount}) doesn't match the recorded payment ({payment.amountPaid}). Informational only.
              </div>
            )}
            {check.possibleDuplicate && (
              <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "12px 14px", marginTop: 10, fontSize: 13, fontWeight: 600, border: "1px solid var(--red)" }}>
                ⚠ This exact reference number was already used and approved on a different invoice. Do not approve without investigating — this may be a reused or reissued transaction.
              </div>
            )}
            {settlementFailed && (              <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "12px 14px", marginTop: 10, fontSize: 13, fontWeight: 600, border: "1px solid var(--red)" }}>
                ⚠ This transaction did NOT go to Auction Ethiopia's own account. Review carefully before approving.
              </div>
            )}
          </div>
        )}
        {check && check.processingStatus !== "completed" && (
          <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-3)" }}>Still processing — check again shortly.</div>
        )}
      </div>
    </div>
  );
}
