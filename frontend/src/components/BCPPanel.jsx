import { useState, useEffect, useRef } from 'react'
import { iniciarBCP, confirmarLoginBCP, cancelarBCP, capturarDomBCP, iniciarLibreBCP, suscribirLogs, getConfig, sesionActivaBCP } from '../api/client'
import { LogsPanel } from './LogsPanel'

/** Fecha de hoy en timezone Lima → "YYYY-MM-DD" (valor para input type=date) */
function todayISO() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Lima' })
}

/** Retorna el ultimo dia laborable anterior a hoy en timezone Lima (YYYY-MM-DD).
 *  Lunes → Viernes anterior (retrocede 3 dias)
 *  Domingo → Viernes anterior (retrocede 2 dias)
 *  Sabado → Viernes anterior (retrocede 1 dia)
 *  Cualquier otro dia de semana → dia anterior
 */
function ultimoDiaLaborable() {
  const limaHoy = new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Lima' })
  const [y, m, d] = limaHoy.split('-').map(Number)
  const ayer = new Date(y, m - 1, d - 1)
  const dow = ayer.getDay() // 0=Dom, 6=Sab
  if (dow === 6) ayer.setDate(ayer.getDate() - 1) // Sab → Vie
  if (dow === 0) ayer.setDate(ayer.getDate() - 2) // Dom → Vie
  const yy = ayer.getFullYear()
  const mm = String(ayer.getMonth() + 1).padStart(2, '0')
  const dd = String(ayer.getDate()).padStart(2, '0')
  return `${yy}-${mm}-${dd}`
}

/** "YYYY-MM-DD" → "DD/MM/YYYY" (formato que espera el flujo BCP) */
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

export function BCPPanel() {
  const [fechaDesde, setFechaDesde] = useState(ultimoDiaLaborable)
  const [fechaHasta, setFechaHasta] = useState(todayISO)
  const [maxPdfs,    setMaxPdfs]    = useState('')

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

  // Al montar: cargar VNC URL y reconectar a sesion activa si existe
  useEffect(() => {
    getConfig().then((cfg) => {
      const base = window.location.origin
      setVncUrl(
        `${base}/vnc/bcp/vnc.html?autoconnect=1&resize=scale&password=${cfg.vnc_password}&path=vnc/bcp/`
      )
    })

    sesionActivaBCP().then((data) => {
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
    esRef.current = suscribirLogs(
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
  const isTerminal  = ['completado', 'error', 'cancelado'].includes(status)

  async function handleIniciar(e) {
    e.preventDefault()
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarBCP({
        fechaDesde: toDisplayDate(fechaDesde),
        fechaHasta: toDisplayDate(fechaHasta),
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
      await confirmarLoginBCP(sessionId)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleIniciarLibre() {
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarLibreBCP()
      setSessionId(data.session_id)
      setStatus(data.status)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleCancelar() {
    if (sessionId) await cancelarBCP(sessionId)
    reset()
  }

  async function handleCapturarDom() {
    if (!sessionId) return
    setCapturando(true)
    setDomCapturado(null)
    try {
      const data = await capturarDomBCP(sessionId)
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
      {/* ---------------------------------------------------------------- */}
      {/* Hero — solo cuando no hay sesion activa                           */}
      {/* ---------------------------------------------------------------- */}
      {!status && (
        <div className="bank-hero">
          <div className="hero-text">
            <h2>Descarga de Comprobantes</h2>
            <p>Selecciona el rango de fechas y el bot descargará<br />los PDFs desde el portal Telecredito.</p>
          </div>
          <i className="fa-solid fa-file-arrow-down hero-icon" />
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Formulario                                                        */}
      {/* ---------------------------------------------------------------- */}
      {!status && (
        <div className="card">
          <div className="card-header">
            <div className="card-header-row">
              <div>
                <div className="card-title">Parámetros de descarga</div>
                <div className="card-subtitle">Rango de fechas en horario de Lima (UTC-5)</div>
              </div>
            </div>
          </div>
          <div className="card-body">
            <form onSubmit={handleIniciar}>
              <div className="form-row">
                <div className="form-group">
                  <label className="form-label">Fecha desde</label>
                  <input
                    className="form-input"
                    type="date"
                    required
                    value={fechaDesde}
                    onChange={(e) => setFechaDesde(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Fecha hasta</label>
                  <input
                    className="form-input"
                    type="date"
                    required
                    value={fechaHasta}
                    onChange={(e) => setFechaHasta(e.target.value)}
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

      {/* ---------------------------------------------------------------- */}
      {/* Barra de estado                                                   */}
      {/* ---------------------------------------------------------------- */}
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

      {/* ---------------------------------------------------------------- */}
      {/* Login prompt                                                      */}
      {/* ---------------------------------------------------------------- */}
      {status === 'esperando_login' && (
        <div className="login-prompt">
          <div className="login-prompt-header">
            <i className="fa-solid fa-circle-exclamation" />
            Acción requerida — login manual
          </div>
          <div className="login-prompt-body">
            <ol className="login-steps">
              <li>En el visor de abajo, inicia sesión con tus credenciales BCP.</li>
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

      {/* ---------------------------------------------------------------- */}
      {/* Modo libre                                                        */}
      {/* ---------------------------------------------------------------- */}
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

      {/* ---------------------------------------------------------------- */}
      {/* Visor noVNC                                                       */}
      {/* ---------------------------------------------------------------- */}
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
            title="Visor de navegador remoto"
            allow="clipboard-read; clipboard-write"
          />
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Logs                                                              */}
      {/* ---------------------------------------------------------------- */}
      {logs.length > 0 && (
        <div>
          <div className="logs-label">
            <i className="fa-solid fa-terminal" />
            Registro de actividad
          </div>
          <LogsPanel logs={logs} />
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Estados finales                                                   */}
      {/* ---------------------------------------------------------------- */}
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
