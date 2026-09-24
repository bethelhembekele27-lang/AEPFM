import { useState } from "react";
import { getAccessibleNavItems } from "../data";
import logo from "../logo";
import ProfileMenu from "./ProfileMenu";

export default function Header({ page, setPage, role, privileges, username, theme, setTheme, onLogout, onOpenAccountSettings }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const items = getAccessibleNavItems(privileges);

  const goTo = (key) => {
    setPage(key);
    setMobileNavOpen(false);
  };

  return (
    <div className="navbar">
      <div className="brand">
        <img src={logo} alt="Auction Ethiopia S.C." />
        <div className="brand-sub">Processing Fee Management</div>
      </div>
      <div className="navbar-right">
        <div className="nav">
          {items.map((n) => (
            <div key={n.key} className={"nav-item" + (page === n.key ? " active" : "")} onClick={() => goTo(n.key)}>
              {n.label}
            </div>
          ))}
        </div>
        <button
          className="hamburger-btn"
          onClick={() => setMobileNavOpen((v) => !v)}
          aria-label="Menu"
          aria-expanded={mobileNavOpen}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <ProfileMenu username={username} role={role} theme={theme} setTheme={setTheme} onLogout={onLogout} onOpenAccountSettings={onOpenAccountSettings} />
      </div>
      {mobileNavOpen && (
        <>
          <div className="mobile-nav-scrim" onClick={() => setMobileNavOpen(false)} />
          <div className="mobile-nav-panel">
            {items.map((n) => (
              <div key={n.key} className={"nav-item" + (page === n.key ? " active" : "")} onClick={() => goTo(n.key)}>
                {n.label}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}