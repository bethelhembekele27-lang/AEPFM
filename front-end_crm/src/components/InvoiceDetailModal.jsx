import { useState } from "react";
import { LOCKED_STATUSES, PDF_ROLES, actionDefsFor, batchLabel, money } from "../data";
import Stamp from "./Stamp";
import { ActionBtn } from "./ActionButton";
import GeneratePdfModal from "./GeneratePdfModal";

const FIELD_SOURCE_DEFS = [
  { key: "lotNumber", label: "Lot Number" },
  { key: "auctionName", label: "Auction" },
  { key: "winningAmount", label: "Amount" },
  { key: "bidderName", label: "Bidder Name" },
  { key: "winnerPhone", label: "Phone" },
  { key: "status", label: "Status" },
  { key: "companyName", label: "Company / Legal Name" },
  { key: "initialPrice", label: "Initial Price" },
  { key: "cpoAmount", label: "CPO Amount" },
  { key: "cpoBank", label: "CPO Bank" },
  { key: "submittedAt", label: "Submitted / Received Date" },
];

export default function InvoiceDetailModal({ invoice, role, onClose, onGeneratePdf }) {
  const [showGenerate, setShowGenerate] = useState(false);
  if (!invoice) return null;
  const locked = LOCKED_STATUSES.includes(invoice.status);
  const canGeneratePdf = PDF_ROLES.includes(role) && !LOCKED_STATUSES.includes(invoice.status);
  const otherActions = actionDefsFor(invoice).filter((b) => b.label !== "Generate invoice PDF");

  const extraDataRows = (invoice.lots || []).flatMap((l) =>
    Object.entries(l.extraFields || {}).map(([key, value]) => ({
      lotNumber: l.lotNumber,
      key,
      value,
    }))
  );

  const columnMapping = invoice.columnMapping;

  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal">
        <div className="modal-head">
          <div>
            <h2 style={{ margin: 0 }}>{invoice.inv}</h2>
            <div style={{ color: "var(--text-2)", fontSize: 13, marginTop: 2 }}>
              {batchLabel(invoice.batchId)} \u00b7 {invoice.lots.length} lot(s)
            </div>
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: 16 }}>
            <Stamp status={invoice.status} />
            {locked && <span className="badge-note">Locked \u2014 no edits except admin override</span>}
          </div>
          <div className="field-grid">
            <div className="field"><div className="fl">Bidder</div><div className="fv">{invoice.bidderName}</div></div>
            <div className="field"><div className="fl">Company</div><div className="fv">{invoice.companyName || <span style={{ color: "var(--text-3)" }}>Not set \u2014 edit winner record to add</span>}</div></div>
            <div className="field"><div className="fl">Phone</div><div className="fv mono">{invoice.winnerPhone}</div></div>
            <div className="field"><div className="fl">Fee percentage</div><div className="fv mono">{invoice.feePercentage}%</div></div>
            <div className="field"><div className="fl">Invoice date</div><div className="fv mono">{invoice.invoiceDate}</div></div>
            <div className="field"><div className="fl">Due date</div><div className="fv mono">{invoice.dueDate}</div></div>
            <div className="field"><div className="fl">Total amount</div><div className="fv mono">{money(invoice.totalAmount)}</div></div>
            <div className="field"><div className="fl">Verified by</div><div className="fv">{invoice.verifiedBy}</div></div>
          </div>

          <div className="section-label">Lots ({invoice.lots.length})</div>
          <div className="tbl-wrap" style={{ marginBottom: 6 }}>
            <table>
              <thead><tr><th>Lot #</th><th>Auction</th><th>Winning amount</th><th>Fee %</th><th>Lot fee</th></tr></thead>
              <tbody>
                {invoice.lots.map((l) => (
                  <tr key={l.lotNumber}>
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

          {columnMapping && (
            <>
              <div className="section-label">Field sources</div>
              <div className="tbl-wrap" style={{ marginBottom: 6 }}>
                <table>
                  <thead><tr><th>Field</th><th>Source column in uploaded file</th></tr></thead>
                  <tbody>
                    {FIELD_SOURCE_DEFS.map((f) => {
                      const source = columnMapping[f.key];
                      return (
                        <tr key={f.key}>
                          <td>{f.label}</td>
                          <td className={source ? "mono" : ""} style={!source ? { color: "var(--text-3)", fontStyle: "italic" } : undefined}>
                            {source || "Not present in file"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <div className="locked-note" style={{ marginBottom: 14 }}>
                Shows which column in the originally uploaded spreadsheet supplied each field for this batch.
              </div>
            </>
          )}

          {extraDataRows.length > 0 && (
            <>
              <div className="section-label">Additional imported data</div>
              <div className="tbl-wrap" style={{ marginBottom: 6 }}>
                <table>
                  <thead><tr><th>Lot #</th><th>Field</th><th>Value</th></tr></thead>
                  <tbody>
                    {extraDataRows.map((row, i) => (
                      <tr key={`${row.lotNumber}-${row.key}-${i}`}>
                        <td className="mono">{row.lotNumber}</td>
                        <td>{row.key}</td>
                        <td>{String(row.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="locked-note" style={{ marginBottom: 14 }}>
                Columns from the original spreadsheet that don't map to a standard invoice field \u2014 kept for reference.
              </div>
            </>
          )}

          <div className="field" style={{ margin: "16px 0" }}>
            <div className="fl">Remarks</div>
            <div className="fv">{invoice.remarks || <span style={{ color: "var(--text-3)" }}>No remarks added</span>}</div>
          </div>

          <div className="section-label">Attachments</div>
          <div className="attach-list">
            <div className="attach-item"><span className="ic"></span> Invoice document \u2014 {invoice.inv}.pdf</div>
            {["paid", "under_verification", "payment_submitted"].includes(invoice.status) && (
              <div className="attach-item"><span className="ic"></span> Bank slip / transfer proof \u2014 receipt_{invoice.inv}.pdf</div>
            )}
          </div>

          <div className="modal-actions">
            {canGeneratePdf && (
              <button className="btn btn-sm" onClick={() => setShowGenerate(true)}>Generate invoice PDF</button>
            )}
            {otherActions.map((b, i) => (
              <ActionBtn key={i} label={b.label} roles={b.roles} role={role} />
            ))}
          </div>
          {locked && (
            <div className="locked-note">
              Action buttons are hidden once an invoice is Paid, Cancelled, or Waived \u2014 only an Administrator override can change status from here.
            </div>
          )}
        </div>
      </div>
      {showGenerate && (
        <GeneratePdfModal
          invoices={[invoice]}
          onConfirm={onGeneratePdf}
          onClose={() => setShowGenerate(false)}
        />
      )}
    </div>
  );
}