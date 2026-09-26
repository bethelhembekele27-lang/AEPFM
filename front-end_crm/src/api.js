export const API_BASE =
  import.meta.env.VITE_API_BASE || "http://localhost:8000";

export function apiCall(endpoint, options = {}) {
  const token = sessionStorage.getItem('authToken');
  const isFormData = options.body instanceof FormData;

  const headers = {
    ...(!isFormData && { 'Content-Type': 'application/json' }),
    ...options.headers,
  };

  if (token) {
    headers.Authorization = `Token ${token}`;
  }

  return fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  }).then((res) => {
    // The server expires idle tokens after 12h (ExpiringTokenAuthentication).
    // A 401 on anything other than the login attempt itself therefore means
    // "session expired" — clear the stored credentials and bounce to login
    // rather than leaving the user on a page whose every request 401s.
    // Excluded for /auth/login so a wrong password doesn't wipe the form.
    if (res.status === 401 && !endpoint.includes('/auth/login')) {
      sessionStorage.removeItem('authToken');
      localStorage.removeItem('authToken');
      localStorage.removeItem('authUser');
      window.location.reload();
    }
    return res;
  });
}