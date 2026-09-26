import { useState, useEffect } from "react";
import { apiCall } from "../api";

export default function CallCenter({ role, token, privileges }) {
  const [rows, setRows] = useState([]);
  const [statusFilters, setStatusFilters] = useState([{ value: "", label: "All unpaid statuses" }]);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notesEditMode, setNotesEditMode] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [draftNote, setDraftNote] = useState("");
  const [saving, setSaving] = useState(false);

  const canManage = (privileges || []).includes("manage_call_center");

  useEffect(() => { fetchRows(); }, [statusFilter]);

  async function fetchRows() {
    setLoading(true);
    setError("");
    try {
      const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
      const res = await apiCall(`/api/call-center/${qs}`, {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to load call center list");
        return;
      }
      setRows(data.rows);
      setStatusFilters(data.statusFilters);
    } catch (err) {
      setError("Network error loading call center list");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function startEdit(row) {
    if (!notesEditMode || !canManage) return;
    setEditingId(row.id);
    setDraftNote(row.callNotes || "");
  }

  function cancelEdit() {
    setEditingId(null);
    setDraftNote("");
  }

  async function saveNote(id) {
    setSaving(true);
    try {
      const res = await apiCall(`/api/call-center/${id}/note/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ callNotes: draftNote }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to save note");
        return;
      }
      setRows((prev) => prev.map((r) => (r.id === id ? { ...r, callNotes: data.callNotes } : r)));
      setEditingId(null);
    } catch (err) {
      setError("Network error saving note");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  const STATUS_LABELS = {
    invoice_generated: "Invoice Generated",
    pending_payment: "Pending Payment",
    payment_submitted: "Payment Submitted",
    under_verification: "Under Verification",
    overdue: "Overdue",
  };

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16, flexWrap: "wrap" }}>
        <div className="field" style={{ maxWidth: 240 }}>
          <select
            className="select-standalone"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ maxWidth: 240 }}
          >
            {statusFilters.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </div>
        <div style={{ fontSize: 13, color: "var(--text-2)" }}>
          {loading ? "Loading..." : `${rows.length} to contact`}
        </div>
        {canManage && (
          <button
            className={"btn btn-sm" + (notesEditMode ? " btn-brass" : "")}
            style={{ marginLeft: "auto" }}
            onClick={() => { setNotesEditMode((v) => !v); cancelEdit(); }}
          >
            {notesEditMode ? "Done editing" : "Edit notes"}
          </button>
        )}
      </div>

      {notesEditMode && (
        <div className="queue-note" style={{ marginBottom: 10 }}>
          Click any row below to edit its note.
        </div>
      )}

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th>Bidder</th>
                <th>Phone</th>
                <th>Company</th>
                <th>Auction</th>
                <th>Amount Due</th>
                <th>Due Date</th>
                <th>Status</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && !loading ? (
                <tr><td colSpan={8} style={{ textAlign: "center", color: "var(--text-3)", padding: 20 }}>Nobody to contact right now</td></tr>
              ) : rows.map((r) => (
                <tr
                  key={r.id}
                  onClick={() => editingId !== r.id && startEdit(r)}
                  style={{ cursor: notesEditMode && canManage && editingId !== r.id ? "pointer" : "default" }}
                >
                  <td>{r.bidderName}</td>
                  <td className="mono">{r.phone}</td>
                  <td>{r.companyName}</td>
                  <td>{r.auction}</td>
                  <td className="amount">ETB {Number(r.amountDue).toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
                  <td>{r.dueDate}</td>
                  <td><span className={`stamp ${r.status}`}>{STATUS_LABELS[r.status] || r.status}</span></td>
                  <td style={{ minWidth: 220 }} onClick={(e) => e.stopPropagation()}>
                    {editingId === r.id ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        <input
                          value={draftNote}
                          onChange={(e) => setDraftNote(e.target.value)}
                          style={{ width: "100%" }}
                          autoFocus
                        />
                        <div style={{ display: "flex", gap: 6 }}>
                          <button className="btn btn-sm btn-brass" onClick={() => saveNote(r.id)} disabled={saving}>
                            {saving ? "Saving..." : "Save"}
                          </button>
                          <button className="btn btn-sm" onClick={cancelEdit} disabled={saving}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div style={{ fontSize: 13, color: r.callNotes ? "var(--text)" : "var(--text-3)", fontStyle: r.callNotes ? "normal" : "italic" }}>
                        {r.callNotes || "No notes yet"}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="locked-note" style={{ marginTop: 14 }}>
        Only CRM / Call Center Officers can call bidders or add notes here — click "Edit notes" above, then click a row to update it.
      </div>
    </div>
  );
}