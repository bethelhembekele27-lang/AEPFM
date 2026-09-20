import { useState } from "react";
import { apiCall } from "../api";

export default function NewWinnerModal({ onClose, onCreated, token }) {
  const [bidderName, setBidderName] = useState("");
  const [winnerPhone, setWinnerPhone] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [lots, setLots] = useState([{ lotNumber: "", auctionName: "", winningAmount: "" }]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function updateLot(i, field, value) {
    setLots((prev) => prev.map((l, idx) => idx === i ? { ...l, [field]: value } : l));
  }
  function addLot() {
    setLots((prev) => [...prev, { lotNumber: "", auctionName: "", winningAmount: "" }]);
  }
  function removeLot(i) {
    setLots((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function handleCreate() {
    setError("");
    if (!bidderName.trim() || !winnerPhone.trim()) { setError("Bidder name and phone are required."); return; }
    if (lots.some((l) => !l.lotNumber || !l.winningAmount)) { setError("Every lot needs a lot number and winning amount."); return; }

    setSaving(true);
    try {
      const res = await apiCall('/api/winners/manual/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ bidderName, winnerPhone, companyName, lots }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Failed to create winner"); return; }
      onCreated();
      onClose();
    } catch (err) {
      setError("Network error creating winner");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-head">
          <h2 style={{ margin: 0 }}>New winner</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field-grid">
            <div className="field"><div className="fl">Bidder name</div><input value={bidderName} onChange={(e) => setBidderName(e.target.value)} /></div>
            <div className="field"><div className="fl">Phone</div><input value={winnerPhone} onChange={(e) => setWinnerPhone(e.target.value)} placeholder="e.g. 0911234567" /></div>
            <div className="field" style={{ gridColumn: "1 / -1" }}><div className="fl">Company <span className="opt">(optional)</span></div><input value={companyName} onChange={(e) => setCompanyName(e.target.value)} /></div>
          </div>

          <div className="section-label">Lots</div>
          {lots.map((lot, i) => (
            <div key={i} className="field-grid" style={{ marginBottom: 8, alignItems: "end" }}>
              <div className="field"><div className="fl">Lot #</div><input value={lot.lotNumber} onChange={(e) => updateLot(i, "lotNumber", e.target.value)} /></div>
              <div className="field"><div className="fl">Auction</div><input value={lot.auctionName} onChange={(e) => updateLot(i, "auctionName", e.target.value)} /></div>
              <div className="field"><div className="fl">Winning amount</div><input type="number" step="0.01" value={lot.winningAmount} onChange={(e) => updateLot(i, "winningAmount", e.target.value)} /></div>
              {lots.length > 1 && <button className="btn btn-sm btn-danger" onClick={() => removeLot(i)}>Remove</button>}
            </div>
          ))}
          <button className="btn btn-sm" style={{ marginBottom: 14 }} onClick={addLot}>+ Add lot</button>

          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-brass" onClick={handleCreate} disabled={saving}>{saving ? "Creating..." : "Create winner & invoice"}</button>
            <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}
