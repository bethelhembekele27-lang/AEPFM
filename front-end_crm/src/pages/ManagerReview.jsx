import { useState, useEffect } from "react";
import { money } from "../data";
import { apiCall, API_BASE } from "../api";

function fileUrl(path) {
  if (!path) return "";
  return path.startsWith("http") ? path : `${API_BASE}${path}`;
}
function initials(name) {
  return (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}
function formatWhen(iso) {
  if (!iso) return { date: "—", time: "" };
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" }),
    time: d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }),
  };
}
function isImageFile(url) {
  return /\.(jpe?g|png|gif|webp|heic)(\?|$)/i.test(url || "");
}

const EyeIcon = () => (<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>);
const TrashIcon = () => (<svg viewBox="0 0 24 24" fill="currentColor"><path d="M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM9 16h2v-7H9v7zm4 0h2v-7h-2v7z" /></svg>);
const CheckIcon = () => (<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6L9 17l-5-5" /></svg>);
const XIcon = () => (<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>);
const CloseIcon = () => (<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>);
const SearchIcon = () => (<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg>);

const TABS = [
  { key: "pending_manager_review", label: "Pending", sub: "Requires review", accent: "amber" },
  { key: "manager_approved", label: "Approved", sub: "Successfully verified", accent: "green" },
  { key: "manager_rejected", label: "Rejected", sub: "Payment not accepted", accent: "red" },
];
const EMPTY_COPY = {
  pending_manager_review: "No receipts waiting on review right now.",
  manager_approved: "No approved receipts yet.",
  manager_rejected: "No rejected receipts.",
};

export default function ManagerReview({ role, token }) {
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState([]);
  const [tab, setTab] = useState("pending_manager_review");
  const [search, setSearch] = useState("");
  const [drawerRow, setDrawerRow] = useState(null);
  const [reviewing, setReviewing] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);

  const canManage = role === "administrator" || role === "auction_manager";
  const canDelete = role === "administrator";

  useEffect(() => { if (canManage) { fetchRows(tab); fetchCounts(); } else setLoading(false); }, [tab]);

  async function fetchRows(status) {
    setLoading(true);
    setError("");
    try {
      const res = await apiCall(`/api/receipts/?verificationStatus=${status}`, { headers: token ? { Authorization: `Token ${token}` } : {} });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Failed to load receipts"); return; }
      setRows(data);
    } catch (err) {
      setError("Network error loading receipts");
      console.error(err);
    } finally { setLoading(false); }
  }

  async function fetchCounts() {
    try {
      const results = await Promise.all(TABS.map((t) =>
        apiCall(`/api/receipts/?verificationStatus=${t.key}`, { headers: token ? { Authorization: `Token ${token}` } : {} }).then((r) => r.json())
      ));
      const next = {};
      TABS.forEach((t, i) => { next[t.key] = results[i]?.length ?? 0; });
      setCounts(next);
    } catch (err) { console.error(err); }
  }

  function switchTab(t) { setTab(t); setSelected([]); setSearch(""); setDrawerRow(null); }
  function toggleRow(id) { setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]); }
  function toggleAll() { setSelected(selected.length === filteredRows.length ? [] : filteredRows.map((r) => r.id)); }
  function openReview(decision, ids) { if (!ids.length) return; setSelected(ids); setReviewing(decision); setNote(""); }

  async function submitReview() {
    if (reviewing === "reject" && !note.trim()) return;
    setSaving(true);
    try {
      for (const id of selected) {
        const res = await apiCall(`/api/receipts/${id}/review/`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
          body: JSON.stringify({ decision: reviewing, note }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          window.alert(`Failed on payment #${id}: ${data.error || "unknown error"}`);
        }
      }
      setReviewing(null); setSelected([]); setDrawerRow(null);
      await fetchRows(tab); await fetchCounts();
    } catch (err) {
      window.alert("Network error submitting review");
      console.error(err);
    } finally { setSaving(false); }
  }

  async function handleDelete(ids) {
    if (!ids.length) return;
    if (!window.confirm(`Permanently delete ${ids.length} receipt record(s)? This cannot be undone.`)) return;
    try {
      for (const id of ids) {
        await apiCall(`/api/payments/${id}/`, { method: "DELETE", headers: token ? { Authorization: `Token ${token}` } : {} });
      }
      setSelected([]); setDrawerRow(null);
      await fetchRows(tab); await fetchCounts();
    } catch (err) {
      window.alert("Failed to delete one or more records");
      console.error(err);
    }
  }

  async function extractReceipt(paymentId) {
    setExtracting(true);
    try {
      const res = await apiCall(`/api/receipts/${paymentId}/extract/`, {
        method: "POST",
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) { window.alert(data.error || "Extraction failed"); return; }
      setDrawerRow((r) => ({ ...r, extraction: data }));
      setRows((prev) => prev.map((r) => (r.id === paymentId ? { ...r, extraction: data } : r)));
    } catch (err) {
      window.alert("Network error during extraction");
      console.error(err);
    } finally {
      setExtracting(false);
    }
  }

  if (!canManage) {
    return <div className="card"><h3 style={{ margin: "0 0 6px" }}>Receipt verification</h3><div className="locked-note">Only Administrators and Auction Managers can review bidder-submitted receipts.</div></div>;
  }

  const filteredRows = search.trim()
    ? rows.filter((r) => `${r.bidderName} ${r.invoiceNumber} ${r.winnerPhone}`.toLowerCase().includes(search.toLowerCase()))
    : rows;
  const reviewRows = rows.filter((r) => selected.includes(r.id));

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 22, flexWrap: "wrap", gap: 8 }}>
        <div>
          <h2 style={{ margin: "0 0 4px", fontSize: 21 }}>Receipt verification</h2>
          <div style={{ fontSize: 13, color: "var(--text-2)" }}>Review submitted payment receipts before marking invoices as paid.</div>
        </div>
        {counts.pending_manager_review > 0 && (
          <div style={{ fontSize: 12.5, color: "var(--amber)", fontWeight: 600 }}>
            {counts.pending_manager_review} pending review
          </div>
        )}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 22 }}>
        {TABS.map((t) => {
          const active = tab === t.key;
          const isPending = t.key === "pending_manager_review";
          return (
            <div
              key={t.key}
              onClick={() => switchTab(t.key)}
              style={{
                cursor: "pointer", borderRadius: 10, padding: "14px 16px",
                background: isPending ? "var(--amber-bg)" : "var(--panel)",
                border: `1px solid ${active ? `var(--${t.accent})` : "var(--border)"}`,
                boxShadow: active ? `0 0 0 1px var(--${t.accent})` : "none",
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <div style={{ fontSize: 12.5, fontWeight: 600, color: isPending ? "var(--amber)" : "var(--text)" }}>{t.label}</div>
                <div style={{ fontFamily: "'IBM Plex Mono'", fontSize: 20, fontWeight: 600, color: `var(--${t.accent})` }}>{counts[t.key] ?? "—"}</div>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 2 }}>{t.sub}</div>
            </div>
          );
        })}
      </div>

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1 1 240px", maxWidth: 320 }}>
          <span style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-3)" }}><SearchIcon /></span>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search bidder or invoice..."
            style={{ width: "100%", padding: "8px 10px 8px 32px", border: "1px solid var(--border)", borderRadius: 6, fontSize: 13, fontFamily: "'Inter'" }}
          />
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--text-2)" }}>
            {selected.length > 0 ? `${selected.length} selected` : `${filteredRows.length} record${filteredRows.length === 1 ? "" : "s"}`}
          </span>
          {canDelete && selected.length > 0 && (
            <button className="btn btn-sm btn-icon-only btn-danger" onClick={() => handleDelete(selected)} title="Delete"><TrashIcon /></button>
          )}
          {tab === "pending_manager_review" && selected.length > 0 && (
            <>
              <button className="btn btn-sm btn-brass" onClick={() => openReview("approve", selected)}>Approve</button>
              <button className="btn btn-sm btn-danger" onClick={() => openReview("reject", selected)}>Reject</button>
            </>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: 0, overflow: "hidden" }}>
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}><input type="checkbox" checked={filteredRows.length > 0 && selected.length === filteredRows.length} onChange={toggleAll} /></th>
                <th>Bidder</th><th>Invoice</th><th>Amount</th><th>{tab === "pending_manager_review" ? "Submitted" : "Reviewed"}</th>
                {tab !== "pending_manager_review" && <th>Status</th>}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-3)", padding: 40 }}>Loading...</td></tr>
              ) : filteredRows.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--text-3)", padding: 40 }}>
                  {search ? "No results match your search." : EMPTY_COPY[tab]}
                </td></tr>
              ) : filteredRows.map((p) => {
                const when = formatWhen(tab === "pending_manager_review" ? p.uploadedAt : p.managerVerifiedDate);
                return (
                  <tr
                    key={p.id}
                    onClick={() => setDrawerRow(p)}
                    style={{ cursor: "pointer", background: selected.includes(p.id) ? "var(--brass-bg)" : undefined }}
                  >
                    <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleRow(p.id)} /></td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{ width: 30, height: 30, borderRadius: "50%", background: "var(--brass)", color: "#fff", fontSize: 11, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          {initials(p.bidderName)}
                        </div>
                        <div>
                          <div style={{ fontSize: 13.5 }}>{p.bidderName}</div>
                          <div className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{p.winnerPhone}</div>
                        </div>
                      </div>
                    </td>
                    <td className="mono" style={{ fontSize: 12.5, color: "var(--text-2)" }}>{p.invoiceNumber}</td>
                    <td className="amount" style={{ fontWeight: 600 }}>{money(p.amountPaid)}</td>
                    <td>
                      <div style={{ fontSize: 12.5 }}>{when.date}</div>
                      <div style={{ fontSize: 11, color: "var(--text-3)" }}>{when.time}</div>
                    </td>
                    {tab !== "pending_manager_review" && (
                      <td><span className={`stamp ${tab === "manager_approved" ? "paid" : "cancelled"}`}>{tab === "manager_approved" ? "Approved" : "Rejected"}</span></td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {drawerRow && (
        <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) setDrawerRow(null); }}>
          <div style={{
            position: "absolute", top: 0, right: 0, bottom: 0, width: "min(420px, 100%)",
            background: "var(--panel)", boxShadow: "-8px 0 24px rgba(20,23,28,0.14)",
            display: "flex", flexDirection: "column", overflowY: "auto",
          }}>
            <div style={{ padding: "20px 22px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontWeight: 600, fontSize: 15 }}>Receipt details</div>
              <button className="modal-close" onClick={() => setDrawerRow(null)}><CloseIcon /></button>
            </div>
            <div style={{ padding: 22, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
                <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--brass)", color: "#fff", fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  {initials(drawerRow.bidderName)}
                </div>
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14.5 }}>{drawerRow.bidderName}</div>
                  <div className="mono" style={{ fontSize: 12, color: "var(--text-3)" }}>{drawerRow.invoiceNumber}</div>
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 20 }}>
                <div><div className="fl">Amount</div><div style={{ fontWeight: 600, fontSize: 15 }}>{money(drawerRow.amountPaid)}</div></div>
                <div><div className="fl">Phone</div><div className="mono" style={{ fontSize: 13 }}>{drawerRow.winnerPhone}</div></div>
                <div>
                  <div className="fl">{tab === "pending_manager_review" ? "Submitted" : "Reviewed"}</div>
                  <div style={{ fontSize: 13 }}>
                    {(() => { const w = formatWhen(tab === "pending_manager_review" ? drawerRow.uploadedAt : drawerRow.managerVerifiedDate); return `${w.date}, ${w.time}`; })()}
                  </div>
                </div>
                {tab !== "pending_manager_review" && (
                  <div><div className="fl">Status</div><span className={`stamp ${tab === "manager_approved" ? "paid" : "cancelled"}`}>{tab === "manager_approved" ? "Approved" : "Rejected"}</span></div>
                )}
              </div>

              {drawerRow.managerNote && (
                <div style={{ marginBottom: 20 }}>
                  <div className="fl">Note</div>
                  <div style={{ fontSize: 13, color: "var(--text-2)" }}>{drawerRow.managerNote}</div>
                </div>
              )}

              <div className="fl" style={{ marginBottom: 8 }}>Receipt</div>
              {drawerRow.receiptUrl ? (
                isImageFile(drawerRow.receiptUrl) ? (
                  <a href={fileUrl(drawerRow.receiptUrl)} target="_blank" rel="noopener noreferrer">
                    <img src={fileUrl(drawerRow.receiptUrl)} alt="Receipt" style={{ width: "100%", borderRadius: 8, border: "1px solid var(--border)", display: "block" }} />
                  </a>
                ) : (
                  <a href={fileUrl(drawerRow.receiptUrl)} target="_blank" rel="noopener noreferrer" className="btn" style={{ width: "100%", textAlign: "center", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                    <EyeIcon /> Open receipt document
                  </a>
                )
              ) : <div className="locked-note" style={{ marginTop: 0 }}>No receipt file.</div>}
            </div>

            {tab === "manager_approved" && (
              <div style={{ marginTop: 20 }}>
                <div className="fl" style={{ marginBottom: 8 }}>AI-extracted data</div>
                {drawerRow.extraction ? (
                  <div className="card" style={{ background: "var(--paper)", fontSize: 13 }}>
                    <div>TIN: {drawerRow.extraction.tin || "—"}</div>
                    <div>Receipt #: {drawerRow.extraction.receiptNumber || "—"}</div>
                    <div>Date on receipt: {drawerRow.extraction.extractedDate || "—"}</div>
                    <div>Customer: {drawerRow.extraction.customerName || "—"}</div>
                    <div>Total: {drawerRow.extraction.totalAmount ?? "—"}</div>
                    <div>VAT: {drawerRow.extraction.vatAmount ?? "—"}</div>
                    {drawerRow.extraction.totalAmount && Number(drawerRow.extraction.totalAmount) !== Number(drawerRow.amountPaid) && (
                      <div style={{ color: "var(--amber)", marginTop: 6 }}>
                        Note: extracted total ({drawerRow.extraction.totalAmount}) doesn't match the recorded payment amount ({drawerRow.amountPaid}) — worth a manual look.
                      </div>
                    )}
                    <div style={{ color: "var(--text-3)", marginTop: 6 }}>Confidence: {drawerRow.extraction.extractionConfidence || "unknown"}</div>
                  </div>
                ) : (
                  <button className="btn btn-sm" onClick={() => extractReceipt(drawerRow.id)} disabled={extracting}>
                    {extracting ? "Extracting..." : "Extract with AI"}
                  </button>
                )}
              </div>
            )}

            {tab === "pending_manager_review" && (
              <div style={{ padding: 22, borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
                <button className="btn btn-brass" style={{ flex: 1 }} onClick={() => openReview("approve", [drawerRow.id])}>Approve receipt</button>
                <button className="btn btn-danger" style={{ flex: 1 }} onClick={() => openReview("reject", [drawerRow.id])}>Reject</button>
              </div>
            )}
            {canDelete && (
              <div style={{ padding: "0 22px 22px" }}>
                <button className="btn btn-ghost btn-danger" style={{ width: "100%" }} onClick={() => handleDelete([drawerRow.id])}>Delete this record</button>
              </div>
            )}
          </div>
        </div>
      )}

      {reviewing && (
        <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) setReviewing(null); }}>
          <div className="modal" style={{ maxWidth: 440 }}>
            <div style={{ padding: "32px 28px 20px", textAlign: "center", borderBottom: "1px solid var(--border)" }}>
              <div style={{ width: 52, height: 52, borderRadius: "50%", margin: "0 auto 14px", display: "flex", alignItems: "center", justifyContent: "center", background: reviewing === "approve" ? "var(--green-bg)" : "var(--red-bg)", color: reviewing === "approve" ? "var(--green)" : "var(--red)" }}>
                {reviewing === "approve" ? <CheckIcon /> : <XIcon />}
              </div>
              <h3 style={{ margin: "0 0 10px", fontSize: 16 }}>{reviewing === "approve" ? "Approve" : "Reject"} receipt{selected.length === 1 ? "" : "s"}</h3>
              {reviewRows.length <= 3 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 8 }}>
                  {reviewRows.map((r) => (
                    <div key={r.id} style={{ fontSize: 12.5, color: "var(--text-2)" }}>
                      <span style={{ fontWeight: 600, color: "var(--text)" }}>{r.bidderName}</span> · {r.invoiceNumber} · {money(r.amountPaid)}
                    </div>
                  ))}
                </div>
              ) : (
                <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 8 }}>{reviewRows.length} receipts selected</div>
              )}
              <div style={{ fontSize: 12.5, color: "var(--text-3)", lineHeight: 1.5 }}>
                {reviewing === "approve" ? "This immediately marks the invoice(s) as Paid and records it in the audit trail." : "The bidder will be notified by SMS and asked to resubmit."}
              </div>
            </div>
            <div style={{ padding: "18px 28px 28px" }}>
              <label style={{ display: "block", fontSize: 11.5, textTransform: "uppercase", letterSpacing: "0.04em", color: "var(--text-3)", marginBottom: 6 }}>
                Note {reviewing === "reject" ? <span className="req">(required)</span> : <span className="opt">(optional)</span>}
              </label>
              <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} autoFocus
                placeholder={reviewing === "reject" ? "e.g. amount doesn't match, receipt is blurry..." : "Internal note, visible in the audit trail"}
                style={{ width: "100%", fontFamily: "'Inter'", fontSize: 13.5, padding: 10, border: "1px solid var(--border)", borderRadius: 8, marginBottom: 18, resize: "vertical" }} />
              <div style={{ display: "flex", gap: 8 }}>
                <button className={`btn ${reviewing === "approve" ? "btn-brass" : "btn-danger"}`} style={{ flex: 1 }} onClick={submitReview} disabled={saving || (reviewing === "reject" && !note.trim())}>
                  {saving ? "Saving..." : reviewing === "approve" ? "Approve receipt" : "Confirm reject"}
                </button>
                <button className="btn btn-ghost" onClick={() => setReviewing(null)} disabled={saving}>Cancel</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
