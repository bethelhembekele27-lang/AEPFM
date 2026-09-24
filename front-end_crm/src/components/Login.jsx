import { useState, useEffect, useRef } from "react";
import { demoAccounts } from "../data";
import logo from "../logo";
import { API_BASE } from "../api";

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID;

// Google's initialize() can only be called once per page load, and the callback
// it is given is frozen at that moment. If it pointed straight at a component's
// function, then after a logout and re-login it would call the OLD, unmounted
// component's setState (errors would silently not show). So initialize() gets a
// stable wrapper and each Login instance registers itself in this variable.
let googleInitialized = false;
let googleHandler = null;

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

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [googleLoading, setGoogleLoading] = useState(false);
  const googleButtonRef = useRef(null);
  const rememberRef = useRef(false);

  useEffect(() => { rememberRef.current = remember; }, [remember]);

  function completeLogin(data, rememberMe) {
    sessionStorage.setItem('authToken', data.token);
    if (rememberMe) {
      localStorage.setItem('authToken', data.token);
      localStorage.setItem('authUser', JSON.stringify({ username: data.username, role: data.role, privileges: data.privileges }));
    }
    onLogin(data.role, data.username, data.token, rememberMe, data.privileges);
  }

  async function handleGoogleCredential(response) {
    setGoogleLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/api/auth/google/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: response.credential }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setError(data.error || "Google sign-in failed.");
        return;
      }
      completeLogin(data, rememberRef.current);
    } catch (err) {
      setError("Network error. Please try again.");
      console.error(err);
    } finally {
      setGoogleLoading(false);
    }
  }

  useEffect(() => { googleHandler = handleGoogleCredential; });   // runs every render
  useEffect(() => () => { googleHandler = null; }, []);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    let timer;
    function setup() {
      if (cancelled) return;
      if (!window.google?.accounts?.id) { timer = setTimeout(setup, 100); return; }
      if (!googleInitialized) {
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (r) => googleHandler?.(r),
        });
        googleInitialized = true;
      }
      if (googleButtonRef.current) {
        googleButtonRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          theme: "outline", size: "large", width: 316, text: "signin_with",
        });
      }
    }
    setup();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  async function attemptLogin() {
    setError("");

    if (!username.trim() || !password) {
      setError("Username and password required.");
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/api/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username.trim(), password }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        setError(errorData.non_field_errors?.[0] || "Login failed");
        return;
      }

      const data = await response.json();
      completeLogin(data, remember);
    } catch (err) {
      setError("Network error. Please try again.");
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter") attemptLogin();
  }

  return (
    <div className="login-screen">
      <div className="login-card">
        <img src={logo} alt="Auction Ethiopia S.C." style={{ maxWidth: 240, width: "100%", height: "auto", objectFit: "contain", display: "block", margin: "0 auto 20px" }} />
        <h2 style={{ margin: "0 0 4px", textAlign: "center" }}>Sign in</h2>
        <div style={{ fontSize: 12.5, color: "var(--text-2)", textAlign: "center", marginBottom: 22 }}>Processing Fee Management</div>

        <label className="login-label">Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="e.g. admin"
          autoFocus
        />
        <label className="login-label" style={{ marginTop: 12 }}>Password</label>
        <div style={{ position: "relative" }}>
          <input
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Enter your password"
            style={{ paddingRight: 36 }}
          />
          <EyeToggleButton show={showPassword} onToggle={() => setShowPassword((s) => !s)} />
        </div>

        <label className="remember-row">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          Remember me on this device
        </label>

        {error && <div className="login-error">{error}</div>}

        <button className="btn btn-primary" style={{ width: "100%", marginTop: 18 }} onClick={attemptLogin}>Sign in</button>

        {GOOGLE_CLIENT_ID && (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "16px 0" }}>
              <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
              <span style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: "0.05em" }}>or</span>
              <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
            </div>
            <div style={{ display: "flex", justifyContent: "center", opacity: googleLoading ? 0.6 : 1, pointerEvents: googleLoading ? "none" : "auto" }}>
              <div ref={googleButtonRef} />
            </div>
          </>
        )}
      </div>
    </div>
  );
}