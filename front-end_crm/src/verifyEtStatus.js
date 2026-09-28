export function verifyEtStatus(check, amountDue) {
  if (!check) return { label: "Not checked", color: "" };
  if (check.processingStatus === "failed") return { label: "Check failed", color: "cancelled" };
  if (check.processingStatus !== "completed") return { label: "Checking…", color: "under_verification" };
  if (check.possibleDuplicate) return { label: "Duplicate reference", color: "cancelled" };
  if (check.pendingDuplicate) return { label: "Also pending elsewhere", color: "pending_payment" };
  if (check.verified === false) return { label: "Not verified", color: "cancelled" };
  if (check.settlementMatched === false) return { label: "Wrong account", color: "cancelled" };
  if (check.verified === true) {
    if (check.settlementMatched !== true) return { label: "Account unconfirmed", color: "pending_payment" };
    const diff = Number(check.amount) - Number(amountDue);
    if (amountDue != null && diff < -1) return { label: "Underpaid", color: "cancelled" };
    if (amountDue != null && diff > 1) return { label: "Overpaid", color: "pending_payment" };
    return { label: "Verified", color: "paid" };
  }
  return { label: "Unknown", color: "cancelled" };
}
