export const statusLabels = {
  invoice_generated: "Draft",
  pending_payment: "Pending Payment",
  payment_submitted: "Payment Submitted",
  under_verification: "Under Verification",
  paid: "Paid",
  overdue: "Overdue",
  cancelled: "Cancelled",
  waived: "Waived",
};

export const statusCounts = {
  invoice_generated: 20, pending_payment: 25, payment_submitted: 12, under_verification: 8,
  paid: 55, overdue: 8, cancelled: 2, waived: 0,
};

export const LOCKED_STATUSES = ["paid", "cancelled", "waived"];

export const roleLabels = {
  administrator: "Administrator",
  auction_manager: "Auction Manager",
  finance_manager: "Finance Manager",
  call_operator: "CRM / Call Center Officer",
  viewer: "Viewer",
};

export const navItems = [
  { key: "dashboard", label: "Financial dashboard", sub: "" },
  { key: "import", label: "Import batches", sub: "" },
  { key: "operations", label: "Operations", sub: "" },
  { key: "receipts", label: "Verify receipts", sub: "" },
  { key: "queues", label: "Operational queues", sub: "" },
  { key: "reports", label: "Reports", sub: "" },
  { key: "callcenter", label: "Call center" },
  { key: "audit", label: "Audit trail", sub: "" },
  { key: "employees", label: "Employees" },
];

// Which privilege(s) each page requires — any one is enough. null means
// "no restriction, any logged-in employee." Kept here so the nav bar and
// each page component agree on who can see what.
export const pagePrivileges = {
  dashboard: ["view_dashboard"],
  import: null,
  operations: null,
  queues: ["view_invoices"],
  reports: ["view_reports"],
  callcenter: null,
  receipts: ["manager_verify_receipt", "verify_payment"],
  audit: ["view_audit"],
  employees: ["manage_users"],
};

export function canAccessPage(pageKey, privileges) {
  const required = pagePrivileges[pageKey];
  if (!required) return true;
  const owned = privileges || [];
  return required.some((p) => owned.includes(p));
}

export function getAccessibleNavItems(privileges) {
  return navItems.filter((n) => canAccessPage(n.key, privileges));
}

export function getDefaultPage(privileges) {
  const accessible = getAccessibleNavItems(privileges);
  return accessible.length > 0 ? accessible[0].key : null;
}



export const money = (n) =>
  "ETB " + Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const batches = [
  { id: 1, fileName: "bid_data_report_q3.xlsx", batchName: "Ethio Telecom Q3 2026", companyName: "Ethio Telecom", auctionDate: "2026-06-11", uploadDate: "2026-07-16", status: "confirmed", totalRecords: 45, validRecords: 45, importedBy: "Sara Admin" },
  { id: 2, fileName: "bid_data_report_customs.xlsx", batchName: "", companyName: "Addis Ababa Airport Customs", auctionDate: "2026-07-02", uploadDate: "2026-07-18", status: "confirmed", totalRecords: 18, validRecords: 18, importedBy: "K. Novak" },
];

export function batchLabel(batchId) {
  const b = batches.find((x) => x.id === batchId);
  return b ? (b.batchName || b.companyName) : "—";
}

const rawInvoiceSeed = [
  { inv: "INV-2026-1042", batchId: 1, bidderName: "J. Whitfield", companyName: "Whitfield Holdings", winnerPhone: "251911002233", status: "under_verification", invoiceDate: "2026-07-08", dueDate: "2026-07-22", feePercentage: "5.00", remarks: "Bidder requested extended review window.", verifiedBy: "—",
    lots: [
      { lotNumber: "AE-3391", auctionName: "Spring Classic Cars — Lot 4", winningAmount: "22400.00", feePercentage: "5.00", lotFee: "1120.00" },
      { lotNumber: "AE-3392", auctionName: "Spring Classic Cars — Lot 7", winningAmount: "15800.00", feePercentage: "5.00", lotFee: "790.00" },
    ] },
  { inv: "INV-2026-1043", batchId: 2, bidderName: "R. Delgado", companyName: "", winnerPhone: "251955667788", status: "paid", invoiceDate: "2026-07-05", dueDate: "2026-07-19", feePercentage: "5.00", remarks: "", verifiedBy: "A. Costa",
    lots: [{ lotNumber: "AE-4012", auctionName: "Estate Jewelry Lot 12", winningAmount: "20400.00", feePercentage: "5.00", lotFee: "1020.00" }] },
  { inv: "INV-2026-1044", batchId: 1, bidderName: "Marchetti Estates", companyName: "Marchetti Estates", winnerPhone: "251911998811", status: "overdue", invoiceDate: "2026-06-28", dueDate: "2026-07-12", feePercentage: "4.00", remarks: "Second reminder sent 07-14.", verifiedBy: "—",
    lots: [{ lotNumber: "AE-2210", auctionName: "Vintage Watches — Lot 2", winningAmount: "29800.00", feePercentage: "4.00", lotFee: "1192.00" }] },
  { inv: "INV-2026-1045", batchId: 2, bidderName: "T. Hollis", companyName: "", winnerPhone: "251933445566", status: "pending_payment", invoiceDate: "2026-07-11", dueDate: "2026-07-25", feePercentage: "5.00", remarks: "", verifiedBy: "—",
    lots: [{ lotNumber: "AE-5501", auctionName: "Modern Art Sale — Lot 9", winningAmount: "15600.00", feePercentage: "5.00", lotFee: "780.00" }] },
  { inv: "INV-2026-1046", batchId: 1, bidderName: "P. Adeyemi", companyName: "", winnerPhone: "251977889900", status: "payment_submitted", invoiceDate: "2026-07-14", dueDate: "2026-07-28", feePercentage: "5.00", remarks: "Receipt uploaded, awaiting review.", verifiedBy: "—",
    lots: [
      { lotNumber: "AE-6001", auctionName: "Rare Books — Lot 1", winningAmount: "3300.00", feePercentage: "5.00", lotFee: "165.00" },
      { lotNumber: "AE-6002", auctionName: "Rare Books — Lot 2", winningAmount: "2900.00", feePercentage: "5.00", lotFee: "145.00" },
      { lotNumber: "AE-6003", auctionName: "Rare Books — Lot 3", winningAmount: "2100.00", feePercentage: "5.00", lotFee: "105.00" },
    ] },
  { inv: "INV-2026-1047", batchId: 1, bidderName: "L. Fontaine", companyName: "", winnerPhone: "251922334455", status: "invoice_generated", invoiceDate: "2026-07-09", dueDate: "2026-07-23", feePercentage: "5.00", remarks: "", verifiedBy: "—",
    lots: [{ lotNumber: "AE-3395", auctionName: "Spring Classic Cars — Lot 11", winningAmount: "44500.00", feePercentage: "5.00", lotFee: "2225.00" }] },
  { inv: "INV-2026-1048", batchId: 2, bidderName: "S. Okafor", companyName: "", winnerPhone: "251944556677", status: "waived", invoiceDate: "2026-06-30", dueDate: "2026-07-14", feePercentage: "5.00", remarks: "Fee waived — repeat client goodwill gesture.", verifiedBy: "A. Costa",
    lots: [{ lotNumber: "AE-4020", auctionName: "Estate Jewelry Lot 12 — Lot 6", winningAmount: "12900.00", feePercentage: "5.00", lotFee: "645.00" }] },
  { inv: "INV-2026-1049", batchId: 1, bidderName: "D. Berg", companyName: "", winnerPhone: "251988990011", status: "cancelled", invoiceDate: "2026-07-13", dueDate: "2026-07-27", feePercentage: "4.00", remarks: "Winner withdrew, item relisted.", verifiedBy: "—",
    lots: [{ lotNumber: "AE-2215", auctionName: "Vintage Watches — Lot 5", winningAmount: "19200.00", feePercentage: "4.00", lotFee: "768.00" }] },
];

export const invoicesSeed = rawInvoiceSeed.map((inv) => ({
  ...inv,
  totalAmount: inv.lots.reduce((sum, l) => sum + parseFloat(l.lotFee), 0).toFixed(2),
}));

export const demoAccounts = [
  { username: "admin", password: "admin123", role: "administrator" },
  { username: "auction", password: "auction123", role: "auction_manager" },
  { username: "finance", password: "finance123", role: "finance_manager" },
  { username: "callcenter", password: "call123", role: "call_operator" },
  { username: "viewer", password: "viewer123", role: "viewer" },
];

export const auditLog = [
  { d: "2026-07-19", t: "14:22", u: "K. Novak", r: "CRM / Call Center Officer", a: "Add remarks", pv: "—", nv: "Receipt uploaded, awaiting review.", rs: "Bidder submitted receipt via email", ip: "—" },
  { d: "2026-07-18", t: "09:47", u: "A. Costa", r: "Finance Manager", a: "Mark payment settled", pv: "payment_submitted", nv: "paid", rs: "Bank transfer confirmed", ip: "172.16.4.22" },
  { d: "2026-07-17", t: "16:03", u: "A. Costa", r: "Finance Manager", a: "Verify transaction", pv: "payment_submitted", nv: "under_verification", rs: "Reference FT261458ZWL3 matched", ip: "172.16.4.22" },
  { d: "2026-07-16", t: "11:12", u: "System", r: "—", a: "Mark overdue", pv: "pending_payment", nv: "overdue", rs: "Due date passed with no payment", ip: "—" },
  { d: "2026-07-16", t: "10:00", u: "Sara Admin", r: "Administrator", a: "Confirm import batch", pv: "—", nv: "45 invoices created (batch #1)", rs: "Ethio Telecom Q3 2026 bid data reviewed", ip: "10.0.0.14" },
  { d: "2026-07-15", t: "10:30", u: "S. Iyer", r: "Administrator", a: "Waive processing fee", pv: "pending_payment", nv: "waived", rs: "Repeat client goodwill gesture", ip: "10.0.0.14" },
];

export const searchFieldDefs = {
  bidderName: { label: "bidder name", type: "text" },
  phoneNumber: { label: "phone number", type: "text" },
  auctionCompany: { label: 'Auctioning company', type: 'text' },
  lotNo: { label: "lot number", type: "text" },
  batchId: { label: "import batch", type: "select", options: batches.map((b) => ({ v: String(b.id), l: b.batchName || b.companyName })) },
  status: { label: "payment status", type: "select", options: Object.keys(statusLabels).map((k) => ({ v: k, l: statusLabels[k] })) },
  daterange: { label: "date range", type: "daterange" },
};

export const periodLabels = { today: "Today", week: "This week", month: "This month", year: "This year" };
export const receivedByPeriod = { today: "6,340.00", week: "18,920.00", month: "97,880.00", year: "612,400.00" };

export const statusCountsByPeriod = {
  today: { invoice_generated: 2, pending_payment: 3, payment_submitted: 1, under_verification: 1, paid: 4, overdue: 0, cancelled: 0, waived: 0 },
  week: { invoice_generated: 6, pending_payment: 9, payment_submitted: 4, under_verification: 3, paid: 14, overdue: 2, cancelled: 0, waived: 0 },
  month: statusCounts,
  year: { invoice_generated: 38, pending_payment: 52, payment_submitted: 24, under_verification: 15, paid: 340, overdue: 19, cancelled: 9, waived: 3 },
};

// Which roles may move an invoice to a new status. Locked statuses (paid/cancelled/waived)
// can only be changed by an administrator override, matching the spec.
export function canChangeStatus(invoice, privileges, role) {
  if (LOCKED_STATUSES.includes(invoice.status)) return role === "administrator"; // override_status stays admin-only, not in the catalog
  return (privileges || []).includes("change_status_generic");
}

// Permission logic for the action buttons on an invoice (Verify, Reject,
// Mark paid, etc). Lives here alongside canChangeStatus since both are
// permission/data logic, not presentational — ActionButton.jsx only holds
// the actual <button> components now.
//
// Entries carry either `privKey` (checked against session privileges) or an
// explicit `roleOnly`/`roles` marker for the few actions that still have no
// catalog key. Grep for "roleOnly:" or "roles:" to list what is deliberately
// still role-gated.
export function actionDefsFor(inv, privileges, role) {
  if (LOCKED_STATUSES.includes(inv.status)) {
    return [{ label: "Override status", roleOnly: true }];
  }
  const btns = [];
  if (inv.status === "invoice_generated") btns.push({ label: "Generate invoice PDF", privKey: "generate_invoice" });
  if (inv.status === "invoice_generated" || inv.status === "pending_payment") btns.push({ label: "Upload receipt", privKey: "upload_payment_proof" });
  if (inv.status === "payment_submitted") {
    btns.push({ label: "Verify transaction", privKey: "change_status_generic" });
    btns.push({ label: "Reject", privKey: "change_status_generic" });
  }
  btns.push({ label: "Mark paid", privKey: "change_status_generic" });
  btns.push({ label: "Mark overdue", privKey: "change_status_generic" });
  if (inv.status === "overdue") btns.push({ label: "Extend due date", privKey: "extend_due_date" });
  btns.push({ label: "Remarks", roles: ["administrator", "auction_manager", "finance_manager", "call_operator"] });
  return btns;
}