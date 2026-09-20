import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall, API_BASE } from "../api";
import logo from "../logo";

const CLOSED_STATUSES = ["paid", "cancelled", "waived"];

// TODO: have a native Amharic speaker review these before shipping to real bidders.
const STATUS_LABELS_AM = {
  invoice_generated: "ደረሰኝ ተዘጋጅቷል",
  pending_payment: "ክፍያ በመጠባበቅ ላይ",
  payment_submitted: "ደረሰኝ ገብቷል",
  under_verification: "በማረጋገጥ ላይ",
  paid: "ተከፍሏል",
  overdue: "ጊዜው አልፏል",
  cancelled: "ተሰርዟል",
  waived: "ነፃ ተደርጓል",
};

const MAX_RECEIPT_FILE_SIZE = 10 * 1024 * 1024; // mirrors public_views.py MAX_RECEIPT_FILE_SIZE

function isLikelyPdf(file) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

export default function PublicInvoice({ token }) {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");

  const [receiptFile, setReceiptFile] = useState(null);
  const [fileError, setFileError] = useState("");
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
        setLoadError(
          res.status === 404
            ? "ደረሰኝ አልተገኘም። እባክዎ አገናኙን ያረጋግጡ።"
            : "ደረሰኙን መጫን አልተቻለም።"
        );
        return;
      }
      const data = await res.json();
      setInvoice(data);
    } catch (err) {
      setLoadError("ደረሰኙን በመጫን ላይ የአውታረ መረብ ስህተት ተከስቷል።");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function validateFile(file) {
    if (file.size > MAX_RECEIPT_FILE_SIZE) {
      return "ፋይሉ በጣም ትልቅ ነው፣ እባክዎ ከ10MB ያነሰ ፋይል ይስቀሉ";
    }
    const isPdf = isLikelyPdf(file);
    const isImage = file.type.startsWith("image/");
    if (!isPdf && !isImage) {
      return "ፋይሉ ትክክለኛ አይደለም፣ እባክዎ ትክክለኛ PDF ወይም ግልጽ ፎቶ ይስቀሉ";
    }
    return "";
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0] || null;
    setFileError("");
    if (!file) {
      setReceiptFile(null);
      return;
    }
    const err = validateFile(file);
    if (err) {
      setFileError(err);
      setReceiptFile(null);
      e.target.value = "";
      return;
    }
    setReceiptFile(file);
  }

  async function handleSubmitReceipt(e) {
    e.preventDefault();
    setSubmitError("");
    setSubmitResult(null);

    if (!receiptFile) {
      setSubmitError("እባክዎ የክፍያ ደረሰኝ ፋይል ያያይዙ።");
      return;
    }

    setSubmitting(true);
    const formData = new FormData();
    formData.append("receiptFile", receiptFile);
    // amountPaid / paymentMethod / paymentDate are deliberately NOT sent —
    // the backend defaults these server-side (see public_views.py).

    try {
      const res = await apiCall(`/api/public/invoice/${token}/receipt/`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (!res.ok) {
        setSubmitError(data.error || data.detail || "ደረሰኙን መላክ አልተቻለም።");
        return;
      }
      setSubmitResult(data);
      await fetchInvoice();
    } catch (err) {
      setSubmitError("ደረሰኙን በመላክ ላይ የአውታረ መረብ ስህተት ተከስቷል።");
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  const pdfUrl = `${API_BASE}/api/public/invoice/${token}/pdf/`;

  return (
    <div style={{ minHeight: "100vh", background: "var(--paper)", display: "flex", justifyContent: "center", padding: "24px 12px" }}>
      <div style={{ width: "100%", maxWidth: 560 }}>
        <div style={{ display: "flex", justifyContent: "center", marginBottom: 20 }}>
          <img src={logo} alt="Auction Ethiopia S.C." style={{ height: 44, width: "auto" }} />
        </div>

        {loading && (
          <div className="card" style={{ textAlign: "center", padding: 28 }}>ደረሰኙን በመጫን ላይ…</div>
        )}

        {!loading && loadError && (
          <div className="card" style={{ textAlign: "center", padding: 28, color: "var(--red)" }}>{loadError}</div>
        )}

        {!loading && !loadError && invoice && (
          <>
            <div className="card" style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 18 }}>{invoice.invoiceNumber}</h2>
                  <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 2 }}>
                    {invoice.bidderName}{invoice.companyName ? ` · ${invoice.companyName}` : ""}
                  </div>
                </div>
                <span className={`stamp ${invoice.status}`}>
                  {STATUS_LABELS_AM[invoice.status] || invoice.status}
                </span>
              </div>

              <div className="field-grid" style={{ marginBottom: 2 }}>
                <div className="field"><div className="fl">የደረሰኝ ቀን</div><div className="fv mono">{invoice.invoiceDate}</div></div>
                <div className="field"><div className="fl">የመክፈያ ቀነ ገደብ</div><div className="fv mono">{invoice.dueDate}</div></div>
                <div className="field"><div className="fl">ጠቅላላ መጠን</div><div className="fv mono">{money(invoice.totalAmount)}</div></div>
              </div>

              <div className="section-label">ሎቶች ({invoice.lots?.length || 0})</div>
              <div className="tbl-wrap" style={{ marginBottom: 12 }}>
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead><tr><th>ሎት #</th><th>ጨረታ</th><th>ያሸነፉት መጠን</th><th>ክፍያ %</th><th>የክፍያ መጠን</th></tr></thead>
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

              <a href={pdfUrl} target="_blank" rel="noopener noreferrer" className="btn btn-brass" style={{ display: "inline-block", textDecoration: "none", textAlign: "center", width: "100%" }}>
                ደረሰኝ (PDF) ይመልከቱ
              </a>
            </div>

            {CLOSED_STATUSES.includes(invoice.status) ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>ይህ ደረሰኝ ተዘግቷል</div>
                <div className="locked-note" style={{ marginTop: 0 }}>
                  ተጨማሪ እርምጃ አያስፈልግም — ደረሰኙ {STATUS_LABELS_AM[invoice.status] || invoice.status} ተብሎ ተመዝግቧል።
                </div>
              </div>
            ) : submitResult?.success ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div className="login-success" style={{ display: "inline-block" }}>
                  {submitResult.message || "ደረሰኙ ደርሶናል። በቅርቡ ይታያል።"}
                </div>
              </div>
            ) : (
              <div className="card">
                <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>የክፍያ ደረሰኝዎን ይስቀሉ</h3>
                <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 14 }}>
                  የባንክ ደረሰኝ ወይም የገንዘብ ማስተላለፊያ ማረጋገጫ ፎቶ ወይም PDF ያያይዙ።
                </div>
                <form onSubmit={handleSubmitReceipt}>
                  <div
                    className="filedrop"
                    onClick={() => document.getElementById("public-receipt-input")?.click()}
                    style={{ cursor: "pointer", marginBottom: 10 }}
                  >
                    {receiptFile ? receiptFile.name : "ፋይል ለመምረጥ እዚህ ይጫኑ — ፎቶ ወይም PDF"}
                    <input
                      id="public-receipt-input"
                      type="file"
                      accept="image/*,application/pdf"
                      onChange={handleFileChange}
                      style={{ display: "none" }}
                    />
                  </div>

                  {fileError && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 12.5 }}>{fileError}</div>}
                  {submitError && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 12.5 }}>{submitError}</div>}

                  <button type="submit" className="btn btn-brass" style={{ width: "100%" }} disabled={submitting || !receiptFile}>
                    {submitting ? "በመላክ ላይ…" : "ደረሰኝ ላክ"}
                  </button>
                </form>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}