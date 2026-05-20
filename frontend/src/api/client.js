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

export async function iniciarBCP({ fechaDesde, fechaHasta, maxPdfs }) {
  const res = await fetch(`${BASE}/bcp/iniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      fecha_desde: fechaDesde,
      fecha_hasta: fechaHasta,
      max_pdfs: maxPdfs,
    }),
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
// Documentos
// ---------------------------------------------------------------------------

export async function listarDocumentos() {
  const res = await fetch(`${BASE}/documentos`)
  if (!res.ok) throw new Error('Error al listar documentos')
  return res.json()
}

export function urlDescargarTodos() {
  return `${BASE}/documentos/descargar-todos`
}

export function urlDescargarArchivo(filename) {
  return `${BASE}/documentos/${encodeURIComponent(filename)}`
}

export async function eliminarTodosDocumentos() {
  const res = await fetch(`${BASE}/documentos`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Error al eliminar documentos')
  return res.json()
}
