export const API = `http://${window.location.hostname}:8095`;

export const authFetch = (url, options = {}) => {
  const token = localStorage.getItem('demandaflow_token');
  const headers = { ...options.headers };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (!headers['Content-Type'] && options.method !== 'GET') headers['Content-Type'] = 'application/json';

  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) {
      localStorage.removeItem('demandaflow_user');
      localStorage.removeItem('demandaflow_token');
      window.location.reload();
    }
    return res;
  });
};
