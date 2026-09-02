export const API = `http://${window.location.hostname}:8095`;

export const authFetch = (url, options = {}) => {
  const token = sessionStorage.getItem('demandaflow_token');
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  // FormData needs the browser to set its own multipart boundary — never
  // force JSON on top of it, or the upload comes out unparseable server-side.
  if (!headers['Content-Type'] && options.method !== 'GET' && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
  }

  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) {
      sessionStorage.removeItem('demandaflow_user');
      sessionStorage.removeItem('demandaflow_token');
      window.location.reload();
    }
    return res;
  });
};
