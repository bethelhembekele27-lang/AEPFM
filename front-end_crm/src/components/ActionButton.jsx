export function ActionBtn({ label, privKey, roles, roleOnly, role, privileges, onClick, disabled }) {
  const allowed = privKey
    ? (privileges || []).includes(privKey)
    : roleOnly
    ? role === "administrator"
    : (roles || []).includes(role);
  return (
    <button
      onClick={onClick}
      disabled={disabled || !allowed}
      className={"btn btn-sm" + (allowed ? "" : " locked")}
    >
      {label}
    </button>
  );
}