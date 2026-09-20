import { useState, useEffect } from "react";
import { LOCKED_STATUSES, PDF_ROLES, searchFieldDefs, money } from "../data";
import { ActionBtn } from "../components/ActionButton";
import StatusCell from "../components/StatusCell";
import GeneratePdfModal from "../components/GeneratePdfModal";
import { apiCall, API_BASE } from "../api";
import DueDateCell from "../components/DueDateCell";

export default function Operations({ role, token, onOpenDetail, onOpenSms }) {
  const [searchField, setSearchField] = useState("bidderName");
  const [searchValue, setSearchValue] = useState("");
  const [searchValueTo, setSearchValueTo] = useState("");
  const [filtered, setFiltered] = useState(null);
  const [selected, setSelected] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showGenerateModal, setShowGenerateModal] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize] = useState(20);

  useEffect(() => {
    fetchInvoices();
  }, [currentPage, token]);
 
  const [hasNext, setHasNext] = useState(false);

async function fetchInvoices() {
  try {
    setLoading(true);
    const response = await apiCall(`/api/invoices/?page=${currentPage}`, {
      method: 'GET',
      headers: token ? { Authorization: `Token ${token}` } : {},
    });

    if (!response.ok) {
      if (response.status === 404 && currentPage > 1) {
        // fell past the last page — step back instead of erroring
        setCurrentPage((p) => Math.max(1, p - 1));
        return;
      }
      setError(`Failed to load invoices: ${response.status}`);
      return;
    }

    const data = await response.json();
    const invoiceList = data.results || data;
    setInvoices(invoiceList);
    setHasNext(Boolean(data.next));
    setError("");
  } catch (err) {
    setError('Network error loading invoices');
    console.error(err);
  } finally {
    setLoading(false);
  }
}

  const rows = filtered || invoices;
  const searchDef = searchFieldDefs[searchField];
  const canGeneratePdf = PDF_ROLES.includes(role);

  function runSearch() {
    if (searchField === "daterange") {
      let f = invoices;
      if (searchValue) f = f.filter((inv) => inv.dueDate >= searchValue);
      if (searchValueTo) f = f.filter((inv) => inv.dueDate <= searchValueTo);
      setFiltered(f);
      return;
    }
    const val = searchValue.toLowerCase().trim();
    if (!val) { setFiltered(null); return; }
    setFiltered(invoices.filter((inv) => {
      switch (searchField) {
        case "bidderName": return inv.bidderName.toLowerCase().includes(val);
        case "phoneNumber": return inv.winnerPhone.includes(val);
        case "companyName": return (inv.companyName || "").toLowerCase().includes(val);
        case "lotNo": return inv.lots.some((l) => l.lotNumber.toLowerCase().includes(val));
        case "batchId": return String(inv.importBatch) === val;
        case "status": return inv.status === val;
        default: return true;
      }
    }));
  }

  function clearSearch() {
    setSearchField("bidderName");
    setSearchValue("");
    setSearchValueTo("");
    setFiltered(null);
  }

  function toggleRow(invId) {
    setSelected((s) => s.includes(invId) ? s.filter((x) => x !== invId) : [...s, invId]);
  }

  function toggleAll() {
    setSelected(selected.length === rows.length ? [] : rows.map((r) => r.id));
  }

  async function changeStatus(invId, newStatus) {
    try {
      const response = await apiCall(`/api/invoices/${invId}/change-status/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ status: newStatus }),
      });

      if (response.ok) {
        await fetchInvoices();
      } else {
        setError('Failed to update status');
      }
    } catch (err) {
      setError('Network error updating status');
      console.error(err);
    }
  }

  const eligibleForPdf = invoices.filter((inv) => 
    selected.includes(inv.id) && !LOCKED_STATUSES.includes(inv.status)
  );

  function openGenerateModal() {
    if (selected.length === 0) {
      window.alert("Select at least one invoice first.");
      return;
    }
    if (eligibleForPdf.length === 0) {
      window.alert("None of the selected invoices are eligible — Paid, Cancelled, and Waived invoices can't have a new PDF generated.");
      return;
    }
    setShowGenerateModal(true);
  }

  async function confirmGeneratePdf({
    percentagesByInvId, auctionRefNumber, amhNames,
    amountWordsByInv = {}, feeWordsByInv = {}, officeAddress = '',
    totalAmountByInv = {}, feeAmountByInv = {}, bankAccountByInv = {},
    paragraph1ByInv = {}, paragraph2ByInv = {},
  }) {
    try {
      for (const [invId, pct] of Object.entries(percentagesByInvId)) {
        const amhName = amhNames[invId] || '';

        const response = await fetch(`${API_BASE}/api/invoices/${invId}/generate-pdf/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Token ${token}`,
          },
          body: JSON.stringify({
            feePercentage: parseFloat(pct),
            auctionRefNumber: auctionRefNumber || '',
            bidderNameAmharic: amhName,
            amountInWords: amountWordsByInv[invId] || '',
            feeInWords: feeWordsByInv[invId] || '',
            officeAddress: officeAddress || '',
            totalAmount: totalAmountByInv[invId] || '',
            feeAmount: feeAmountByInv[invId] || '',
            bankAccount: bankAccountByInv[invId] || '',
            paragraph1: paragraph1ByInv[invId] || '',
            paragraph2: paragraph2ByInv[invId] || '',
          }),
        });
      // ...rest unchanged
      // ...rest unchanged

        if (!response.ok) {
          const error = await response.json();
          setError(`Failed: ${error.detail}`);
          return;
        }

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;

        const invoiceRecord = invoices.find((i) => String(i.id) === String(invId));
        const safeName = (invoiceRecord?.bidderName || `Invoice_${invId}`)
          .trim()
          .replace(/[^a-zA-Z0-9]+/g, '_');
        a.download = `${safeName}_${invoiceRecord?.invoiceNumber || invId}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }

      alert('PDFs generated successfully!');
      await fetchInvoices();
      setSelected([]);
      setShowGenerateModal(false);
    } catch (err) {
      setError('Failed to generate PDFs');
      console.error(err);
    }
  }
  
const canDelete = role === "administrator";
const [showBulkUpdate, setShowBulkUpdate] = useState(false);

async function deleteSelected() {
  if (selected.length === 0) return;
  if (!window.confirm(`Delete ${selected.length} invoice${selected.length > 1 ? "s" : ""} permanently? This cannot be undone.`)) return;
  try {
    for (const id of selected) {
      await apiCall(`/api/invoices/${id}/`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
    }
    await fetchInvoices();
    setSelected([]);
  } catch (err) {
    setError('Failed to delete one or more invoices');
    console.error(err);
  }
}

function openBulkUpdate() {
  if (selected.length === 0) {
    window.alert("Select at least one invoice first.");
    return;
  }
  setShowBulkUpdate(true);
}

async function confirmBulkUpdate(newStatus) {
  try {
    for (const id of selected) {
      await apiCall(`/api/invoices/${id}/change-status/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ status: newStatus }),
      });
    }
    await fetchInvoices();
    setSelected([]);
    setShowBulkUpdate(false);
  } catch (err) {
    setError('Bulk update failed');
    console.error(err);
  }
}
async function changeDueDate(invId, newDate) {
  try {
    const response = await apiCall(`/api/invoices/${invId}/extend-due-date/`, {
      method: 'POST',
      body: JSON.stringify({ dueDate: newDate }),
    });
    if (response.ok) await fetchInvoices();
    else setError('Failed to update due date');
  } catch (err) {
    setError('Network error updating due date');
  }
}

function exportRecords() {
  const rowsToExport = selected.length > 0 ? invoices.filter((inv) => selected.includes(inv.id)) : rows;
  if (rowsToExport.length === 0) {
    window.alert("No records to export.");
    return;
  }
  const headers = ["Invoice #", "Bidder", "Company", "Lots", "Total Amount", "Due Date", "Status"];
  const csvRows = rowsToExport.map((inv) => [
    inv.invoiceNumber,
    inv.bidderName,
    inv.companyName || "",
    inv.lots?.length || 0,
    inv.totalAmount,
    inv.dueDate,
    inv.status,
  ]);
  const csv = [headers, ...csvRows]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","))
    .join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `invoices_export_${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

  if (loading) return <div style={{ padding: 20 }}>Loading invoices...</div>;
  if (error) return <div style={{ padding: 20, color: 'red' }}>{error}</div>;

  return (
    <div>
      <div className="filters">
        <select className="grow" value={searchField} onChange={(e) => { setSearchField(e.target.value); setSearchValue(""); setSearchValueTo(""); }}>
          <option value="bidderName">Bidder name</option>
          <option value="phoneNumber">Phone number</option>
          <option value="companyName">Company name</option>
          <option value="lotNo">Lot number</option>
          <option value="batchId">Import batch</option>
          <option value="status">Payment status</option>
          <option value="daterange">Date range</option>
        </select>
        {searchDef.type === "select" && (
          <select className="grow" value={searchValue} onChange={(e) => setSearchValue(e.target.value)}>
            <option value="">Any {searchDef.label}</option>
            {searchDef.options.map((o) => <option key={o.v} value={o.v}>{o.l}</option>)}
          </select>
        )}
        {searchDef.type === "text" && (
          <input value={searchValue} onChange={(e) => setSearchValue(e.target.value)} placeholder={`Search by ${searchDef.label}`} />
        )}
        {searchDef.type === "daterange" && (
          <>
            <input type="date" value={searchValue} onChange={(e) => setSearchValue(e.target.value)} />
            <span style={{ color: "var(--text-3)", fontSize: 12 }}>to</span>
            <input type="date" value={searchValueTo} onChange={(e) => setSearchValueTo(e.target.value)} />
          </>
        )}
        <button className="btn btn-primary" onClick={runSearch}>Search</button>
        <button className="btn btn-ghost" onClick={clearSearch}>Clear</button>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginBottom: 12, alignItems: "center" }}> 
        {selected.length > 0 && (
          <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>
            {selected.length} selected
          </span>
        )}

        <ActionBtn
          label="Generate invoice PDF"
          roles={PDF_ROLES}
          role={role}
          onClick={openGenerateModal}
        />

        <button className="btn btn-blue" onClick={exportRecords}>
          Export records
        </button>

        {role === "administrator" && ( 
          <button
            className="btn btn-amber"
            onClick={openBulkUpdate}
            disabled={selected.length === 0}
          >
            Bulk update status
          </button>
        )}

        {canDelete && (
          <button
            className="btn btn-danger btn-delete"
            onClick={deleteSelected}
            disabled={selected.length === 0}
            title="Delete selected invoices"
            aria-label="Delete selected invoices"
          >
            <svg
              className="btn-icon"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
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
                  {canGeneratePdf && <input type="checkbox" checked={rows.length > 0 && selected.length === rows.length} onChange={toggleAll} />}
                </th>
                <th>Invoice #</th><th>Bidder</th><th>Auctioning Company</th><th>Lots</th><th>Total amount</th><th>Due date</th><th>Status</th><th>SMS</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan={9} style={{ textAlign: "center", color: "var(--text-3)", padding: 28 }}>No records match that search</td></tr>}
              {rows.map((inv) => (
                <tr key={inv.id}>
                  <td>
                    {canGeneratePdf && <input type="checkbox" checked={selected.includes(inv.id)} onChange={() => toggleRow(inv.id)} />}
                  </td>
                  <td className="mono">
                    <span style={{ cursor: "pointer" }} onClick={() => onOpenDetail(inv.id)}>{inv.invoiceNumber}</span>
                    {inv.callNotes && (
                      <span
                        title="Has call center notes"
                        style={{ marginLeft: 6, cursor: "pointer" }}
                        onClick={(e) => {
                          e.stopPropagation();
                          alert(`Call center notes for ${inv.invoiceNumber}:\n\n${inv.callNotes}`);
                        }}
                      >
                        📎
                      </span>
                    )}
                  </td>
                  <td>{inv.bidderName}</td>
                  <td>{inv.auctionCompany || <span style={{ color: "var(--text-3)" }}>—</span>}</td>
                  <td className="mono">{inv.lots?.length || 0}</td>
                  <td className="amount">{money(inv.totalAmount.toFixed(2))}</td>
                  <td><DueDateCell invoice={inv} role={role} onChangeDueDate={changeDueDate} /></td>
                  <td><StatusCell invoice={inv} role={role} onChangeStatus={changeStatus} /></td>
                  <td>
                    {inv.smsSentAt && (
                      <div style={{ fontSize: 11.5, color: "var(--green)", marginBottom: 4 }}>
                        SMS sent ✓ {new Date(inv.smsSentAt).toLocaleDateString()}
                      </div>
                    )}
                    {canGeneratePdf && !LOCKED_STATUSES.includes(inv.status) && inv.status !== "invoice_generated" && (
                      <button className="btn btn-sm" onClick={() => onOpenSms(inv.id)}>
                        {inv.smsSentAt ? "Resend SMS" : "Send SMS"}
                      </button>
                    )}
                  </td>
                  </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <span>Showing {invoices.length} records</span>
          <div className="btns">
            <button className="btn btn-sm" onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1}>Previous</button>
            <button className="btn btn-sm" onClick={() => setCurrentPage(p => p + 1)} disabled={!hasNext}>Next</button>
          </div>
        </div>
      </div>

      <div className="locked-note" style={{ marginTop: 10 }}>
        Click an invoice number to open its full record. Click a status badge to change it directly — only available to roles allowed to make that change.
      </div>

      {showGenerateModal && (
        <GeneratePdfModal
          invoices={eligibleForPdf}
          onConfirm={confirmGeneratePdf}
          onClose={() => setShowGenerateModal(false)}
        />
      )}
      {showBulkUpdate && (
        <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) setShowBulkUpdate(false); }}>
          <div className="modal" style={{ maxWidth: 420 }}>
            <div className="modal-head">
              <h2 style={{ margin: 0 }}>Bulk update status</h2>
              <button className="modal-close" onClick={() => setShowBulkUpdate(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <div className="locked-note" style={{ marginBottom: 14 }}>
                Sets the new status on all {selected.length} selected invoices. Locked statuses (Paid,
                Cancelled, Waived) and disallowed transitions are skipped per invoice.
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {["pending_payment", "under_verification", "paid", "overdue", "cancelled", "waived"].map((s) => (
                  <button key={s} className={`status-btn ${s}`} onClick={() => confirmBulkUpdate(s)}>
                    {s.replace(/_/g, " ")}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}