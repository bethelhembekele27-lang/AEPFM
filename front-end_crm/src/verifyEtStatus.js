/**
 * Single source of truth for how a Verify.ET check is labelled and coloured.
 *
 * Both the queue row chip and the drawer panel call this, so they can never
 * disagree — previously the row badge said "Verified" even when the verified
 * amount didn't match what was recorded, which reads as a false all-clear.
 *
 * Order matters: a wrong-account settlement is the most serious signal, so it
 * wins over everything; then a hard "not verified"; then amount mismatch;
 * only then a clean pass.
 */
export function verifyEtStatus(check, amountPaid) {
  if (!check) return { label: "Not checked", color: "" };
  if (check.processingStatus !== "completed") {
    return { label: "Checking…", color: "under_verification" };
  }
  if (check.possibleDuplicate) {
    return { label: "Duplicate reference", color: "cancelled" };
  }
  if (check.pendingDuplicate) {
    return { label: "Also pending elsewhere", color: "pending_payment" };
  }
  if (check.settlementMatched === false) {
    return { label: "Wrong account", color: "cancelled" };
  }
  if (check.verified === false) {
    return { label: "Not verified", color: "cancelled" };
  }
  if (check.verified === true) {
    const mismatch = check.amount != null && Number(check.amount) !== Number(amountPaid);
    if (mismatch) return { label: "Amount mismatch", color: "pending_payment" };
    return { label: "Verified", color: "paid" };
  }
  return { label: "Unknown", color: "cancelled" };
}
