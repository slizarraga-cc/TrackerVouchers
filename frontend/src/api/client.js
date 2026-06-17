const BASE = '/api'

/** Extrae un mensaje legible del body de error de FastAPI. */
function extractError(body) {
  if (!body) return 'Error desconocido'
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) return body.detail.map((e) => e.msg).join(', ')
  return JSON.stringify(body)
}

export async function getConfig() {
  const res = await fetch(`${BASE}/config`)
  return res.json()
}

export async function iniciarBCP({ fecha, maxPdfs }) {
  const res = await fetch(`${BASE}/bcp/iniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fecha, max_pdfs: maxPdfs ?? null }),
  })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function confirmarLoginBCP(sessionId) {
  const res = await fetch(`${BASE}/bcp/${sessionId}/confirmar-login`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al confirmar login')
  }
  return res.json()
}

export async function cancelarBCP(sessionId) {
  const res = await fetch(`${BASE}/bcp/${sessionId}/cancelar`, { method: 'POST' })
  return res.json()
}

export async function capturarDomBCP(sessionId) {
  const res = await fetch(`${BASE}/bcp/${sessionId}/capturar-dom`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function iniciarLibreBCP() {
  const res = await fetch(`${BASE}/bcp/iniciar-libre`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function sesionActivaBCP() {
  const res = await fetch(`${BASE}/bcp/sesion-activa`)
  return res.json()
}

/**
 * Abre un EventSource SSE hacia /api/bcp/:sessionId/logs.
 * Llama onLog(msg) por cada linea de log y onStatus(status) por cada cambio de estado.
 * Retorna la instancia de EventSource para poder cerrarla.
 */
export function suscribirLogs(sessionId, onLog, onStatus) {
  const es = new EventSource(`${BASE}/bcp/${sessionId}/logs`)
  es.onmessage = (e) => onLog(e.data)
  es.addEventListener('status', (e) => onStatus(e.data))
  es.onerror = () => es.close()
  return es
}

// ---------------------------------------------------------------------------
// BBVA
// ---------------------------------------------------------------------------

export async function iniciarBBVA({ fecha, maxPdfs }) {
  const res = await fetch(`${BASE}/bbva/iniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fecha, max_pdfs: maxPdfs ?? null }),
  })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function confirmarLoginBBVA(sessionId) {
  const res = await fetch(`${BASE}/bbva/${sessionId}/confirmar-login`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al confirmar login BBVA')
  }
  return res.json()
}

export async function cancelarBBVA(sessionId) {
  const res = await fetch(`${BASE}/bbva/${sessionId}/cancelar`, { method: 'POST' })
  return res.json()
}

export async function capturarDomBBVA(sessionId) {
  const res = await fetch(`${BASE}/bbva/${sessionId}/capturar-dom`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function iniciarLibreBBVA() {
  const res = await fetch(`${BASE}/bbva/iniciar-libre`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function sesionActivaBBVA() {
  const res = await fetch(`${BASE}/bbva/sesion-activa`)
  return res.json()
}

export function suscribirLogsBBVA(sessionId, onLog, onStatus) {
  const es = new EventSource(`${BASE}/bbva/${sessionId}/logs`)
  es.onmessage = (e) => onLog(e.data)
  es.addEventListener('status', (e) => onStatus(e.data))
  es.onerror = () => es.close()
  return es
}

// ---------------------------------------------------------------------------
// IBK
// ---------------------------------------------------------------------------

export async function iniciarIBK({ fechaInicio, fechaFin, maxPdfs }) {
  const res = await fetch(`${BASE}/ibk/iniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fecha_inicio: fechaInicio, fecha_fin: fechaFin, max_pdfs: maxPdfs ?? null }),
  })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function confirmarLoginIBK(sessionId) {
  const res = await fetch(`${BASE}/ibk/${sessionId}/confirmar-login`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al confirmar login IBK')
  }
  return res.json()
}

export async function cancelarIBK(sessionId) {
  const res = await fetch(`${BASE}/ibk/${sessionId}/cancelar`, { method: 'POST' })
  return res.json()
}

export async function capturarDomIBK(sessionId) {
  const res = await fetch(`${BASE}/ibk/${sessionId}/capturar-dom`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function iniciarLibreIBK() {
  const res = await fetch(`${BASE}/ibk/iniciar-libre`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function sesionActivaIBK() {
  const res = await fetch(`${BASE}/ibk/sesion-activa`)
  return res.json()
}

export function suscribirLogsIBK(sessionId, onLog, onStatus) {
  const es = new EventSource(`${BASE}/ibk/${sessionId}/logs`)
  es.onmessage = (e) => onLog(e.data)
  es.addEventListener('status', (e) => onStatus(e.data))
  es.onerror = () => es.close()
  return es
}

export async function probarCamaraIBK() {
  const res = await fetch(`${BASE}/ibk/probar-camara`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function detenerPruebaCamaraIBK() {
  const res = await fetch(`${BASE}/ibk/probar-camara`, { method: 'DELETE' })
  return res.json()
}

// ---------------------------------------------------------------------------
// Scotiabank
// ---------------------------------------------------------------------------

export async function iniciarScotiabank({ fechaDesde, fechaHasta, maxPdfs }) {
  const res = await fetch(`${BASE}/scotiabank/iniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ fechaDesde, fechaHasta, max_pdfs: maxPdfs ?? null }),
  })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function confirmarLoginScotiabank(sessionId) {
  const res = await fetch(`${BASE}/scotiabank/${sessionId}/confirmar-login`, { method: 'POST' })
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || 'Error al confirmar login Scotiabank')
  }
  return res.json()
}

export async function cancelarScotiabank(sessionId) {
  const res = await fetch(`${BASE}/scotiabank/${sessionId}/cancelar`, { method: 'POST' })
  return res.json()
}

export async function capturarDomScotiabank(sessionId) {
  const res = await fetch(`${BASE}/scotiabank/${sessionId}/capturar-dom`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function iniciarLibreScotiabank() {
  const res = await fetch(`${BASE}/scotiabank/iniciar-libre`, { method: 'POST' })
  if (!res.ok) throw new Error(extractError(await res.json()))
  return res.json()
}

export async function sesionActivaScotiabank() {
  const res = await fetch(`${BASE}/scotiabank/sesion-activa`)
  return res.json()
}

export function suscribirLogsScotiabank(sessionId, onLog, onStatus) {
  const es = new EventSource(`${BASE}/scotiabank/${sessionId}/logs`)
  es.onmessage = (e) => onLog(e.data)
  es.addEventListener('status', (e) => onStatus(e.data))
  es.onerror = () => es.close()
  return es
}

// ---------------------------------------------------------------------------
// Camera relay (IBK)
// ---------------------------------------------------------------------------

/**
 * Abre un WebSocket al relay de cámara del servidor.
 * El servidor recibe frames JPEG y los pipa a /dev/video0 (v4l2loopback)
 * para que Chrome-IBK los lea como cámara virtual.
 */
export function conectarCameraRelay() {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${proto}//${window.location.host}/ws/camera`)
}

// ---------------------------------------------------------------------------
// Documentos
// ---------------------------------------------------------------------------

export async function listarDocumentos() {
  const res = await fetch(`${BASE}/documentos`)
  if (!res.ok) throw new Error('Error al listar documentos')
  return res.json()
}

export function urlDescargarTodos(fecha = null) {
  const base = `${BASE}/documentos/descargar-todos`
  return fecha ? `${base}?fecha=${encodeURIComponent(fecha)}` : base
}

export function urlDescargarArchivo(filename) {
  return `${BASE}/documentos/${encodeURIComponent(filename)}`
}

export async function eliminarTodosDocumentos() {
  const res = await fetch(`${BASE}/documentos`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Error al eliminar documentos')
  return res.json()
}
