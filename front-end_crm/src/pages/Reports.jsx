import { useState, useEffect } from "react";
import { apiCall, API_BASE } from "../api";

const REPORT_TYPE_OPTIONS = [
  { v: "outstanding", l: "Outstanding processing fees" },
  { v: "overdue", l: "Overdue payments report" },
  { v: "daily", l: "Daily collections" },
  { v: "monthly", l: "Monthly collections" },
  { v: "verification", l: "Payment verification report" },
  { v: "by-auction", l: "Revenue by auction" },
  { v: "by-client", l: "Revenue by client" },
];

const PERIOD_OPTIONS = [
  { v: "today", l: "Today" },
  { v: "week", l: "This week" },
  { v: "month", l: "This month" },
  { v: "year", l: "This year" },
];

const STATUS_LABELS = {
  invoice_generated: "Invoice Generated",
  pending_payment: "Pending Payment",
  payment_submitted: "Payment Submitted",
  under_verification: "Under Verification",
  paid: "Paid",
  overdue: "Overdue",
  cancelled: "Cancelled",
  waived: "Waived",
};

const FILTERS_KEY = "reports_filters_draft";

function loadDraftFilters() {
  try {
    const raw = sessionStorage.getItem(FILTERS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (err) {
    console.error("Failed to load saved report filters", err);
  }
  return {
    reportType: "outstanding", period: "month",
    clientCompany: "", importBatch: "", auction: "",
    dateFrom: "", dateTo: "", paymentStatus: [],
  };
}

export default function Reports({ privileges, token }) {
  const [filters, setFilters] = useState(loadDraftFilters);
  const [options, setOptions] = useState({ companies: [], importBatches: [], paymentStatuses: [] });
  const [preview, setPreview] = useState(null);
  const [showFilters, setShowFilters] = useState(true);
  const [loading, setLoading] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const [error, setError] = useState("");
  const [recent, setRecent] = useState([]);

  useEffect(() => { fetchRecent(); fetchOptions(); }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(FILTERS_KEY, JSON.stringify(filters));
    } catch (err) {
      console.error("Failed to save report filters", err);
    }
  }, [filters]);

  async function fetchOptions() {
    try {
      const res = await apiCall('/api/reports/filter-options/', {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (res.ok) setOptions(await res.json());
    } catch (err) {
      console.error('Failed to load filter options', err);
    }
  }

  async function fetchRecent() {
    try {
      const res = await apiCall('/api/reports/recent/', {
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (res.ok) setRecent(await res.json());
    } catch (err) {
      console.error('Failed to load recent reports', err);
    }
  }

  function setF(k, v) {
    setFilters((p) => ({ ...p, [k]: v }));
  }

  function toggleStatus(value) {
    setFilters((p) => {
      const has = p.paymentStatus.includes(value);
      return {
        ...p,
        paymentStatus: has
          ? p.paymentStatus.filter((s) => s !== value)
          : [...p.paymentStatus, value],
      };
    });
  }

  function buildBody() {
    const body = { reportType: filters.reportType, period: filters.period };
    ['clientCompany', 'importBatch', 'auction', 'dateFrom', 'dateTo'].forEach((k) => {
      if (filters[k]) body[k] = filters[k];
    });
    if (filters.paymentStatus.length > 0) body.paymentStatus = filters.paymentStatus;
    return body;
  }

  async function runPreview() {
    setLoading(true);
    setError("");
    try {
      const res = await apiCall('/api/reports/preview/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify(buildBody()),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || 'Failed to run report');
        setPreview(null);
        return;
      }
      setPreview(data);
      setShowFilters(false);
    } catch (err) {
      setError('Network error running report');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function generatePdf() {
    setError("");
    setPdfLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/reports/generate-pdf/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Token ${token}`,
        },
        body: JSON.stringify(buildBody()),
      });
      if (!res.ok) {
        let message = 'Failed to generate PDF';
        try {
          const data = await res.json();
          message = data.error || message;
        } catch {
          message = `Server error (${res.status})`;
        }
        setError(message);
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${filters.reportType}-report.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      await fetchRecent();
    } catch (err) {
      setError('Network error generating PDF');
      console.error(err);
    } finally {
      setPdfLoading(false);
    }
  }

  const canView = (privileges || []).includes("view_reports");

  if (!canView) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 6px" }}>Custom reports</h3>
        <div className="locked-note">You don't have the "Generate custom reports" privilege.</div>
      </div>
    );
  }

  return (
    <div>
      {showFilters && (
        <div className="card">  
          <h3 style={{ margin: "0 0 4px" }}>Build a custom report</h3>
          <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 16 }}>
            Choose a report type and narrow it to a specific period, client, batch, or auction. Preview on screen, then generate a PDF.
          </div>

          <div className="field-grid">
            <div className="field">
              <div className="fl">Report type</div>
              <select value={filters.reportType} onChange={(e) => setF("reportType", e.target.value)}>
                {REPORT_TYPE_OPTIONS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="fl">Period</div>
              <select value={filters.period} onChange={(e) => setF("period", e.target.value)}>
                {PERIOD_OPTIONS.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
              </select>
            </div>

            <div className="field">
              <div className="fl">Client / company <span className="opt">(optional)</span></div>
              <select value={filters.clientCompany} onChange={(e) => setF("clientCompany", e.target.value)}>
                <option value="">Any client</option>
                {options.companies.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="field">
              <div className="fl">Import batch <span className="opt">(optional)</span></div>
              <select value={filters.importBatch} onChange={(e) => setF("importBatch", e.target.value)}>
                <option value="">Any batch</option>
                {options.importBatches.map((b) => <option key={b.id} value={b.id}>{b.label}</option>)}
              </select>
            </div>

            <div className="field">
              <div className="fl">Date from <span className="opt">(optional)</span></div>
              <input type="date" value={filters.dateFrom} onChange={(e) => setF("dateFrom", e.target.value)} />
            </div>
            <div className="field">
              <div className="fl">Date to <span className="opt">(optional)</span></div>
              <input type="date" value={filters.dateTo} onChange={(e) => setF("dateTo", e.target.value)} />
            </div>

            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <div className="fl">Auction <span className="opt">(optional)</span></div>
              <input
                placeholder="e.g. Spring Classic Cars"
                value={filters.auction}
                onChange={(e) => setF("auction", e.target.value)}
              />
            </div>
          </div>

          <div style={{ marginBottom: 18 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text)", marginBottom: 10 }}>
              Payment status <span className="opt" style={{ fontWeight: 400 }}>(optional — pick as many as you like)</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "12px 28px" }}>
              {(options.paymentStatuses.length > 0
                ? options.paymentStatuses
                : Object.entries(STATUS_LABELS).map(([value, label]) => ({ value, label }))
              ).map((s) => (
                <label
                  key={s.value}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 7,
                    fontSize: 13.5,
                    cursor: "pointer",
                    whiteSpace: "nowrap",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={filters.paymentStatus.includes(s.value)}
                    onChange={() => toggleStatus(s.value)}
                    style={{ width: 15, height: 15, accentColor: "var(--brass)", flexShrink: 0 }}
                  />
                  {s.label}
                </label>
              ))}
            </div>
          </div>

          <button className="btn btn-primary" onClick={runPreview} disabled={loading}>
            {loading ? "Loading..." : "Preview report"}
          </button>
          {error && <div style={{ color: "var(--red)", marginTop: 10, fontSize: 13 }}>{error}</div>}
        </div>
      )}

      {preview && (
        <div className="card" style={{ marginTop: showFilters ? 16 : 0 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 4 }}>
            <h3 style={{ margin: 0 }}>{preview.title} — preview</h3>
            <div style={{ fontSize: 12.5, color: "var(--text-2)" }}>
              {preview.periodLabel} · {preview.count} record(s) · total ETB {Number(preview.total).toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
          </div>
          <div className="tbl-wrap" style={{ marginTop: 12, marginBottom: 14 }}>
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>{preview.columns.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.rows.length === 0 ? (
                    <tr><td colSpan={preview.columns.length} style={{ textAlign: "center", color: "var(--text-3)", padding: 20 }}>No matching records</td></tr>
                  ) : preview.rows.map((row, i) => (
                    <tr key={i}>
                      {preview.columns.map((c) => (
                        <td key={c.key}>
                          {c.key === "status" ? (
                            <span className={`stamp ${row[c.key]}`}>
                              {STATUS_LABELS[row[c.key]] || row[c.key]}
                            </span>
                          ) : (
                            row[c.key]
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-brass" onClick={generatePdf} disabled={pdfLoading}>
              {pdfLoading ? "Generating..." : "Generate PDF"}
            </button>
            <button className="btn" onClick={() => setShowFilters(true)}>Adjust filters</button>
          </div>
        </div>
      )}

      {recent.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <h3 style={{ margin: "0 0 10px" }}>Recently generated</h3>
          <div className="tbl-wrap">
            <div style={{ overflowX: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Report title</th>
                    <th>Period</th>
                    <th>Rows</th>
                    <th>Generated at</th>
                    <th>Generated by</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((r) => (
                    <tr key={r.id}>
                      <td>{r.title}</td>
                      <td>{r.periodLabel}</td>
                      <td className="amount">{r.rowCount}</td>
                      <td>{new Date(r.generatedAt).toLocaleString()}</td>
                      <td>{r.generatedBy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}