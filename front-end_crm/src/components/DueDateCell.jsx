import { useState } from "react";

export default function DueDateCell({ invoice, role, privileges, onChangeDueDate }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(invoice.dueDate);
  const editable = (privileges || []).includes("extend_due_date");

  if (editing) {
    return (
      <input
        type="date"
        autoFocus
        className="mono"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => { setEditing(false); if (value !== invoice.dueDate) onChangeDueDate(invoice.id, value); }}
      />
    );
  }
  return (
    <span
      onClick={() => editable && setEditing(true)}
      title={editable ? "Click to change due date" : "Only administrators can extend due dates"}
      style={{ cursor: editable ? "pointer" : "default" }}
      className="mono"
    >
      {new Date(invoice.dueDate).toLocaleDateString()}
    </span>
  );
}