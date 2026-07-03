import { useState, useEffect, useRef } from 'react'
import { iniciarBCP2, confirmarLoginBCP2, cancelarBCP2, capturarDomBCP2, iniciarLibreBCP2, suscribirLogsBCP2, getConfig, sesionActivaBCP2 } from '../api/client'
import { LogsPanel } from './LogsPanel'

/** Retorna el ultimo dia laborable anterior a hoy en timezone Lima (YYYY-MM-DD). */
function ultimoDiaLaborable() {
  const limaHoy = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Lima' })
  const [y, m, d] = limaHoy.split('-').map(Number)
  const ayer = new Date(y, m - 1, d - 1)
  const dow = ayer.getDay()
  if (dow === 6) ayer.setDate(ayer.getDate() - 1)
  if (dow === 0) ayer.setDate(ayer.getDate() - 2)
  const yy = ayer.getFullYear()
  const mm = String(ayer.getMonth() + 1).padStart(2, '0')
  const dd = String(ayer.getDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

/** "YYYY-MM-DD" → "DD/MM/YYYY" */
function toDisplayDate(htmlDate) {
  if (!htmlDate) return ''
  const [y, m, d] = htmlDate.split('-')
  return `${d}/${m}/${y}`
}

const STATUS_LABELS = {
  iniciando:        'Conectando al navegador...',
  esperando_login:  'Esperando login manual',
  ejecutando:       'Descargando comprobantes...',
  completado:       'Completado',
  error:            'Error',
  cancelado:        'Cancelado',
  libre:            'Modo libre — navegador activo',
}

const STATUS_COLORS = {
  iniciando:       'var(--warn-text)',
  esperando_login: 'var(--warn-text)',
  ejecutando:      'var(--info-text)',
  completado:      'var(--success-text)',
  error:           'var(--error-text)',
  cancelado:       'var(--text-muted)',
  libre:           'var(--warn-text)',
}

export function BCP2Panel() {
  const [fecha,   setFecha]   = useState(ultimoDiaLaborable)
  const [maxPdfs, setMaxPdfs] = useState('')

  const [sessionId,    setSessionId]    = useState(null)
  const [status,       setStatus]       = useState(null)
  const [logs,         setLogs]         = useState([])
  const [resultado,    setResultado]    = useState(null)
  const [apiError,     setApiError]     = useState(null)
  const [vncUrl,       setVncUrl]       = useState('')
  const [vncFullscreen, setVncFullscreen] = useState(false)
  const [domCapturado, setDomCapturado] = useState(null)
  const [capturando,   setCapturando]   = useState(false)

  const esRef = useRef(null)

  useEffect(() => {
    getConfig().then((cfg) => {
      const base = window.location.origin
      setVncUrl(
        `${base}/vnc/bcp2/vnc.html?autoconnect=1&resize=scale&password=${cfg.vnc_password}&path=vnc/bcp2/`
      )
    })

    sesionActivaBCP2().then((data) => {
      if (data.session_id) {
        setSessionId(data.session_id)
        setStatus(data.status)
        if (data.resultado !== null) setResultado(data.resultado)
      }
    }).catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setVncFullscreen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (!sessionId) return
    esRef.current = suscribirLogsBCP2(
      sessionId,
      (msg) => setLogs((prev) => [...prev, msg]),
      (newStatus) => {
        setStatus(newStatus)
        if (['completado', 'error', 'cancelado'].includes(newStatus)) {
          esRef.current?.close()
        }
      }
    )
    return () => esRef.current?.close()
  }, [sessionId])

  const isActive    = status && !['completado', 'error', 'cancelado'].includes(status)
  const showVnc     = ['esperando_login', 'ejecutando', 'libre'].includes(status)

  async function handleIniciar(e) {
    e.preventDefault()
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarBCP2({
        fecha: toDisplayDate(fecha),
        maxPdfs: maxPdfs !== '' ? Number(maxPdfs) : null,
      })
      setSessionId(data.session_id)
      setStatus(data.status)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleConfirmarLogin() {
    setApiError(null)
    try {
      await confirmarLoginBCP2(sessionId)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleIniciarLibre() {
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarLibreBCP2()
      setSessionId(data.session_id)
      setStatus(data.status)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleCancelar() {
    if (sessionId) await cancelarBCP2(sessionId)
    reset()
  }

  async function handleCapturarDom() {
    if (!sessionId) return
    setCapturando(true)
    setDomCapturado(null)
    try {
      const data = await capturarDomBCP2(sessionId)
      setDomCapturado(data)
    } catch (err) {
      setApiError(err.message)
    } finally {
      setCapturando(false)
    }
  }

  function reset() {
    esRef.current?.close()
    setSessionId(null)
    setStatus(null)
    setLogs([])
    setResultado(null)
    setApiError(null)
    setVncFullscreen(false)
    setDomCapturado(null)
    setCapturando(false)
  }

  return (
    <>
      {!status && (
        <div className="bank-hero">
          <div className="hero-text">
            <h2>Descarga de Comprobantes</h2>
            <p>Selecciona la fecha y el bot descargará<br />los PDFs desde el portal Telecredito.</p>
          </div>
          <i className="fa-solid fa-file-arrow-down hero-icon" />
        </div>
      )}

      {!status && (
        <div className="card">
          <div className="card-header">
            <div className="card-header-row">
              <div>
                <div className="card-title">Parámetros de descarga</div>
                <div className="card-subtitle">Fecha en horario de Lima (UTC-5)</div>
              </div>
            </div>
          </div>
          <div className="card-body">
            <form onSubmit={handleIniciar}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Fecha</label>
                  <input
                    className="form-input"
                    type="date"
                    required
                    value={fecha}
                    onChange={(e) => setFecha(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Máx. PDFs <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(opcional)</span></label>
                  <input
                    className="form-input form-input--short"
                    type="number"
                    max={500}
                    placeholder="Todos"
                    value={maxPdfs}
                    onChange={(e) => setMaxPdfs(e.target.value)}
                  />
                </div>
              </div>

              {apiError && (
                <p className="error-inline" style={{ marginBottom: '12px' }}>
                  <i className="fa-solid fa-circle-exclamation" />
                  {apiError}
                </p>
              )}

              <button className="btn-primary" type="submit">
                <i className="fa-solid fa-play" />
                Iniciar descarga
              </button>
              <button
                className="btn-outline"
                type="button"
                onClick={handleIniciarLibre}
                style={{ marginLeft: '8px' }}
              >
                <i className="fa-solid fa-binoculars" />
                Solo navegar
              </button>
            </form>
          </div>
        </div>
      )}

      {status && (
        <div className="status-bar" style={{ '--status-color': STATUS_COLORS[status] }}>
          <span className="status-dot" />
          <span className="status-label">{STATUS_LABELS[status] ?? status}</span>
          {isActive && (
            <button className="btn-ghost danger" onClick={handleCancelar}>
              <i className="fa-solid fa-xmark" />
              Cancelar
            </button>
          )}
        </div>
      )}

      {status === 'esperando_login' && (
        <div className="login-prompt">
          <div className="login-prompt-header">
            <i className="fa-solid fa-circle-exclamation" />
            Acción requerida — login manual
          </div>
          <div className="login-prompt-body">
            <ol className="login-steps">
              <li>En el visor de abajo, inicia sesión con tus credenciales BCP (cuenta 2).</li>
              <li>Una vez dentro del portal Telecredito, haz clic en <strong>Confirmar login</strong>.</li>
            </ol>
            {apiError && (
              <p className="error-inline">
                <i className="fa-solid fa-circle-xmark" />
                {apiError}
              </p>
            )}
            <div>
              <button className="btn-primary" onClick={handleConfirmarLogin}>
                <i className="fa-solid fa-circle-check" />
                Confirmar login
              </button>
            </div>
          </div>
        </div>
      )}

      {status === 'libre' && (
        <div className="login-prompt">
          <div className="login-prompt-header">
            <i className="fa-solid fa-triangle-exclamation" />
            Modo libre — el flujo se detuvo con un error
          </div>
          <div className="login-prompt-body">
            <p style={{ marginBottom: '12px', color: 'var(--text-muted)' }}>
              El navegador sigue abierto. Navega en el visor, ubícate en la página que quieras
              inspeccionar y luego captura el DOM para que pueda analizarlo y corregir el flujo.
            </p>
            {apiError && (
              <p className="error-inline" style={{ marginBottom: '12px' }}>
                <i className="fa-solid fa-circle-xmark" />
                {apiError}
              </p>
            )}
            {domCapturado && (
              <p style={{ marginBottom: '12px', color: 'var(--success-text)', fontSize: '13px' }}>
                <i className="fa-solid fa-circle-check" style={{ marginRight: '6px' }} />
                DOM guardado: <strong>{domCapturado.filename}</strong>
                {domCapturado.url && (
                  <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>({domCapturado.url})</span>
                )}
              </p>
            )}
            <button
              className="btn-primary"
              onClick={handleCapturarDom}
              disabled={capturando}
            >
              <i className="fa-solid fa-code" />
              {capturando ? 'Capturando...' : 'Capturar DOM'}
            </button>
          </div>
        </div>
      )}

      {showVnc && vncUrl && (
        <div className={`vnc-wrapper${vncFullscreen ? ' vnc-wrapper--fullscreen' : ''}`}>
          <button
            className="vnc-fullscreen-btn"
            onClick={() => setVncFullscreen((v) => !v)}
            title={vncFullscreen ? 'Salir (Esc)' : 'Pantalla completa'}
          >
            <i className={`fa-solid ${vncFullscreen ? 'fa-compress' : 'fa-expand'}`} />
            {vncFullscreen ? 'Salir' : 'Pantalla completa'}
          </button>
          <iframe
            className="vnc-frame"
            src={vncUrl}
            title="Visor de navegador remoto BCP2"
            allow="clipboard-read; clipboard-write"
          />
        </div>
      )}

      {logs.length > 0 && (
        <div>
          <div className="logs-label">
            <i className="fa-solid fa-terminal" />
            Registro de actividad
          </div>
          <LogsPanel logs={logs} />
        </div>
      )}

      {status === 'completado' && (
        <div className="result-card result-card--success">
          <i className="fa-solid fa-circle-check result-icon" />
          <div className="result-content">
            <div className="result-title">Descarga finalizada</div>
            <div className="result-detail">
              {resultado !== null
                ? `${resultado} PDF(s) descargados correctamente.`
                : 'Proceso completado.'}
            </div>
            <div className="result-actions">
              <button className="btn-primary" onClick={reset}>
                <i className="fa-solid fa-rotate-right" />
                Nueva descarga
              </button>
            </div>
          </div>
        </div>
      )}

      {status === 'error' && (
        <div className="result-card result-card--error">
          <i className="fa-solid fa-circle-xmark result-icon" />
          <div className="result-content">
            <div className="result-title">Ocurrió un error</div>
            <div className="result-detail">Revisa el registro de actividad para más detalles.</div>
            <div className="result-actions">
              <button className="btn-outline" onClick={reset}>
                <i className="fa-solid fa-rotate-right" />
                Reintentar
              </button>
            </div>
          </div>
        </div>
      )}

      {status === 'cancelado' && (
        <div className="result-card result-card--neutral">
          <i className="fa-solid fa-circle-minus result-icon" />
          <div className="result-content">
            <div className="result-title">Sesión cancelada</div>
            <div className="result-detail">Puedes iniciar una nueva descarga cuando quieras.</div>
            <div className="result-actions">
              <button className="btn-primary" onClick={reset}>
                <i className="fa-solid fa-play" />
                Nueva descarga
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
