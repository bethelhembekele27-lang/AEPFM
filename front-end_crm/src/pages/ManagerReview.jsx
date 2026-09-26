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

const RefreshIcon = () => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M23 4v6h-6" /><path d="M1 20v-6h6" /><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" /></svg>);
const SparkleIcon = () => (<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" /></svg>);
const WarnIcon = () => (<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" /><line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" /></svg>);

const VERIFY_ET_BANKS = [
  { v: "", l: "Let Verify.ET detect it" },
  { v: "cbe", l: "CBE" }, { v: "telebirr", l: "Telebirr" }, { v: "boa", l: "Bank of Abyssinia" },
  { v: "dashen", l: "Dashen Bank" }, { v: "awash", l: "Awash Bank" }, { v: "cbebirr", l: "CBE Birr" },
  { v: "mpesa", l: "MPESA" }, { v: "siinqee", l: "Siinqee Bank" }, { v: "kaafiebirr", l: "Kaafi Ebirr" },
];
const SUFFIX_BANKS = ["cbe", "boa"];
const PHONE_BANKS = ["cbebirr"];

function ConfidenceBadge({ level }) {
  const map = { high: "paid", medium: "pending_payment", low: "cancelled" };
  const label = level ? level.charAt(0).toUpperCase() + level.slice(1) : "Unknown";
  return <span className={`stamp ${map[level] || "cancelled"}`}>{label}</span>;
}

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

export default function ManagerReview({ role, privileges, token }) {
  const canManage = (privileges || []).includes("manager_verify_receipt");
  const restrictedView = !canManage && (privileges || []).includes("verify_payment");
  const canAccess = canManage || restrictedView;
  const canDelete = (privileges || []).includes("delete_records");

  const [tab, setTab] = useState(restrictedView ? "manager_approved" : "pending_manager_review");
  const [rows, setRows] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState([]);
  const [search, setSearch] = useState("");
  const [drawerRow, setDrawerRow] = useState(null);
  const [reviewing, setReviewing] = useState(null);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [vetBank, setVetBank] = useState("");
  const [vetRef, setVetRef] = useState("");
  const [vetSuffix, setVetSuffix] = useState("");
  const [vetPhone, setVetPhone] = useState("");
  const [vetChecking, setVetChecking] = useState(false);
  const [vetError, setVetError] = useState("");

  function openDrawerRow(row) {
    setDrawerRow(row);
    setVetRef(row?.extraction?.bankReferenceNumber || "");
    setVetBank("");
    setVetSuffix("");
    setVetPhone("");
    setVetError("");
  }

  async function checkVerifyEt() {
    if (!drawerRow) return;
    setVetChecking(true);
    setVetError("");
    try {
      const res = await apiCall(`/api/receipts/${drawerRow.id}/verify-transaction/`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ bank: vetBank, referenceNumber: vetRef, accountSuffix: vetSuffix, phoneNumber: vetPhone }),
      });
      const data = await res.json();
      if (!res.ok) { setVetError(data.error || "Check failed"); return; }
      setDrawerRow((r) => ({ ...r, verifyEtCheck: data }));
      setRows((prev) => prev.map((r) => (r.id === drawerRow.id ? { ...r, verifyEtCheck: data } : r)));
    } catch (err) {
      setVetError("Network error");
      console.error(err);
    } finally {
      setVetChecking(false);
    }
  }

  useEffect(() => { if (canAccess) { fetchRows(tab); fetchCounts(); } else setLoading(false); }, [tab]);

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

  function switchTab(t) {
    if (restrictedView && t !== "manager_approved") return;
    setTab(t); setSelected([]); setSearch(""); setDrawerRow(null);
  }
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

  if (!canAccess) {
    return <div className="card"><h3 style={{ margin: "0 0 6px" }}>Receipt verification</h3><div className="locked-note">Only Administrators, Auction Managers, and Finance Managers can view receipts here.</div></div>;
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

      <div style={{ display: "grid", gridTemplateColumns: restrictedView ? "1fr" : "repeat(3, 1fr)", gap: 12, marginBottom: 22 }}>
        {(restrictedView ? TABS.filter((t) => t.key === "manager_approved") : TABS).map((t) => {
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
          {canManage && canDelete && selected.length > 0 && (
            <button className="btn btn-sm btn-icon-only btn-danger" onClick={() => handleDelete(selected)} title="Delete"><TrashIcon /></button>
          )}
          {canManage && tab === "pending_manager_review" && selected.length > 0 && (
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
                <th style={{ width: 32 }}>
                  {canManage && <input type="checkbox" checked={filteredRows.length > 0 && selected.length === filteredRows.length} onChange={toggleAll} />}
                </th>
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
                    onClick={() => openDrawerRow(p)}
                    style={{ cursor: "pointer", background: selected.includes(p.id) ? "var(--brass-bg)" : undefined }}
                  >
                    <td onClick={(e) => e.stopPropagation()}>
                      {canManage && <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleRow(p.id)} />}
                    </td>
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

            <div style={{ marginTop: 20 }}>
              <div className="fl" style={{ marginBottom: 8 }}>Verify with Verify.ET</div>
              <div className="card" style={{ background: "var(--paper)", padding: 16 }}>
                <div className="field-grid" style={{ marginBottom: 10, gap: "10px 20px" }}>
                  <div className="field">
                    <div className="fl">Bank</div>
                    <select value={vetBank} onChange={(e) => setVetBank(e.target.value)}>
                      {VERIFY_ET_BANKS.map((b) => <option key={b.v} value={b.v}>{b.l}</option>)}
                    </select>
                  </div>
                  <div className="field">
                    <div className="fl">Reference number</div>
                    <input value={vetRef} onChange={(e) => setVetRef(e.target.value)} placeholder="e.g. FT1234567890" />
                  </div>
                  {SUFFIX_BANKS.includes(vetBank) && (
                    <div className="field"><div className="fl">Account suffix</div><input value={vetSuffix} onChange={(e) => setVetSuffix(e.target.value)} /></div>
                  )}
                  {PHONE_BANKS.includes(vetBank) && (
                    <div className="field"><div className="fl">Phone</div><input value={vetPhone} onChange={(e) => setVetPhone(e.target.value)} placeholder="251911234567" /></div>
                  )}
                </div>

                <button className="btn btn-sm btn-brass" onClick={checkVerifyEt} disabled={vetChecking || !vetRef.trim()}>
                  {vetChecking ? "Checking..." : "Check with Verify.ET"}
                </button>

                {vetError && (
                  vetError === "Verify.ET is not configured on this server." ? (
                    <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-3)", fontStyle: "italic" }}>Verify.ET isn't set up yet.</div>
                  ) : (
                    <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--red)" }}>{vetError}</div>
                  )
                )}

                {drawerRow.verifyEtCheck && drawerRow.verifyEtCheck.processingStatus === "completed" && (
                  <div style={{ marginTop: 14 }}>
                    <span className={`stamp ${drawerRow.verifyEtCheck.verified ? "paid" : "cancelled"}`}>
                      {drawerRow.verifyEtCheck.verified ? "Verified" : "Not verified"}
                    </span>
                    {drawerRow.verifyEtCheck.verified && (
                      <div style={{ fontSize: 12.5, marginTop: 8, lineHeight: 1.6 }}>
                        <div>Amount: {drawerRow.verifyEtCheck.amount} {drawerRow.verifyEtCheck.currency}</div>
                        <div>Sender: {drawerRow.verifyEtCheck.senderName || "—"}</div>
                        <div>Receiver: {drawerRow.verifyEtCheck.receiverName || "—"}</div>
                      </div>
                    )}
                    {drawerRow.verifyEtCheck.amount && Number(drawerRow.verifyEtCheck.amount) !== Number(drawerRow.amountPaid) && (
                      <div style={{ background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5 }}>
                        Verify.ET's amount ({drawerRow.verifyEtCheck.amount}) doesn't match the recorded payment ({drawerRow.amountPaid}). Informational only.
                      </div>
                    )}
                    {drawerRow.verifyEtCheck.settlementMatched === false && (
                      <div style={{ background: "var(--red-bg)", color: "var(--red)", borderRadius: 8, padding: "10px 12px", marginTop: 10, fontSize: 12.5, fontWeight: 600 }}>
                        This transaction did NOT go to Auction Ethiopia's own account. Review carefully before approving.
                      </div>
                    )}
                  </div>
                )}
                {drawerRow.verifyEtCheck && drawerRow.verifyEtCheck.processingStatus !== "completed" && (
                  <div style={{ marginTop: 10, fontSize: 12.5, color: "var(--text-3)" }}>Still processing — check again shortly.</div>
                )}
              </div>
            </div>

            {tab === "manager_approved" && (
              <div style={{ marginTop: 20 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div className="fl" style={{ margin: 0 }}>AI-extracted data</div>
                  {drawerRow.extraction && (
                    <button
                      className="btn btn-sm btn-icon-only"
                      title="Re-extract"
                      onClick={() => extractReceipt(drawerRow.id)}
                      disabled={extracting}
                    >
                      {extracting ? <span style={{ display: "inline-block", width: 14, height: 14, border: "2px solid var(--border)", borderTopColor: "var(--brass)", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} /> : <RefreshIcon />}
                    </button>
                  )}
                </div>

                {drawerRow.extraction ? (
                  <div className="card" style={{ background: "var(--paper)", padding: 16 }}>
                    <div className="field-grid" style={{ marginBottom: 0, gap: "10px 20px" }}>
                      <div className="field"><div className="fl">TIN</div><div className="fv mono">{drawerRow.extraction.tin || "—"}</div></div>
                      <div className="field"><div className="fl">Receipt #</div><div className="fv mono">{drawerRow.extraction.receiptNumber || "—"}</div></div>
                      <div className="field"><div className="fl">Date on receipt</div><div className="fv">{drawerRow.extraction.extractedDate || "—"}</div></div>
                      {drawerRow.extraction.convertedGregorianDate && (
                        <div className="field"><div className="fl">Converted (Gregorian)</div><div className="fv mono">{drawerRow.extraction.convertedGregorianDate}</div></div>
                      )}
                      <div className="field"><div className="fl">Customer name</div><div className="fv">{drawerRow.extraction.customerName || "—"}</div></div>
                      <div className="field"><div className="fl">Total amount</div><div className="fv amount">{drawerRow.extraction.totalAmount ?? "—"}</div></div>
                      <div className="field"><div className="fl">VAT amount</div><div className="fv amount">{drawerRow.extraction.vatAmount ?? "—"}</div></div>
                      <div className="field" style={{ gridColumn: "1 / -1" }}><div className="fl">Description</div><div className="fv">{drawerRow.extraction.description || "—"}</div></div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 14 }}>
                      <span className="fl" style={{ margin: 0 }}>Confidence</span>
                      <ConfidenceBadge level={drawerRow.extraction.extractionConfidence} />
                    </div>

                    {drawerRow.extraction.totalAmount && Number(drawerRow.extraction.totalAmount) !== Number(drawerRow.amountPaid) && (
                      <div style={{ display: "flex", gap: 10, alignItems: "flex-start", background: "var(--amber-bg)", color: "var(--amber)", borderRadius: 8, padding: "10px 12px", marginTop: 14 }}>
                        <WarnIcon />
                        <div style={{ fontSize: 12.5, lineHeight: 1.5 }}>
                          Extracted total (<strong>{drawerRow.extraction.totalAmount}</strong>) doesn't match the recorded payment amount (<strong>{drawerRow.amountPaid}</strong>). Worth a manual look — this is informational only.
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <button className="btn btn-sm btn-brass" style={{ display: "inline-flex", alignItems: "center", gap: 6 }} onClick={() => extractReceipt(drawerRow.id)} disabled={extracting}>
                    {extracting ? (
                      <>
                        <span style={{ display: "inline-block", width: 12, height: 12, border: "2px solid rgba(255,255,255,0.4)", borderTopColor: "#fff", borderRadius: "50%", animation: "spin 0.7s linear infinite" }} />
                        Extracting...
                      </>
                    ) : (
                      <><SparkleIcon /> Extract with AI</>
                    )}
                  </button>
                )}
              </div>
            )}

            {canManage && tab === "pending_manager_review" && (
              <div style={{ padding: 22, borderTop: "1px solid var(--border)", display: "flex", gap: 8 }}>
                <button className="btn btn-brass" style={{ flex: 1 }} onClick={() => openReview("approve", [drawerRow.id])}>Approve receipt</button>
                <button className="btn btn-danger" style={{ flex: 1 }} onClick={() => openReview("reject", [drawerRow.id])}>Reject</button>
              </div>
            )}
            {canManage && canDelete && (
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
