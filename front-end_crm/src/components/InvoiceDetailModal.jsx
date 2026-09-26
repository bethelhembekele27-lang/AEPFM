import { useState, useEffect } from "react";
import { LOCKED_STATUSES, PDF_ROLES, money } from "../data";
import { apiCall, API_BASE } from "../api";
import Stamp from "./Stamp";
import GeneratePdfModal from "./GeneratePdfModal";

const AiSparkle = () => (<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M8.4 15.6l-2.1 2.1" /></svg>);

function AiBadge({ payment, onOpen }) {
  return (
    <span
      title="Click to view AI-extracted data"
      onClick={() => onOpen(payment)}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 18, height: 18, borderRadius: "50%", marginLeft: 6,
        background: "var(--blue-bg)", color: "var(--blue)", fontSize: 10, fontWeight: 700,
        cursor: "pointer", verticalAlign: "middle",
      }}
    >
      AI
    </span>
  );
}

function ExtractionPopover({ extraction, amountPaid, onClose }) {
  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 420 }}>
        <div className="modal-head">
          <h3 style={{ margin: 0, fontSize: 15 }}>AI-extracted data</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field-grid" style={{ marginBottom: 0, gap: "10px 20px" }}>
            <div className="field"><div className="fl">TIN</div><div className="fv mono">{extraction.tin || "—"}</div></div>
            <div className="field"><div className="fl">Receipt #</div><div className="fv mono">{extraction.receiptNumber || "—"}</div></div>
            <div className="field"><div className="fl">Date on receipt</div><div className="fv">{extraction.extractedDate || "—"}</div></div>
            <div className="field"><div className="fl">Customer name</div><div className="fv">{extraction.customerName || "—"}</div></div>
            <div className="field"><div className="fl">Total amount</div><div className="fv amount">{extraction.totalAmount ?? "—"}</div></div>
            <div className="field"><div className="fl">VAT amount</div><div className="fv amount">{extraction.vatAmount ?? "—"}</div></div>
            <div className="field" style={{ gridColumn: "1 / -1" }}><div className="fl">Description</div><div className="fv">{extraction.description || "—"}</div></div>
          </div>
          {extraction.totalAmount && Number(extraction.totalAmount) !== Number(amountPaid) && (
            <div style={{ background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 14, fontSize: 12.5 }}>
              Extracted total ({extraction.totalAmount}) doesn't match the recorded payment ({amountPaid}). Informational only.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const DOC_TYPES = [
  { v: "bank_slip", l: "Bank Slip" },
  { v: "transfer_proof", l: "Transfer Proof" },
  { v: "cpo", l: "CPO Document" },
  { v: "invoice", l: "Invoice Document" },
  { v: "payment_confirmation", l: "Payment Confirmation" },
  { v: "supporting_document", l: "Supporting Document" },
  { v: "other", l: "Other" },
];

function fileUrl(path) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}

export default function InvoiceDetailModal({ invoiceId, role, token, privileges, onClose }) {
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showGenerate, setShowGenerate] = useState(false);
  const [extractionPopover, setExtractionPopover] = useState(null);

  const [attachments, setAttachments] = useState([]);
  const [docType, setDocType] = useState("other");
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);

  const [editing, setEditing] = useState(false);
  const [editName, setEditName] = useState("");
  const [editCompany, setEditCompany] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editRemarks, setEditRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState("");

  const canUpload = role === "administrator" || role === "auction_manager"; // upload_payment_proof — no catalog key yet
  const canDelete = role === "administrator"; // delete_records — no catalog key yet
  const canEdit = (privileges || []).includes("edit_invoice");

  useEffect(() => {
    if (invoiceId) fetchInvoice();
  }, [invoiceId]);

  async function fetchInvoice() {
    setLoading(true);
    setError("");
    try {
      const res = await apiCall(`/api/invoices/${invoiceId}/`, {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (!res.ok) { setError("Failed to load invoice"); return; }
      const data = await res.json();
      setInvoice(data);
      setEditName(data.bidderName);
      setEditCompany(data.companyName || "");
      setEditPhone(data.winnerPhone || "");
      setEditRemarks(data.remarks || "");
      fetchAttachments();
    } catch (err) {
      setError("Network error loading invoice");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function fetchAttachments() {
    try {
      const res = await apiCall(`/api/invoices/${invoiceId}/attachments/`, {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (res.ok) setAttachments(await res.json());
    } catch (err) {
      console.error("Failed to load attachments", err);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    const formData = new FormData();
    formData.append("filePath", file);
    formData.append("fileName", file.name);
    formData.append("fileExtension", file.name.includes(".") ? file.name.split(".").pop() : "");
    formData.append("fileSize", (file.size / 1024).toFixed(2));
    formData.append("documentType", docType);
    try {
      const res = await apiCall(`/api/invoices/${invoiceId}/attachments/`, {
        method: "POST",
        headers: token ? { Authorization: `Token ${token}` } : {},
        body: formData,
      });
      if (!res.ok) { window.alert("Upload failed."); return; }
      setFile(null);
      await fetchAttachments();
    } catch (err) {
      window.alert("Network error uploading file.");
      console.error(err);
    } finally {
      setUploading(false);
    }
  }

  async function handleDeleteAttachment(id) {
    if (!window.confirm("Delete this attachment permanently?")) return;
    try {
      const res = await apiCall(`/api/attachments/${id}/`, {
        method: "DELETE",
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (res.ok) await fetchAttachments();
      else window.alert("Failed to delete attachment.");
    } catch (err) {
      window.alert("Network error deleting attachment.");
      console.error(err);
    }
  }

  async function handleDeletePayment(id) {
    if (!window.confirm("Delete this payment record permanently?")) return;
    try {
      const res = await apiCall(`/api/payments/${id}/`, { method: "DELETE", headers: token ? { Authorization: `Token ${token}` } : {} });
      if (res.ok) await fetchInvoice();
      else window.alert("Failed to delete payment.");
    } catch (err) {
      window.alert("Network error deleting payment.");
      console.error(err);
    }
  }

  async function handleSaveEdit() {
    setEditError("");
    setSaving(true);
    try {
      const winnerRes = await apiCall(`/api/winners/${invoice.winner.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ bidderName: editName, companyName: editCompany, winnerPhone: editPhone }),
      });
      if (!winnerRes.ok) { setEditError("Failed to save bidder info."); return; }

      const invRes = await apiCall(`/api/invoices/${invoiceId}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ remarks: editRemarks }),
      });
      if (!invRes.ok) { setEditError("Failed to save remarks."); return; }

      setEditing(false);
      await fetchInvoice();
    } catch (err) {
      setEditError("Network error saving changes.");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  async function handleGeneratePdf(formData) {
    const invId = invoiceId;
    const pct = formData.percentagesByInvId[invId];
    const amhName = formData.amhNames[invId] || "";
    try {
      const res = await fetch(`${API_BASE}/api/invoices/${invId}/generate-pdf/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
        body: JSON.stringify({
          feePercentage: parseFloat(pct),
          auctionRefNumber: formData.auctionRefNumber || "",
          bidderNameAmharic: amhName,
          amountInWords: (formData.amountWordsByInv || {})[invId] || "",
          feeInWords: (formData.feeWordsByInv || {})[invId] || "",
          officeAddress: formData.officeAddress || "",
          totalAmount: (formData.totalAmountByInv || {})[invId] || "",
          feeAmount: (formData.feeAmountByInv || {})[invId] || "",
          bankAccount: (formData.bankAccountByInv || {})[invId] || "",
          paragraph1: (formData.paragraph1ByInv || {})[invId] || "",
          paragraph2: (formData.paragraph2ByInv || {})[invId] || "",
        }),
      });
      if (!res.ok) { window.alert("PDF generation failed."); return; }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `Invoice_${invoice.invoiceNumber}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      await fetchInvoice();
    } catch (err) {
      window.alert("Network error generating PDF.");
      console.error(err);
    }
  }

  if (!invoiceId) return null;
  if (loading) return (
    <div className="overlay active"><div className="modal" style={{ padding: 40, textAlign: "center" }}>Loading...</div></div>
  );
  if (error || !invoice) return (
    <div className="overlay active" onClick={onClose}>
      <div className="modal" style={{ padding: 40, textAlign: "center", color: "var(--red)" }}>{error || "Not found"}</div>
    </div>
  );

  const locked = LOCKED_STATUSES.includes(invoice.status);
  const canGeneratePdf = PDF_ROLES.includes(role) && !locked;

  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-head">
          <div>
            <h2 style={{ margin: 0 }}>{invoice.invoiceNumber}</h2>
            <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 2 }}>
              {invoice.lots.length} lot(s){invoice.importBatch ? ` · Batch #${invoice.importBatch}` : ""}
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: 16, display: "flex", gap: 8, alignItems: "center" }}>
            <Stamp status={invoice.status} />
            {locked && <span className="badge-note">Locked — no edits except admin override</span>}
          </div>

          {editing ? (
            <div className="card" style={{ background: "var(--paper)", marginBottom: 16 }}>
              <div className="section-label" style={{ marginTop: 0 }}>Edit bidder info & remarks</div>
              <div className="field-grid">
                <div className="field"><div className="fl">Bidder name</div><input value={editName} onChange={(e) => setEditName(e.target.value)} /></div>
                <div className="field"><div className="fl">Company</div><input value={editCompany} onChange={(e) => setEditCompany(e.target.value)} /></div>
                <div className="field"><div className="fl">Phone</div><input value={editPhone} onChange={(e) => setEditPhone(e.target.value)} /></div>
              </div>
              <div className="field" style={{ marginBottom: 14 }}>
                <div className="fl">Remarks</div>
                <textarea value={editRemarks} onChange={(e) => setEditRemarks(e.target.value)} rows={3} style={{ width: "100%", fontFamily: "'Inter'", fontSize: 14, padding: 10, border: "1px solid var(--border)", borderRadius: 6 }} />
              </div>
              {editError && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{editError}</div>}
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-brass" onClick={handleSaveEdit} disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
                <button className="btn btn-ghost" onClick={() => setEditing(false)} disabled={saving}>Cancel</button>
              </div>
            </div>
          ) : (
            <div className="field-grid">
              <div className="field"><div className="fl">Bidder</div><div className="fv">{invoice.bidderName}</div></div>
              <div className="field"><div className="fl">Company</div><div className="fv">{invoice.companyName || <span style={{ color: "var(--text-3)" }}>Not set</span>}</div></div>
              <div className="field"><div className="fl">Phone</div><div className="fv mono">{invoice.winnerPhone}</div></div>
              <div className="field"><div className="fl">Fee percentage</div><div className="fv mono">{invoice.feePercentage}%</div></div>
              <div className="field"><div className="fl">Invoice date</div><div className="fv mono">{invoice.invoiceDate}</div></div>
              <div className="field"><div className="fl">Due date</div><div className="fv mono">{invoice.dueDate}</div></div>
              <div className="field"><div className="fl">Fee amount</div><div className="fv mono">{money(invoice.totalAmount)}</div></div>
              <div className="field"><div className="fl">Verified by</div><div className="fv">{invoice.verifiedBy || "—"}</div></div>
            </div>
          )}

          {canEdit && !editing && (
            <button className="btn btn-sm" style={{ marginBottom: 16 }} onClick={() => setEditing(true)}>Edit invoice</button>
          )}

          <div className="section-label">Lots ({invoice.lots.length})</div>
          <div className="tbl-wrap" style={{ marginBottom: 16 }}>
            <table>
              <thead><tr><th>Lot #</th><th>Auction</th><th>Winning amount</th><th>Fee %</th><th>Lot fee</th></tr></thead>
              <tbody>
                {invoice.lots.map((l) => (
                  <tr key={l.id}>
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

          {invoice.payments && invoice.payments.length > 0 && (
            <>
              <div className="section-label">Payments &amp; receipts</div>
              <div className="tbl-wrap" style={{ marginBottom: 16 }}>
                <table>
                  <thead>
                    <tr><th>Amount</th><th>Date</th><th>Status</th><th></th></tr>
                  </thead>
                  <tbody>
                    {invoice.payments.map((p) => (
                      <tr key={p.id}>
                        <td className="amount">{money(p.amountPaid)}</td>
                        <td className="mono">{p.paymentDate}</td>
                        <td>
                          {p.verificationStatus === "manager_approved" && <span className="stamp paid">Approved{p.extraction !== undefined && p.extraction !== null && <AiBadge payment={p} onOpen={setExtractionPopover} />}</span>}
                          {p.verificationStatus === "manager_rejected" && <span className="stamp cancelled">Rejected</span>}
                          {p.verificationStatus === "pending_manager_review" && <span className="stamp pending_payment">Pending review</span>}
                          {(!p.verificationStatus || p.verificationStatus === "not_applicable") && (
                            <span className="stamp invoice_generated">{p.paymentStatus}</span>
                          )}
                        </td>
                        <td style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                          {p.receiptUrl && (
                            <a href={fileUrl(p.receiptUrl)} target="_blank" rel="noopener noreferrer" className="btn btn-sm btn-icon-only" title="View receipt">
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                <circle cx="12" cy="12" r="3" />
                              </svg>
                            </a>
                          )}
                          {canDelete && (
                            <button className="btn btn-sm btn-icon-only btn-danger" title="Delete payment" onClick={() => handleDeletePayment(p.id)}>
                              <svg viewBox="0 0 24 24" fill="currentColor" style={{ width: 16, height: 16 }}><path d="M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM9 16h2v-7H9v7zm4 0h2v-7h-2v7z" /></svg>
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <div className="section-label">Attachments</div>
          <div className="attach-list" style={{ marginBottom: 12 }}>
            {attachments.length === 0 && <div className="locked-note" style={{ marginTop: 0 }}>No attachments yet.</div>}
            {attachments.map((a) => (
              <div key={a.id} className="attach-item" style={{ justifyContent: "space-between" }}>
                <a href={fileUrl(a.filePath)} target="_blank" rel="noopener noreferrer" style={{ color: "var(--brass-dark)" }}>
                  {a.fileName} <span style={{ color: "var(--text-3)", fontWeight: 400 }}>({a.documentType})</span>
                </a>
                {canDelete && <button className="btn btn-sm btn-danger" onClick={() => handleDeleteAttachment(a.id)}>Delete</button>}
              </div>
            ))}
          </div>
          {canUpload && (
            <div className="card" style={{ background: "var(--paper)", marginBottom: 16, padding: 16 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                <select className="select-standalone" style={{ maxWidth: 190 }} value={docType} onChange={(e) => setDocType(e.target.value)}>
                  {DOC_TYPES.map((d) => <option key={d.v} value={d.v}>{d.l}</option>)}
                </select>
                <div
                  className="filedrop"
                  onClick={() => document.getElementById("staff-attach-input")?.click()}
                  style={{ cursor: "pointer", flex: 1, minWidth: 200, padding: "10px 14px" }}
                >
                  {file ? file.name : "Click to choose a file — any document type"}
                  <input id="staff-attach-input" type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} style={{ display: "none" }} />
                </div>
                <button className="btn btn-sm btn-brass" onClick={handleUpload} disabled={!file || uploading}>
                  {uploading ? "Uploading..." : "Upload"}
                </button>
              </div>
            </div>
          )}

          <div className="field" style={{ margin: "16px 0" }}>
            <div className="fl">Remarks</div>
            <div className="fv">{invoice.remarks || <span style={{ color: "var(--text-3)" }}>No remarks added</span>}</div>
          </div>

          <div className="modal-actions">
            {canGeneratePdf && <button className="btn btn-sm" onClick={() => setShowGenerate(true)}>Generate invoice PDF</button>}
          </div>
          {locked && (
            <div className="locked-note">
              Action buttons are hidden once an invoice is Paid, Cancelled, or Waived — only an Administrator override can change status.
            </div>
          )}
        </div>
      </div>
      {showGenerate && (
        <GeneratePdfModal
          invoices={[{ id: invoiceId, invoiceNumber: invoice.invoiceNumber, bidderName: invoice.bidderName, bidderNameAmharic: "", lots: invoice.lots }]}
          onConfirm={handleGeneratePdf}
          onClose={() => setShowGenerate(false)}
        />
      )}
      {extractionPopover && (
        <ExtractionPopover
          extraction={extractionPopover.extraction}
          amountPaid={extractionPopover.amountPaid}
          onClose={() => setExtractionPopover(null)}
        />
      )}
    </div>
  );
}
