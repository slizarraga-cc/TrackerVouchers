import { useState, useEffect, useRef } from 'react'
import { iniciarBBVA, confirmarLoginBBVA, cancelarBBVA, suscribirLogsBBVA, getConfig, sesionActivaBBVA } from '../api/client'
import { LogsPanel } from './LogsPanel'

function todayISO() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Lima' })
}

function toDisplayDate(htmlDate) {
  if (!htmlDate) return ''
  const [y, m, d] = htmlDate.split('-')
  return `${d}/${m}/${y}`
}

const STATUS_LABELS = {
  iniciando:        'Conectando al navegador...',
  esperando_login:  'Esperando login manual',
  ejecutando:       'Descargando pagos masivos...',
  completado:       'Completado',
  error:            'Error',
  cancelado:        'Cancelado',
}

const STATUS_COLORS = {
  iniciando:       'var(--warn-text)',
  esperando_login: 'var(--warn-text)',
  ejecutando:      'var(--info-text)',
  completado:      'var(--success-text)',
  error:           'var(--error-text)',
  cancelado:       'var(--text-muted)',
}

export function BBVAPanel() {
  const today = todayISO()

  const [fecha,    setFecha]    = useState(today)
  const [maxPdfs,  setMaxPdfs]  = useState('')

  const [sessionId,      setSessionId]      = useState(null)
  const [status,         setStatus]         = useState(null)
  const [logs,           setLogs]           = useState([])
  const [resultado,      setResultado]      = useState(null)
  const [apiError,       setApiError]       = useState(null)
  const [vncUrl,         setVncUrl]         = useState('')
  const [vncFullscreen,  setVncFullscreen]  = useState(false)

  const esRef = useRef(null)

  useEffect(() => {
    getConfig().then((cfg) => {
      const host = window.location.hostname
      const port = cfg.vnc_ports?.bbva ?? 7902
      setVncUrl(
        `http://${host}:${port}/vnc.html?autoconnect=1&resize=scale&password=${cfg.vnc_password}`
      )
    })

    sesionActivaBBVA().then((data) => {
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
    esRef.current = suscribirLogsBBVA(
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

  const isActive   = status && !['completado', 'error', 'cancelado'].includes(status)
  const showVnc    = ['esperando_login', 'ejecutando'].includes(status)

  async function handleIniciar(e) {
    e.preventDefault()
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarBBVA({
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
      await confirmarLoginBBVA(sessionId)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleCancelar() {
    if (sessionId) await cancelarBBVA(sessionId)
    reset()
  }

  function reset() {
    esRef.current?.close()
    setSessionId(null)
    setStatus(null)
    setLogs([])
    setResultado(null)
    setApiError(null)
    setVncFullscreen(false)
  }

  return (
    <>
      {/* ---------------------------------------------------------------- */}
      {/* Hero                                                              */}
      {/* ---------------------------------------------------------------- */}
      {!status && (
        <div className="bank-hero">
          <div className="hero-text">
            <h2>Seguimiento de Pagos Masivos</h2>
            <p>Selecciona la fecha y el bot descargará los PDFs<br />desde el portal BBVA Net Cash.</p>
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
              <li>En el visor de abajo, inicia sesión con tus credenciales BBVA.</li>
              <li>Una vez en el dashboard principal, haz clic en <strong>Confirmar login</strong>.</li>
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
