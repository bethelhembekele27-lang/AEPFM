import { useState, useEffect } from "react";
import { apiCall } from "../api";

function groupByCategory(catalog) {
  const groups = {};
  catalog.forEach((p) => {
    if (!groups[p.category]) groups[p.category] = [];
    groups[p.category].push(p);
  });
  return groups;
}

function PrivilegeGrid({ catalog, selected, onToggle, readOnly }) {
  const grouped = groupByCategory(catalog);
  return (
    <div>
      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} style={{ marginBottom: 16 }}>
          <div className="section-label" style={{ margin: "12px 0 8px" }}>{category}</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {items.map((p) => (
              <label key={p.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, cursor: readOnly ? "default" : "pointer" }}>
                <input
                  type="checkbox"
                  checked={selected.includes(p.key)}
                  onChange={() => !readOnly && onToggle(p.key)}
                  disabled={readOnly}
                  style={{ width: 15, height: 15, accentColor: "var(--brass)", flexShrink: 0 }}
                />
                {p.label}
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function NewEmployeeModal({ catalog, roles, onClose, onCreated, token }) {
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [email, setEmail] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [roleId, setRoleId] = useState(roles[0]?.id || "");
  const [privileges, setPrivileges] = useState(roles[0]?.defaultPrivileges || []);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function handleRoleChange(newRoleId) {
    setRoleId(newRoleId);
    const role = roles.find((r) => String(r.id) === String(newRoleId));
    setPrivileges(role ? [...role.defaultPrivileges] : []);
  }

  function togglePrivilege(key) {
    setPrivileges((prev) => (prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]));
  }

  async function handleCreate() {
    setError("");
    if (!fullName.trim() || !username.trim() || !password || !roleId) {
      setError("Full name, username, password, and role are required.");
      return;
    }
    setSaving(true);
    try {
      const res = await apiCall('/api/employees/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({
          fullName: fullName.trim(),
          username: username.trim(),
          email: email.trim(),
          password,
          roleId,
          privileges,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to create employee");
        return;
      }
      onCreated();
      onClose();
    } catch (err) {
      setError("Network error creating employee");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active">
      <div className="modal">
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>New employee</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field-grid">
            <div className="field">
              <div className="fl">Full name</div>
              <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
            </div>
            <div className="field">
              <div className="fl">Username</div>
              <input value={username} onChange={(e) => setUsername(e.target.value)} />
            </div>
            <div className="field">
              <div className="fl">Email <span className="opt">(needed for Google sign-in)</span></div>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <div className="fl">Temporary password</div>
              <div style={{ position: "relative" }}>
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter a temporary password"
                  style={{ paddingRight: 36 }}
                />
                <EyeToggleButton show={showPassword} onToggle={() => setShowPassword((s) => !s)} />
              </div>
            </div>
            <div className="field">
              <div className="fl">Role (template)</div>
              <select value={roleId} onChange={(e) => handleRoleChange(e.target.value)}>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
              </select>
            </div>
          </div>
          <div style={{ fontSize: 12, color: "var(--text-3)", fontStyle: "italic", marginBottom: 4 }}>
            Role sets the starting privileges below — fine-tune any of them for this specific employee.
          </div>

          <PrivilegeGrid catalog={catalog} selected={privileges} onToggle={togglePrivilege} />

          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div className="modal-actions">
            <button className="btn btn-brass" onClick={handleCreate} disabled={saving}>
              {saving ? "Creating..." : "Create account"}
            </button>
            <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function NewRoleModal({ catalog, onClose, onCreated, token }) {
  const [name, setName] = useState("");
  const [privileges, setPrivileges] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function togglePrivilege(key) {
    setPrivileges((prev) => (prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]));
  }

  async function handleCreate() {
    setError("");
    if (!name.trim()) {
      setError("Role name is required.");
      return;
    }
    setSaving(true);
    try {
      const res = await apiCall('/api/roles/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ name: name.trim(), defaultPrivileges: privileges }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to create role");
        return;
      }
      onCreated();
      onClose();
    } catch (err) {
      setError("Network error creating role");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active">
      <div className="modal">
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>New role / department</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field" style={{ marginBottom: 18 }}>
            <div className="fl">Role name</div>
            <input placeholder="e.g. Auction Doctor" value={name} onChange={(e) => setName(e.target.value)} />
          </div>

          <div className="section-label" style={{ margin: "0 0 8px" }}>Default privileges for this role</div>
          <PrivilegeGrid catalog={catalog} selected={privileges} onToggle={togglePrivilege} />

          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div className="modal-actions">
            <button className="btn btn-brass" onClick={handleCreate} disabled={saving}>
              {saving ? "Creating..." : "Create role"}
            </button>
            <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EditPrivilegesModal({ employee, catalog, onClose, onSaved, token }) {
  const [privileges, setPrivileges] = useState(employee.privileges || []);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  function togglePrivilege(key) {
    setPrivileges((prev) => (prev.includes(key) ? prev.filter((p) => p !== key) : [...prev, key]));
  }

  async function handleSave() {
    setSaving(true);
    setError("");
    try {
      const res = await apiCall(`/api/employees/${employee.id}/privileges/`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ privileges }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to save privileges");
        return;
      }
      onSaved();
      onClose();
    } catch (err) {
      setError("Network error saving privileges");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active">
      <div className="modal">
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>Edit privileges — {employee.name}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <PrivilegeGrid catalog={catalog} selected={privileges} onToggle={togglePrivilege} />
          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div className="modal-actions">
            <button className="btn btn-brass" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Save privileges"}
            </button>
            <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

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

function ResetPasswordModal({ employee, onClose, onSaved, token }) {
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    setError("");
    if (newPassword.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (newPassword !== confirm) { setError("Passwords don't match."); return; }
    setSaving(true);
    try {
      const res = await apiCall(`/api/employees/${employee.id}/reset-password/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Token ${token}` } : {}),
        },
        body: JSON.stringify({ newPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Failed to reset password");
        return;
      }
      onSaved();
      onClose();
    } catch (err) {
      setError("Network error resetting password");
      console.error(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="overlay active">
      <div className="modal" style={{ maxWidth: 420 }}>
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>Reset password — {employee.name}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field" style={{ marginBottom: 14 }}>
            <div className="fl">New password</div>
            <div style={{ position: "relative" }}>
              <input
                type={show ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                style={{ paddingRight: 36 }}
              />
              <EyeToggleButton show={show} onToggle={() => setShow((s) => !s)} />
            </div>
          </div>
          <div className="field" style={{ marginBottom: 14 }}>
            <div className="fl">Confirm new password</div>
            <input
              type={show ? "text" : "password"}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Confirm new password"
            />
          </div>
          {error && <div style={{ color: "var(--red)", marginBottom: 10, fontSize: 13 }}>{error}</div>}
          <div className="modal-actions">
            <button className="btn btn-brass" onClick={handleSave} disabled={saving}>
              {saving ? "Saving..." : "Set new password"}
            </button>
            <button className="btn" onClick={onClose} disabled={saving}>Cancel</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function EmployeePreviewModal({ employee, catalog, token, onClose, onSaved, onEditPrivileges, onResetPassword }) {
  const [email, setEmail] = useState(employee.email || "");
  const [emailError, setEmailError] = useState("");
  const [savingEmail, setSavingEmail] = useState(false);

  async function saveEmail() {
    setEmailError("");
    setSavingEmail(true);
    try {
      const res = await apiCall(`/api/employees/${employee.id}/email/`, {
        method: 'PATCH',
        headers: token ? { Authorization: `Token ${token}` } : {},
        body: JSON.stringify({ email: email.trim() }),
      });
      const data = await res.json();
      if (!res.ok) { setEmailError(data.error || "Failed to save email"); return; }
      onSaved();
      onClose();
    } catch (err) {
      setEmailError("Network error saving email");
      console.error(err);
    } finally {
      setSavingEmail(false);
    }
  }

  return (
    <div className="overlay active">
      <div className="modal">
        <div className="modal-head">
          <h3 style={{ margin: 0 }}>{employee.name}</h3>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="field-grid">
            <div className="field"><div className="fl">Username</div><div className="fv mono">{employee.username}</div></div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <div className="fl">Email (used for Google sign-in)</div>
              <div style={{ display: "flex", gap: 8 }}>
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
                <button className="btn btn-sm btn-brass" onClick={saveEmail} disabled={savingEmail || email.trim() === (employee.email || "")}>
                  {savingEmail ? "Saving..." : "Save"}
                </button>
              </div>
              {emailError && <div style={{ color: "var(--red)", fontSize: 12, marginTop: 4 }}>{emailError}</div>}
            </div>
            <div className="field"><div className="fl">Role</div><div className="fv">{employee.roleName}</div></div>
            <div className="field"><div className="fl">Status</div><span className={`stamp ${employee.isActive ? "paid" : "cancelled"}`}>{employee.isActive ? "Active" : "Inactive"}</span></div>
            <div className="field"><div className="fl">Last password change</div><div className="fv">{employee.lastPasswordChangedBy || <span style={{ color: "var(--text-3)" }}>—</span>}</div></div>
            <div className="field"><div className="fl">Last username change</div><div className="fv">{employee.lastUsernameChangedBy || <span style={{ color: "var(--text-3)" }}>—</span>}</div></div>
          </div>

          <div className="section-label">Privileges ({employee.privilegeCount})</div>
          <PrivilegeGrid catalog={catalog} selected={employee.privileges || []} onToggle={() => {}} readOnly />

          <div className="modal-actions">
            <button className="btn btn-brass" onClick={onEditPrivileges}>Edit privileges</button>
            <button className="btn" onClick={onResetPassword}>Reset password</button>
            <button className="btn btn-ghost" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Employees({ role, token }) {
  const [employees, setEmployees] = useState([]);
  const [roles, setRoles] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showNewEmployee, setShowNewEmployee] = useState(false);
  const [showNewRole, setShowNewRole] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState(null);
  const [previewEmployee, setPreviewEmployee] = useState(null);
  const [resetPwEmployee, setResetPwEmployee] = useState(null);
  const [selected, setSelected] = useState([]);

  const canManage = role === "administrator";

  useEffect(() => { fetchAll(); }, []);

  async function fetchAll() {
    setLoading(true);
    setError("");
    try {
      const [empRes, roleRes, catRes] = await Promise.all([
        apiCall('/api/employees/', { headers: token ? { Authorization: `Token ${token}` } : {} }),
        apiCall('/api/roles/', { headers: token ? { Authorization: `Token ${token}` } : {} }),
        apiCall('/api/privileges/', { headers: token ? { Authorization: `Token ${token}` } : {} }),
      ]);
      const [empData, roleData, catData] = await Promise.all([empRes.json(), roleRes.json(), catRes.json()]);
      if (!empRes.ok || !roleRes.ok || !catRes.ok) {
        setError("Failed to load employees/roles data");
        return;
      }
      setEmployees(empData);
      setRoles(roleData);
      setCatalog(catData);
    } catch (err) {
      setError("Network error loading employees/roles");
      console.error(err);
    } finally {
      setLoading(false);
    }
  }

  function toggleRow(id) {
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function toggleAll() {
    setSelected(selected.length === employees.length ? [] : employees.map((e) => e.id));
  }

  async function bulkDeactivate() {
    if (selected.length === 0) return;
    if (!window.confirm(`Deactivate ${selected.length} employee${selected.length > 1 ? "s" : ""}? They will no longer be able to log in.`)) return;
    try {
      const res = await apiCall('/api/employees/bulk-deactivate/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ employeeIds: selected }),
      });
      if (!res.ok) { setError("Failed to deactivate selected employees"); return; }
      setSelected([]);
      await fetchAll();
    } catch (err) {
      setError("Network error deactivating employees");
      console.error(err);
    }
  }

  async function bulkDelete() {
    if (selected.length === 0) return;
    if (!window.confirm(`Delete ${selected.length} employee${selected.length > 1 ? "s" : ""}? This cannot be undone.`)) return;
    try {
      const res = await apiCall('/api/employees/bulk-delete/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
        body: JSON.stringify({ employeeIds: selected }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Failed to delete selected employees"); return; }
      setSelected([]);
      await fetchAll();
    } catch (err) {
      setError("Network error deleting employees");
      console.error(err);
    }
  }

  async function deleteRole(r) {
    if (!window.confirm(`Delete the "${r.name}" role? This cannot be undone.`)) return;
    try {
      const res = await apiCall(`/api/roles/${r.id}/`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Token ${token}` } : {},
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.error || "Failed to delete role");
        return;
      }
      await fetchAll();
    } catch (err) {
      setError("Network error deleting role");
      console.error(err);
    }
  }
  async function bulkActivate() {
      if (selected.length === 0) return;
      try {
        const res = await apiCall('/api/employees/bulk-activate/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Token ${token}` } : {}) },
          body: JSON.stringify({ employeeIds: selected }),
        });
        if (!res.ok) { setError("Failed to activate selected employees"); return; }
        setSelected([]);
        await fetchAll();
      } catch (err) {
        setError("Network error activating employees");
        console.error(err);
      }
    }

  if (!canManage) {
    return (
      <div className="card">
        <h3 style={{ margin: "0 0 6px" }}>Employees & roles</h3>
        <div className="locked-note">Only Administrators can manage employee accounts and privileges.</div>
      </div>
    );
  }

  if (loading) return <div style={{ padding: 20 }}>Loading...</div>;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {selected.length > 0 && (() => {
            const selectedEmployees = employees.filter((e) => selected.includes(e.id));
            const allInactive = selectedEmployees.every((e) => !e.isActive);
            return (
              <>
                <span style={{ fontSize: 12.5, color: "var(--text-2)" }}>{selected.length} selected</span>
                {selected.length === 1 && (
                  <button className="btn btn-sm" onClick={() => setEditingEmployee(selectedEmployees[0])}>
                    Edit privileges
                  </button>
                )}
                <button className="btn btn-amber btn-sm" onClick={allInactive ? bulkActivate : bulkDeactivate}>
                  {allInactive ? "Activate" : "Deactivate"}
                </button>
                <button className="btn btn-danger btn-sm" onClick={bulkDelete}>Delete</button>
              </>
            );
          })()}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-brass" onClick={() => setShowNewEmployee(true)}>New employee</button>
          <button className="btn btn-primary" onClick={() => setShowNewRole(true)}>New role</button>
        </div>
      </div>

      {error && <div style={{ color: "var(--red)", marginBottom: 12, fontSize: 13 }}>{error}</div>}

      <div className="tbl-wrap">
        <div style={{ overflowX: "auto" }}>
          <table>
            <thead>
              <tr>
                <th style={{ width: 32 }}>
                  <input type="checkbox" checked={employees.length > 0 && selected.length === employees.length} onChange={toggleAll} />
                </th>
                <th>Name</th>
                <th>Username</th>
                <th>Role</th>
                <th>Status</th>
                <th>Last password change</th>
                <th>Last username change</th>
                <th>Privileges</th>
                
              </tr>
            </thead>
            <tbody>
              {employees.map((emp) => (
                <tr key={emp.id}>
                  <td><input type="checkbox" checked={selected.includes(emp.id)} onChange={() => toggleRow(emp.id)} /></td>
                  <td style={{ cursor: "pointer", color: "var(--brass-dark)" }} onClick={() => setPreviewEmployee(emp)}>{emp.name}</td>
                  <td className="mono">{emp.username}</td>
                  <td>{emp.roleName}</td>
                  <td><span className={`stamp ${emp.isActive ? "paid" : "cancelled"}`}>{emp.isActive ? "Active" : "Inactive"}</span></td>
                  <td>{emp.lastPasswordChangedBy || <span style={{ color: "var(--text-3)" }}>—</span>}</td>
                  <td>{emp.lastUsernameChangedBy || <span style={{ color: "var(--text-3)" }}>—</span>}</td>
                  <td className="mono">{emp.privilegeCount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h3 style={{ margin: "0 0 12px" }}>Roles</h3>
        <div className="tbl-wrap">
          <div style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Default privileges</th>
                  <th>Type</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {roles.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td className="mono">{r.privilegeCount}/{catalog.length} default privileges</td>
                    <td style={{ color: "var(--text-3)" }}>
                      {r.isBuiltIn ? <span className="badge-note">Built-in</span> : "Custom"}
                    </td>
                    <td>
                      {!r.isBuiltIn && (
                        <button className="btn btn-sm btn-danger" onClick={() => deleteRole(r)}>Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {showNewEmployee && (
        <NewEmployeeModal catalog={catalog} roles={roles} token={token} onClose={() => setShowNewEmployee(false)} onCreated={fetchAll} />
      )}
      {showNewRole && (
        <NewRoleModal catalog={catalog} token={token} onClose={() => setShowNewRole(false)} onCreated={fetchAll} />
      )}
      {editingEmployee && (
        <EditPrivilegesModal employee={editingEmployee} catalog={catalog} token={token} onClose={() => setEditingEmployee(null)} onSaved={fetchAll} />
      )}
      {previewEmployee && (
        <EmployeePreviewModal
          employee={previewEmployee}
          catalog={catalog}
          token={token}
          onClose={() => setPreviewEmployee(null)}
          onSaved={fetchAll}
          onEditPrivileges={() => { setEditingEmployee(previewEmployee); setPreviewEmployee(null); }}
          onResetPassword={() => { setResetPwEmployee(previewEmployee); setPreviewEmployee(null); }}
        />
      )}
      {resetPwEmployee && (
        <ResetPasswordModal employee={resetPwEmployee} token={token} onClose={() => setResetPwEmployee(null)} onSaved={fetchAll} />
      )}
    </div>
  );
}