import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall, API_BASE } from "../api";
import logo from "../logo";

const CLOSED_STATUSES = ["paid", "cancelled", "waived"];
const MAX_RECEIPT_FILE_SIZE = 10 * 1024 * 1024; // mirrors public_views.py MAX_RECEIPT_FILE_SIZE
const LANG_KEY = "publicInvoiceLang";

// TODO: have a native Amharic speaker review every "am" string before real bidders see this.
const STATUS_LABELS = {
  am: {
    invoice_generated: "ደረሰኝ ተዘጋጅቷል",
    pending_payment: "ክፍያ በመጠባበቅ ላይ",
    payment_submitted: "ደረሰኝ ገብቷል",
    under_verification: "በማረጋገጥ ላይ",
    paid: "ተከፍሏል",
    overdue: "ጊዜው አልፏል",
    cancelled: "ተሰርዟል",
    waived: "ነፃ ተደርጓል",
  },
  en: {
    invoice_generated: "Invoice issued",
    pending_payment: "Payment pending",
    payment_submitted: "Receipt submitted",
    under_verification: "Under review",
    paid: "Paid",
    overdue: "Overdue",
    cancelled: "Cancelled",
    waived: "Waived",
  },
};

const TEXT = {
  am: {
    loading: "ደረሰኙን በመጫን ላይ…",
    notFound: "ደረሰኝ አልተገኘም። እባክዎ አገናኙን ያረጋግጡ።",
    loadFailed: "ደረሰኙን መጫን አልተቻለም።",
    loadNetwork: "ደረሰኙን በመጫን ላይ የአውታረ መረብ ስህተት ተከስቷል።",
    invoiceDate: "የደረሰኝ ቀን",
    dueDate: "የመክፈያ ቀነ ገደብ",
    total: "ጠቅላላ መጠን",
    lots: "ሎቶች",
    colLot: "ሎት #",
    colAuction: "ጨረታ",
    colWon: "ያሸነፉት መጠን",
    colPct: "ክፍያ %",
    colFee: "የክፍያ መጠን",
    viewPdf: "ደረሰኝ (PDF) ይመልከቱ",
    closedTitle: "ይህ ደረሰኝ ተዘግቷል",
    closedNote: (status) => `ተጨማሪ እርምጃ አያስፈልግም — ደረሰኙ ${status} ተብሎ ተመዝግቧል።`,
    uploadTitle: "የክፍያ ደረሰኝዎን ይስቀሉ",
    uploadHelp: "የባንክ ደረሰኝ ወይም የገንዘብ ማስተላለፊያ ማረጋገጫ ፎቶ ወይም PDF ያያይዙ።",
    chooseFile: "ፋይል ለመምረጥ እዚህ ይጫኑ — ፎቶ ወይም PDF",
    send: "ደረሰኝ ላክ",
    sending: "በመላክ ላይ…",
    success: "ደረሰኝዎን ተቀብለናል። በቅርቡ ይገመገማል።",
    attachFirst: "እባክዎ የክፍያ ደረሰኝ ፋይል ያያይዙ።",
    sendFailed: "ደረሰኙን መላክ አልተቻለም።",
    sendNetwork: "ደረሰኙን በመላክ ላይ የአውታረ መረብ ስህተት ተከስቷል።",
    tooMany: "ብዙ ጊዜ ሞክረዋል፣ እባክዎ ከጥቂት ቆይታ በኋላ እንደገና ይሞክሩ።",
    fileTooLarge: "ፋይሉ በጣም ትልቅ ነው፣ እባክዎ ከ10MB ያነሰ ፋይል ይስቀሉ",
    fileNotValid: "ፋይሉ ትክክለኛ አይደለም፣ እባክዎ ትክክለኛ PDF ወይም ግልጽ ፎቶ ይስቀሉ",
    imageNotClear: "ምስሉ ግልጽ አይደለም፣ እባክዎ ግልጽ ፎቶ አንስተው እንደገና ይስቀሉ",
    invoiceClosed: "ይህ ደረሰኝ ተዘግቷል፣ አዲስ ደረሰኝ መቀበል አይቻልም።",
  },
  en: {
    loading: "Loading invoice…",
    notFound: "Invoice not found. Please check the link.",
    loadFailed: "Could not load the invoice.",
    loadNetwork: "A network error occurred while loading the invoice.",
    invoiceDate: "Invoice date",
    dueDate: "Payment due date",
    total: "Total amount",
    lots: "Lots",
    colLot: "Lot #",
    colAuction: "Auction",
    colWon: "Winning amount",
    colPct: "Fee %",
    colFee: "Fee amount",
    viewPdf: "View invoice (PDF)",
    closedTitle: "This invoice is closed",
    closedNote: (status) => `No further action is needed. The invoice is recorded as: ${status}.`,
    uploadTitle: "Upload your payment receipt",
    uploadHelp: "Attach a photo or PDF of your bank receipt or transfer confirmation.",
    chooseFile: "Tap here to choose a file - photo or PDF",
    send: "Send receipt",
    sending: "Sending…",
    success: "We received your receipt. It will be reviewed shortly.",
    attachFirst: "Please attach your payment receipt file.",
    sendFailed: "Could not send the receipt.",
    sendNetwork: "A network error occurred while sending the receipt.",
    tooMany: "Too many attempts. Please try again in a little while.",
    fileTooLarge: "The file is too large. Please upload a file smaller than 10MB.",
    fileNotValid: "This file is not valid. Please upload a valid PDF or a clear photo.",
    imageNotClear: "The image is not clear. Please take a clear photo and upload it again.",
    invoiceClosed: "This invoice is closed and cannot accept a new receipt.",
  },
};

// Backend error codes (public_views.py) -> keys in TEXT. Errors are stored as KEYS
// (not translated strings) so switching language re-translates a visible error.
const ERROR_KEYS = {
  file_too_large: "fileTooLarge",
  file_not_valid: "fileNotValid",
  image_not_clear: "imageNotClear",
  invoice_closed: "invoiceClosed",
  file_required: "attachFirst",
};

function isLikelyPdf(file) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

// Returns a TEXT key describing the problem, or "" if the file looks fine.
function validateFile(file) {
  if (file.size > MAX_RECEIPT_FILE_SIZE) return "fileTooLarge";
  if (!isLikelyPdf(file) && !file.type.startsWith("image/")) return "fileNotValid";
  return "";
}

function LangToggle({ lang, onChange }) {
  const isEn = lang === "en";
  const seg = { flex: 1, textAlign: "center", zIndex: 1, fontSize: 12.5, fontWeight: 600, lineHeight: "30px", transition: "color .2s" };
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isEn}
      aria-label="Language / ቋንቋ"
      onClick={() => onChange(isEn ? "am" : "en")}
      style={{
        position: "relative", display: "flex", width: 92, height: 32, padding: 0,
        border: "1px solid var(--border)", borderRadius: 16, background: "var(--panel)",
        cursor: "pointer", overflow: "hidden", flexShrink: 0,
      }}
    >
      <span
        style={{
          position: "absolute", top: 0, bottom: 0, left: 0, width: "50%",
          borderRadius: 15, background: "var(--brass)",
          transform: isEn ? "translateX(0)" : "translateX(100%)",
          transition: "transform .2s",
        }}
      />
      <span style={{ ...seg, color: isEn ? "#fff" : "var(--text-2)" }}>EN</span>
      <span style={{ ...seg, color: isEn ? "var(--text-2)" : "#fff" }}>አማ</span>
    </button>
  );
}

export default function PublicInvoice({ token }) {
  const [lang, setLang] = useState(() => {
    try {
      return localStorage.getItem(LANG_KEY) === "en" ? "en" : "am";
    } catch {
      return "am";
    }
  });
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadErrorKey, setLoadErrorKey] = useState("");

  const [receiptFile, setReceiptFile] = useState(null);
  const [fileErrorKey, setFileErrorKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitErrorKey, setSubmitErrorKey] = useState("");

  const t = TEXT[lang];
  const statusLabels = STATUS_LABELS[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
    try {
      localStorage.setItem(LANG_KEY, lang);
    } catch {
      // storage unavailable (e.g. private mode): the choice just isn't remembered
    }
  }, [lang]);

  useEffect(() => {
    fetchInvoice();
  }, [token]);

  // silent = refresh in the background (after an upload) without the loading card
  // and without replacing the page with an error if the refresh fails.
  async function fetchInvoice(silent = false) {
    if (!silent) {
      setLoading(true);
      setLoadErrorKey("");
    }
    try {
      const res = await apiCall(`/api/public/invoice/${token}/`, { method: "GET" });
      if (!res.ok) {
        if (!silent) setLoadErrorKey(res.status === 404 ? "notFound" : "loadFailed");
        return;
      }
      setInvoice(await res.json());
    } catch (err) {
      if (!silent) setLoadErrorKey("loadNetwork");
      console.error(err);
    } finally {
      if (!silent) setLoading(false);
    }
  }

  function handleFileChange(e) {
    const file = e.target.files?.[0] || null;
    setFileErrorKey("");
    setSubmitErrorKey("");
    if (!file) {
      setReceiptFile(null);
      return;
    }
    const errKey = validateFile(file);
    if (errKey) {
      setFileErrorKey(errKey);
      setReceiptFile(null);
      e.target.value = "";
      return;
    }
    setReceiptFile(file);
  }

  async function handleSubmitReceipt(e) {
    e.preventDefault();
    setSubmitErrorKey("");

    if (!receiptFile) {
      setSubmitErrorKey("attachFirst");
      return;
    }

    setSubmitting(true);
    const formData = new FormData();
    formData.append("receiptFile", receiptFile);
    // amountPaid / paymentMethod / paymentDate are deliberately NOT sent -
    // the backend defaults these server-side (see public_views.py).

    try {
      const res = await apiCall(`/api/public/invoice/${token}/receipt/`, {
        method: "POST",
        body: formData,
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        // non-JSON error body (e.g. proxy error page): fall through to generic message
      }
      if (!res.ok) {
        if (res.status === 429) setSubmitErrorKey("tooMany");
        else setSubmitErrorKey(ERROR_KEYS[data.code] || "sendFailed");
        return;
      }
      setSubmitted(true);
      await fetchInvoice(true);
    } catch (err) {
      setSubmitErrorKey("sendNetwork");
      console.error(err);
    } finally {
      setSubmitting(false);
    }
  }

  const pdfUrl = `${API_BASE}/api/public/invoice/${token}/pdf/`;

  return (
    <div style={{ minHeight: "100vh", background: "var(--paper)", display: "flex", justifyContent: "center", padding: "24px 12px" }}>
      <div style={{ width: "100%", maxWidth: 560 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 20 }}>
          <img src={logo} alt="Auction Ethiopia S.C." style={{ height: 44, width: "auto", maxWidth: "55%" }} />
          <LangToggle lang={lang} onChange={setLang} />
        </div>

        {loading && (
          <div className="card" style={{ textAlign: "center", padding: 28 }}>{t.loading}</div>
        )}

        {!loading && loadErrorKey && (
          <div className="card" style={{ textAlign: "center", padding: 28, color: "var(--red)" }}>{t[loadErrorKey]}</div>
        )}

        {!loading && !loadErrorKey && invoice && (
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
                  {statusLabels[invoice.status] || invoice.status}
                </span>
              </div>

              <div className="field-grid" style={{ marginBottom: 2 }}>
                <div className="field"><div className="fl">{t.invoiceDate}</div><div className="fv mono">{invoice.invoiceDate}</div></div>
                <div className="field"><div className="fl">{t.dueDate}</div><div className="fv mono">{invoice.dueDate}</div></div>
                <div className="field"><div className="fl">{t.total}</div><div className="fv mono">{money(invoice.totalAmount)}</div></div>
              </div>

              <div className="section-label">{t.lots} ({invoice.lots?.length || 0})</div>
              <div className="tbl-wrap" style={{ marginBottom: 12 }}>
                <div style={{ overflowX: "auto" }}>
                  <table>
                    <thead>
                      <tr>
                        <th>{t.colLot}</th>
                        <th>{t.colAuction}</th>
                        <th>{t.colWon}</th>
                        <th>{t.colPct}</th>
                        <th>{t.colFee}</th>
                      </tr>
                    </thead>
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

              <a
                href={pdfUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn-brass"
                style={{ display: "inline-block", textDecoration: "none", textAlign: "center", width: "100%" }}
              >
                {t.viewPdf}
              </a>
            </div>

            {CLOSED_STATUSES.includes(invoice.status) ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 6 }}>{t.closedTitle}</div>
                <div className="locked-note" style={{ marginTop: 0 }}>
                  {t.closedNote(statusLabels[invoice.status] || invoice.status)}
                </div>
              </div>
            ) : submitted ? (
              <div className="card" style={{ textAlign: "center" }}>
                <div className="login-success" style={{ display: "inline-block" }}>{t.success}</div>
              </div>
            ) : (
              <div className="card">
                <h3 style={{ margin: "0 0 4px", fontSize: 15 }}>{t.uploadTitle}</h3>
                <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 14 }}>{t.uploadHelp}</div>
                <form onSubmit={handleSubmitReceipt}>
                  <div
                    className="filedrop"
                    onClick={() => document.getElementById("public-receipt-input")?.click()}
                    style={{ cursor: "pointer", marginBottom: 10 }}
                  >
                    {receiptFile ? receiptFile.name : t.chooseFile}
                    <input
                      id="public-receipt-input"
                      type="file"
                      accept="image/*,application/pdf"
                      onChange={handleFileChange}
                      style={{ display: "none" }}
                    />
                  </div>

                  {fileErrorKey && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 12.5 }}>{t[fileErrorKey]}</div>}
                  {submitErrorKey && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 12.5 }}>{t[submitErrorKey]}</div>}

                  <button type="submit" className="btn btn-brass" style={{ width: "100%" }} disabled={submitting || !receiptFile}>
                    {submitting ? t.sending : t.send}
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