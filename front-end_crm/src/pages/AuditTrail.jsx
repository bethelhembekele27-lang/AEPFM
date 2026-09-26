import { useState, useEffect } from "react";
import { apiCall } from "../api";

const ACTION_TYPE_LABELS = {
  'change_status': 'Status changed',
  'generate_invoice_pdf': 'Generate invoice PDF',
  'extend_due_date': 'Extend due date',
  'upload_payment': 'Payment uploaded',
  'add_call_note': 'Call center note updated',
  'send_sms': 'SMS sent',
  'other': 'Other',
};

export default function AuditTrail({ role, token, privileges }) {
  const [logs, setLogs] = useState([]);
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [actionTypes, setActionTypes] = useState([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [clearing, setClearing] = useState(false);
  
  const [filters, setFilters] = useState({
    user_id: "",
    role: "",
    action: "",
    date_from: "",
    date_to: "",
  });
  
  const [ordering, setOrdering] = useState("-actionDate");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [count, setCount] = useState(0);

  const canView = (privileges || []).includes("view_audit");
  const canClear = (privileges || []).includes("delete_records");

  useEffect(() => { if (canView) fetchFilterOptions(); }, []);
  useEffect(() => { setPage(1); }, [filters]);
  useEffect(() => { if (canView) fetchLogs(); }, [filters, ordering, page]);

  async function fetchFilterOptions() {
    try {
      const res = await apiCall('/api/audit-logs/filter-options/', {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (!res.ok) return;
      const data = await res.json();
      setUsers(data.users || []);
      setRoles(data.roles || []);
      setActionTypes(data.actionTypes || []);
    } catch (err) {
      console.error('Failed to load filter options', err);
    }
  }

  async function fetchLogs() {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (filters.user_id) params.append('user_id', filters.user_id);
      if (filters.role) params.append('role', filters.role);
      if (filters.action) params.append('action', filters.action);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);
      if (ordering) params.append('ordering', ordering);
      params.append('page', page);

      const res = await apiCall(`/api/audit-logs/?${params.toString()}`, {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to load audit logs");
        return;
      }
      setLogs(data.results || []);
      setCount(data.count || 0);
      setTotalPages(Math.ceil((data.count || 0) / 20));
    } catch (err) {
      setError("Network error loading audit logs");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function setF(k, v) {
    setFilters((p) => ({ ...p, [k]: v }));
  }

  function toggleOrdering(field) {
    if (ordering === field) {
      setOrdering(`-${field}`);
    } else if (ordering === `-${field}`) {
      setOrdering(field);
    } else {
      setOrdering(field);
    }
  }

  function getSortIcon(field) {
    if (!ordering.endsWith(field)) return " ↕";
    return ordering.startsWith('-') ? " ↓" : " ↑";
  }

  async function clearAuditTrail() {
    if (!window.confirm("Clear the entire audit trail? This permanently deletes every log entry and cannot be undone.")) return;
    setClearing(true);
    setError("");
    try {
      const res = await apiCall('/api/audit-logs/clear/', {
        method: 'DELETE',
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to clear audit trail");
        return;
      }
      setLogs([]);
      setCount(0);
      setTotalPages(1);
      setPage(1);
    } catch (err) {
      setError("Network error clearing audit trail");
      console.error(err);
    } finally {
      setClearing(false);
    }
  }

  if (!canView) {
    return (
      <div className="card">
        <h3 style={{ margin: "0 0 6px" }}>Audit trail</h3>
        <div className="locked-note">Only Administrators and Finance Managers can view the audit trail.</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", gap: 12, marginBottom: 16, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <div className="fl">User</div>
          <select value={filters.user_id} onChange={(e) => setF("user_id", e.target.value)}>
            <option value="">All users</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.username}</option>)}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <div className="fl">Role</div>
          <select value={filters.role} onChange={(e) => setF("role", e.target.value)}>
            <option value="">All roles</option>
            {roles.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <div className="fl">Action</div>
          <select value={filters.action} onChange={(e) => setF("action", e.target.value)}>
            <option value="">All actions</option>
            {actionTypes.map((a) => <option key={a.value} value={a.value}>{a.label}</option>)}
          </select>
        </div>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <div className="fl">Date from</div>
          <input type="date" value={filters.date_from} onChange={(e) => setF("date_from", e.target.value)} />
        </div>
        <div className="field" style={{ flex: 1, minWidth: 160 }}>
          <div className="fl">Date to</div>
          <input type="date" value={filters.date_to} onChange={(e) => setF("date_to", e.target.value)} />
        </div>
        {canClear && (
          <button
            className="btn btn-sm btn-danger"
            onClick={clearAuditTrail}
            disabled={clearing || logs.length === 0}
            title="Permanently delete every audit log entry"
          >
            {clearing ? "Clearing..." : "Clear audit trail"}
          </button>
        )}
      </div>

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ cursor: "pointer" }} onClick={() => toggleOrdering("actionDate")}>
                  Date & Time{getSortIcon("actionDate")}
                </th>
                <th style={{ cursor: "pointer" }} onClick={() => toggleOrdering("performedBy__username")}>
                  User{getSortIcon("performedBy__username")}
                </th>
                <th style={{ cursor: "pointer" }} onClick={() => toggleOrdering("userRole")}>
                  Role{getSortIcon("userRole")}
                </th>
                <th>Invoice</th>
                <th>Action</th>
                <th>Previous Value</th>
                <th>New Value</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 20 }}>Loading...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={8} style={{ textAlign: "center", color: "var(--text-3)", padding: 20 }}>No matching audit entries</td></tr>
              ) : logs.map((log) => (
                <tr key={log.id}>
                  <td>{new Date(log.actionDate).toLocaleString()}</td>
                  <td className="mono">{log.performedBy || "—"}</td>
                  <td>{log.userRole || "—"}</td>
                  <td className="mono">{log.invoice}</td>
                  <td>{ACTION_TYPE_LABELS[log.actionType] || log.action}</td>
                  <td style={{ fontSize: 12, color: "var(--text-3)" }}>{log.previousValue || "—"}</td>
                  <td style={{ fontSize: 12, color: "var(--text-3)" }}>{log.newValue || "—"}</td>
                  <td style={{ fontSize: 12, color: "var(--text-3)", maxWidth: 200 }}>{log.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div style={{ display: "flex", justifyContent: "center", gap: 8, marginTop: 16, alignItems: "center" }}>
          <button
            className="btn btn-sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1 || loading}
          >
            Previous
          </button>
          <div style={{ fontSize: 13, color: "var(--text-2)" }}>
            Page {page} of {totalPages} ({count} total)
          </div>
          <button
            className="btn btn-sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || loading}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}