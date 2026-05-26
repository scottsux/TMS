const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

async function request(path, { method = 'GET', body, token, headers: extraHeaders } = {}) {
  const headers = { 'Content-Type': 'application/json', ...(extraHeaders || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.status === 204 ? null : res.json()
}

async function upload(path, formData, { token } = {}) {
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers, // do not set Content-Type; browser will set multipart boundary
    body: formData,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  get: (p, opts) => request(p, { ...opts, method: 'GET' }),
  post: (p, body, opts) => request(p, { ...opts, method: 'POST', body }),
  patch: (p, body, opts) => request(p, { ...opts, method: 'PATCH', body }),
  delete: (p, opts) => request(p, { ...opts, method: 'DELETE' }),
  upload,
}

export default api
