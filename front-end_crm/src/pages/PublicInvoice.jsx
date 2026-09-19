import { useState, useEffect } from "react";
import { statusLabels, money } from "../data";
import { apiCall } from "../api";
import logo from "../logo";

const CLOSED_STATUSES = ["paid", "cancelled", "waived"];

const PAYMENT_METHODS = [
  { v: "bank_transfer", l: "Bank Transfer" },
  { v: "telebirr", l: "Telebirr" },
  { v: "cpo", l: "CPO" },
  { v: "other", l: "Other" },
];

export default function PublicInvoice({ token }) {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [receiptFile, setReceiptFile] = useState(null);
  const [amountPaid, setAmountPaid] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null); // { success, message } | null
  const [submitError, setSubmitError] = useState("");

  useEffect(() => {
    fetchInvoice();
  }, [token]);

  async function fetchInvoice() {
    setLoading(true);
    setLoadError("");
    try {
      const res = await apiCall(`/api/public/invoice/${token}/`, { method: "GET" });
      if (!res.ok) {
        setLoadError(res.status === 404 ? "Invoice not found. Check the link and try again." : "Failed to load invoice.");
        return;
      }
      const data = await res.json();
      setInvoice(data);
    } catch (err) {
      setLoadError("Network error loading invoice.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmitReceipt(e) {
    e.preventDefault();
    setSubmitError("");
    setSubmitResult(null);

    if (!receiptFile) {
      setSubmitError("Please attach a receipt file.");
      return;
    }
    if (!amountPaid) {
      setSubmitError("Please enter the amount paid.");
      return;
    }
    if (!paymentDate) {
      setSubmitError("Please enter the payment date.");
      return;
    }

    setSubmitting(true);
    const formData = new FormData();
    formData.append("receiptFile", receiptFile);
    formData.append("amountPaid", amountPaid);
    formData.append("paymentMethod", paymentMethod);
    formData.append("paymentDate", paymentDate);

    try {
      const res = await apiCall(`/api/public/invoice/${token}/receipt/`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        setSubmitError(data.error || data.detail || firstFieldError(data) || "Failed to submit receipt.");
        return;
      }
      setSubmitResult(data);
      await fetchInvoice();
    } catch (err) {
      setSubmitError("Network error submitting receipt.");
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  function firstFieldError(data) {
    for (const key of Object.keys(data || {})) {
      if (Array.isArray(data[key]) && data[key].length) return data[key][0];
    }
    return "";
  }

  return (
    <div style={{ minHeight: "100vh", background: "var(--paper)", display: "flex", justifyContent: "center", padding: "32px 16px" }}>
      <div style={{ width: "100%", maxWidth: 640 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 24 }}>
          <img src={logo} alt="Auction Ethiopia S.C." style={{ height: 46, width: "auto" }} />
        </div>

        {loading && (
          <div className="card" style={{ textAlign: "center", padding: 32 }}>Loading your invoice…</div>
        )}

        {!loading && loadError && (
          <div className="card" style={{ textAlign: "center", padding: 32, color: "var(--red)" }}>{loadError}</div>
        )}

        {!loading && !loadError && invoice && (
          <>
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
                <div>
                  <h2 style={{ margin: 0 }}>{invoice.invoiceNumber}</h2>
                  <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 2 }}>
                    {invoice.bidderName}{invoice.companyName ? ` · ${invoice.companyName}` : ""}
                  </div>
                </div>
                <span className={`stamp ${invoice.status}`}>{statusLabels[invoice.status] || invoice.status}</span>
              </div>

              <div className="field-grid" style={{ marginBottom: 4 }}>
                <div className="field"><div className="fl">Invoice date</div><div className="fv mono">{invoice.invoiceDate}</div></div>
                <div className="field"><div className="fl">Due date</div><div className="fv mono">{invoice.dueDate}</div></div>
                <div className="field"><div className="fl">Total amount</div><div className="fv mono">{money(invoice.totalAmount)}</div></div>
              </div>

              <div className="section-label">Lots ({invoice.lots?.length || 0})</div>
              <div className="tbl-wrap">
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead><tr><th>Lot #</th><th>Auction</th><th>Winning amount</th><th>Fee %</th><th>Lot fee</th></tr></thead>
                    <tbody>
                      {(invoice.lots || []).map((l) => (
                        <tr key={l.id || l.lotNumber}>
                          <td className="mono">{l.lotNumber}</td>
                          <td>{l.auctionName}</td>
                          <td className="amount">{money(l.winningAmount)}</td>
                          <td className="mono">{l.feePercentage}%</td>
                          <td className="amount">{money(l.lotFee)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {CLOSED_STATUSES.includes(invoice.status) ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>This invoice is closed</div>
                <div className="locked-note" style={{ marginTop: 0 }}>
                  No further action is needed — this invoice is marked {(statusLabels[invoice.status] || invoice.status).toLowerCase()}.
                </div>
              </div>
            ) : submitResult?.success ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div className="login-success" style={{ display: "inline-block" }}>
                  {submitResult.message || "Receipt received. It will be reviewed shortly."}
                </div>
              </div>
            ) : (
              <div className="card">
                <h3 style={{ margin: "0 0 4px" }}>Upload your payment receipt</h3>
                <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 16 }}>
                  Attach a photo or PDF of your bank slip or transfer confirmation, and enter the payment details below.
                </div>
                <form onSubmit={handleSubmitReceipt}>
                  <div className="upload-form">
                    <div className="full">
                      <label>Receipt file <span className="req">*</span></label>
                      <div
                        className="filedrop"
                        onClick={() => document.getElementById("public-receipt-input")?.click()}
                        style={{ cursor: "pointer" }}
                      >
                        {receiptFile ? receiptFile.name : "Click to choose a file — image or PDF"}
                        <input
                          id="public-receipt-input"
                          type="file"
                          accept="image/*,.pdf"
                          onChange={(e) => setReceiptFile(e.target.files?.[0] || null)}
                          style={{ display: "none" }}
                        />
                      </div>
                    </div>
                    <div>
                      <label>Amount paid <span className="req">*</span></label>
                      <input
                        type="number"
                        step="0.01"
                        min="0"
                        value={amountPaid}
                        onChange={(e) => setAmountPaid(e.target.value)}
                        placeholder="e.g. 22400.00"
                      />
                    </div>
                    <div>
                      <label>Payment method <span className="req">*</span></label>
                      <select value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
                        {PAYMENT_METHODS.map((m) => <option key={m.v} value={m.v}>{m.l}</option>)}
                      </select>
                    </div>
                    <div>
                      <label>Payment date <span className="req">*</span></label>
                      <input type="date" value={paymentDate} onChange={(e) => setPaymentDate(e.target.value)} />
                    </div>
                  </div>

                  {submitError && <div style={{ color: "var(--red)", marginTop: 10, fontSize: 12.5 }}>{submitError}</div>}

                  <div style={{ marginTop: 16 }}>
                    <button type="submit" className="btn btn-brass" disabled={submitting}>
                      {submitting ? "Submitting…" : "Submit receipt"}
                    </button>
                  </div>
                </form>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}