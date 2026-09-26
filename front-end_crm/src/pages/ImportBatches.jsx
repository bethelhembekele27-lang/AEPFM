import { useState, useEffect, useRef } from "react";
import { money } from "../data";
import { apiCall } from "../api";
import SendSmsBulkModal from "../components/SendSmsBulkModal";

export default function ImportBatches({ role, token, privileges }) {
  const canImport = (privileges || []).includes("import_batches");
  const [company, setCompany] = useState("");
  const [date, setDate] = useState("");
  const [batchName, setBatchName] = useState("");
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [batches, setBatches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const [dueDate, setDueDate] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 14);
    return d.toISOString().slice(0, 10);
  });
  const [viewingBatch, setViewingBatch] = useState(null);
  const [batchInvoices, setBatchInvoices] = useState([]);
  const [selectedBatches, setSelectedBatches] = useState([]);
  const [showSmsBulkModal, setShowSmsBulkModal] = useState(false);

  useEffect(() => {
    fetchBatches();
  }, [token]);

  async function openBatchDetail(b) {
    setViewingBatch(b);
    const res = await apiCall(`/api/import-batches/${b.id}/invoices/`);
    if (res.ok) {
      const data = await res.json();
      setBatchInvoices(data.results || data);
    }
  }

  async function fetchBatches() {
    try {
      const response = await apiCall('/api/import-batches/', {
        method: 'GET',
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (response.ok) {
        const data = await response.json();
        setBatches(data.results || data);
      }
    } catch (err) {
      console.error('Failed to load batches', err);
    }
  }

  async function runPreview() {
    if (!file || !company || !date) {
      setError("File, company name, and auction date are required.");
      return;
    }

    setLoading(true);
    setError("");

    const formData = new FormData();
    formData.append('file', file);
    formData.append('companyName', company);
    formData.append('auctionDate', date);
    if (batchName) formData.append('batchName', batchName);

    try {
      const response = await apiCall('/api/import-batches/preview/', {
        method: 'POST',
        headers: token ? { Authorization: `Token ${token}` } : {},
        body: formData,
      });

      if (!response.ok) {
        const err = await response.json();
        setError(err.detail || err.error || 'Preview failed');
        setLoading(false);
        return;
      }

      const data = await response.json();
      setPreview(data);
    } catch (err) {
      setError('Network error during preview');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  async function confirmImport() {
    setLoading(true);
    setError("");
    try {
      const response = await apiCall('/api/import-batches/confirm/', {
        method: 'POST',
        body: JSON.stringify({
          fileName: file?.name || '',
          batchName: batchName || '',
          companyName: company,
          auctionDate: date,
          groupedWinners: preview.groupedWinners,
          invalidRecords: preview.flaggedCount || 0,
          dueDate,
          columnMapping: preview.columnMapping || {},
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        setError(err.error || err.detail || 'Confirm failed');
        setLoading(false);
        return;
      }

      await fetchBatches();
      setPreview(null);
      setFile(null);
      setCompany("");
      setDate("");
      setBatchName("");
    } catch (err) {
      setError('Network error during confirm');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function toggleBatchRow(id) {
    setSelectedBatches((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  }

  function toggleAllBatches() {
    setSelectedBatches(selectedBatches.length === batches.length ? [] : batches.map((b) => b.id));
  }

  async function deleteSelectedBatches() {
    if (selectedBatches.length === 0) return;
    if (!window.confirm(`Delete ${selectedBatches.length} batch${selectedBatches.length > 1 ? "es" : ""} and all invoices generated from them? This cannot be undone.`)) return;
    try {
      for (const id of selectedBatches) {
        await apiCall(`/api/import-batches/${id}/`, { method: 'DELETE' });
      }
      await fetchBatches();
      setSelectedBatches([]);
    } catch {
      setError('Network error deleting batches');
    }
  }

  return (
    <div>
      <div className={"card section" + (canImport ? "" : " locked")} style={{ marginBottom: 18 }}>
        <h3 style={{ margin: "0 0 4px" }}>New import batch</h3>
        <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 16 }}>
          Upload a bid data report to generate invoices. Only one file is required — bidder company names are left blank and can be added manually afterward.
        </div>
        <div className="upload-form">
          <div className="full">
            <label>Bid data report <span className="req">*</span> — .xlsx only</label>
            <div
              className="filedrop"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setFile(e.dataTransfer.files[0]);
              }}
              onClick={() => fileInputRef.current?.click()}
              style={{ cursor: 'pointer' }}
            >
              {file ? file.name : "bid_data_report.xlsx — drag file here or click to browse"}
              <input
                ref={fileInputRef}
                type="file"
                accept=".xlsx"
                onChange={(e) => setFile(e.target.files?.[0])}
                style={{ display: 'none' }}
              />
            </div>
          </div>
          <div><label>Company name <span className="req">*</span></label><input value={company} onChange={(e) => setCompany(e.target.value)} placeholder="e.g. Ethio Telecom" /></div>
          <div><label>Auction date <span className="req">*</span></label><input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></div>
          <div className="full"><label>Batch name <span className="opt">(optional)</span></label><input value={batchName} onChange={(e) => setBatchName(e.target.value)} placeholder="e.g. Ethio Telecom Q4 2026" /></div>
        </div>
        {error && <div style={{ color: 'red', marginTop: 8, fontSize: 12 }}>{error}</div>}
        <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
          <button className="btn btn-primary" onClick={runPreview} disabled={loading}>
            {loading ? 'Loading...' : 'Preview import'}
          </button>
        </div>
      </div>
      {!canImport && <div className="locked-note" style={{ marginTop: -10, marginBottom: 18 }}>Only Administrators and Auction Managers can start a new import. You can still review past batches below.</div>}

      {preview && (
        <div className="card" style={{ marginBottom: 18 }}>
          <h3 style={{ margin: "0 0 4px" }}>Preview — nothing saved yet</h3>
          <div style={{ fontSize: 12.5, color: "var(--text-2)", marginBottom: 14 }}>
            {preview.totalWinners || 0} winners · {preview.totalLots || 0} lots found
            {preview.flaggedCount > 0 && ` · ${preview.flaggedCount} row(s) flagged and skipped`}
          </div>

          <div className="tbl-wrap" style={{ marginBottom: 14 }}>
            <table>
              <thead><tr><th>Bidder</th><th>Phone</th><th>Lots</th><th>Total fee</th><th>Fee %</th></tr></thead>
              <tbody>
                {(preview.groupedWinners || []).map((w, i) => (
                  <tr key={i}>
                    <td>{w.bidderName}</td>
                    <td className="mono">{w.winnerPhone}</td>
                    <td className="mono">{w.lots?.length || 0}</td>
                    <td className="amount">{money(parseFloat(w.totalFee || 0).toFixed(2))}</td>
                    <td className="mono">{parseFloat(w.feePercentage || 0.95).toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="locked-note" style={{ marginBottom: 14 }}>Fee % is editable per winner before confirming — click a row to adjust.</div>
          <div className="field" style={{ maxWidth: 220, marginBottom: 14 }}>
            <div className="fl">Due date <span className="opt">(defaults to +14 days)</span></div>
            <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-brass" onClick={confirmImport} disabled={loading}>
              {loading ? 'Confirming...' : 'Confirm & create invoices'}
            </button>
            <button className="btn btn-ghost" onClick={() => setPreview(null)}>Discard preview</button>
          </div>
        </div>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 12, alignItems: "center" }}>
        {selectedBatches.length > 0 && (
          <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
            {selectedBatches.length} selected
          </span>
        )}
        {(privileges || []).includes("delete_records") && (
          <button
            className="btn btn-danger btn-delete"
            onClick={deleteSelectedBatches}
            disabled={selectedBatches.length === 0}
            title="Delete selected batches"
            aria-label="Delete selected batches"
          >
            <svg className="btn-icon" viewBox="0 0 24 24" fill="currentColor">
              <path d="M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM9 16h2v-7H9v7zm4 0h2v-7h-2v7z" />
            </svg>
          </button>
        )}
      </div>

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}>
                  {(privileges || []).includes("delete_records") && <input type="checkbox" checked={batches.length > 0 && selectedBatches.length === batches.length} onChange={toggleAllBatches} />}
                </th>
                <th>Batch</th><th>Company</th><th>Auction date</th><th>Uploaded</th><th>Records</th><th>Status</th><th>Imported by</th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id}>
                  <td>
                    {(privileges || []).includes("delete_records") && <input type="checkbox" checked={selectedBatches.includes(b.id)} onChange={() => toggleBatchRow(b.id)} />}
                  </td>
                  <td onClick={() => openBatchDetail(b)} style={{ cursor: "pointer" }}>
                    {b.batchName || <span style={{ color: "var(--text-3)" }}>—</span>}
                    <div style={{ fontSize: 11, color: "var(--text-3)" }} className="mono">{b.fileName}</div>
                  </td>
                  <td>{b.companyName}</td>
                  <td className="mono">{new Date(b.auctionDate).toLocaleDateString()}</td>
                  <td className="mono">{new Date(b.uploadDate).toLocaleDateString()}</td>
                  <td className="mono">{b.validRecords}/{b.totalRecords}</td>
                  <td><span className="stamp paid" style={{ transform: "none" }}>{b.status}</span></td>
                  <td>{b.importedBy}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {viewingBatch && (
        <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) setViewingBatch(null); }}>
          <div className="modal">
            <div className="modal-head">
              <h3 style={{ margin: 0 }}>{viewingBatch.batchName || viewingBatch.companyName}</h3>
              <button className="modal-close" onClick={() => setViewingBatch(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <button className="btn btn-blue" style={{ marginBottom: 12 }} onClick={() => setShowSmsBulkModal(true)}>
                Send SMS to all {batchInvoices.length} invoices in this batch
              </button>
              {showSmsBulkModal && (
                <SendSmsBulkModal
                  invoices={batchInvoices}
                  token={token}
                  onClose={() => setShowSmsBulkModal(false)}
                  onDone={() => openBatchDetail(viewingBatch)}
                />
              )}
              <div className="tbl-wrap">
                <table>
                  <thead><tr><th>Invoice #</th><th>Bidder</th><th>Total</th><th>Status</th></tr></thead>
                  <tbody>
                    {batchInvoices.map((inv) => (
                      <tr key={inv.id}>
                        <td className="mono">{inv.invoiceNumber}</td>
                        <td>{inv.bidderName}</td>
                        <td className="amount">{money(inv.totalAmount.toFixed(2))}</td>
                        <td><span className={`stamp ${inv.status}`}>{inv.status}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}