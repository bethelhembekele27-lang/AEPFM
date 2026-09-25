import { useState } from "react";
import { apiCall } from "../api";

function EyeToggleButton({ show, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label={show ? "Hide password" : "Show password"}
      style={{
        position: "absolute", right: 6, top: "50%", transform: "translateY(-50%)",
        background: "none", border: "none", cursor: "pointer", color: "var(--text-3)",
        display: "flex", alignItems: "center", padding: 4,
      }}
    >
      {show ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.4 18.4 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      )}
    </button>
  );
}

export default function AccountSettingsModal({ username, token, onSave, onClose }) {
  const [name, setName] = useState(username);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showOld, setShowOld] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setError("");
    if (newPassword && newPassword !== confirmPassword) { setError("New passwords don't match."); return; }
    if (newPassword && !oldPassword) { setError("Enter your current password to set a new one."); return; }
    if (!name.trim()) { setError("Name can't be empty."); return; }

    setSaving(true);
    try {
      const authHeaders = { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) };

      const profileRes = await apiCall('/api/account/profile/', {
        method: 'PATCH',
        headers: authHeaders,
        body: JSON.stringify({ displayName: name.trim() }),
      });
      const profileData = await profileRes.json();
      if (!profileRes.ok) { setError(profileData.error || "Failed to save profile"); return; }

      if (newPassword) {
        const pwRes = await apiCall('/api/account/change-password/', {
          method: 'PATCH',
          headers: authHeaders,
          body: JSON.stringify({ oldPassword, newPassword }),
        });
        const pwData = await pwRes.json();
        if (!pwRes.ok) { setError(pwData.error || "Failed to change password"); return; }
      }

      onSave(profileData.displayName || name.trim());
      setSaved(true);
      setTimeout(onClose, 900);
    } catch (err) {
      setError("Network error saving profile");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: 440 }}>
        <div className="modal-head">
          <h2 style={{ margin: 0 }}>Edit profile</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <label className="login-label">Display name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} style={{ marginBottom: 14 }} />

          <label className="login-label">Current password <span style={{ color: "var(--text-3)", textTransform: "none" }}>(required to change password)</span></label>
          <div style={{ position: "relative", marginBottom: 14 }}>
<input
               type={showOld ? "text" : "password"}
               value={oldPassword}
               onChange={(e) => setOldPassword(e.target.value)}
               placeholder="Enter your current password"
               autoComplete="current-password"
               style={{ paddingRight: 36 }}
             />
            <EyeToggleButton show={showOld} onToggle={() => setShowOld((s) => !s)} />
          </div>

          <label className="login-label">New password <span style={{ color: "var(--text-3)", textTransform: "none" }}>(leave blank to keep current)</span></label>
          <div style={{ position: "relative", marginBottom: 14 }}>
<input
               type={showNew ? "text" : "password"}
               value={newPassword}
               onChange={(e) => setNewPassword(e.target.value)}
               placeholder="Enter new password"
               autoComplete="new-password"
               style={{ paddingRight: 36 }}
             />
            <EyeToggleButton show={showNew} onToggle={() => setShowNew((s) => !s)} />
          </div>

          <label className="login-label">Confirm new password</label>
<input
             type={showNew ? "text" : "password"}
             value={confirmPassword}
             onChange={(e) => setConfirmPassword(e.target.value)}
             placeholder="Confirm new password"
             autoComplete="new-password"
             style={{ marginBottom: 14 }}
           />

          {error && <div className="login-error" style={{ marginBottom: 12 }}>{error}</div>}
          {saved && <div className="login-success" style={{ marginBottom: 12 }}>Saved.</div>}
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-brass" onClick={handleSave} disabled={saving}>{saving ? "Saving..." : "Save changes"}</button>
            <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}