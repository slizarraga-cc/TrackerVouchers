import { useState, useEffect, useRef } from 'react'
import { iniciarIBK, confirmarLoginIBK, cancelarIBK, suscribirLogsIBK, getConfig, sesionActivaIBK, conectarCameraRelay } from '../api/client'
import { LogsPanel } from './LogsPanel'

function hoyLima() {
  return new Date().toLocaleDateString('sv-SE', { timeZone: 'America/Lima' })
}

function ultimoDiaLaborable() {
  const limaHoy = hoyLima()
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

function toDisplayDate(htmlDate) {
  if (!htmlDate) return ''
  const [y, m, d] = htmlDate.split('-')
  return `${d}/${m}/${y}`
}

const STATUS_LABELS = {
  iniciando:        'Conectando al navegador...',
  esperando_login:  'Esperando login manual',
  ejecutando:       'Generando solicitudes y descargando PDFs...',
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

export function IBKPanel() {
  const [fechaInicio, setFechaInicio] = useState(ultimoDiaLaborable)
  const [fechaFin,    setFechaFin]    = useState(hoyLima)
  const [maxPdfs,     setMaxPdfs]     = useState('')

  const [sessionId,     setSessionId]     = useState(null)
  const [status,        setStatus]        = useState(null)
  const [logs,          setLogs]          = useState([])
  const [resultado,     setResultado]     = useState(null)
  const [apiError,      setApiError]      = useState(null)
  const [vncUrl,        setVncUrl]        = useState('')
  const [vncFullscreen, setVncFullscreen] = useState(false)

  const esRef       = useRef(null)
  const wsRef       = useRef(null)
  const streamRef   = useRef(null)
  const cameraRef   = useRef(null)
  const canvasRef   = useRef(null)
  const frameTimer  = useRef(null)
  const [cameraError, setCameraError] = useState(null)

  useEffect(() => {
    getConfig().then((cfg) => {
      const base = window.location.origin
      setVncUrl(
        `${base}/vnc/ibk/vnc.html?autoconnect=1&resize=scale&password=${cfg.vnc_password}&path=vnc/ibk/`
      )
    })

    sesionActivaIBK().then((data) => {
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
    esRef.current = suscribirLogsIBK(
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

  // Iniciar/detener relay de cámara según el estado de la sesión
  useEffect(() => {
    if (status === 'esperando_login') {
      startCameraRelay()
    } else {
      stopCameraRelay()
    }
    return () => stopCameraRelay()
  }, [status])

  async function startCameraRelay() {
    setCameraError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      })
      streamRef.current = stream
      if (cameraRef.current) cameraRef.current.srcObject = stream

      const ws = conectarCameraRelay()
      wsRef.current = ws

      ws.onopen = () => {
        const canvas = canvasRef.current
        const video  = cameraRef.current
        if (!canvas || !video) return
        canvas.width  = 640
        canvas.height = 480
        const ctx = canvas.getContext('2d')

        frameTimer.current = setInterval(() => {
          if (ws.readyState !== WebSocket.OPEN) return
          ctx.drawImage(video, 0, 0, 640, 480)
          canvas.toBlob((blob) => {
            if (!blob || ws.readyState !== WebSocket.OPEN) return
            blob.arrayBuffer().then((buf) => {
              if (ws.readyState === WebSocket.OPEN) ws.send(buf)
            })
          }, 'image/jpeg', 0.8)
        }, Math.round(1000 / 15))
      }

      ws.onerror = () => setCameraError('Error en la conexión WebSocket de cámara.')
    } catch (err) {
      if (err.name === 'NotAllowedError') {
        setCameraError('Permiso de cámara denegado. Permite el acceso en tu navegador.')
      } else if (err.name === 'NotFoundError') {
        setCameraError('No se encontró ninguna cámara conectada.')
      } else {
        setCameraError(`Error de cámara: ${err.message}`)
      }
    }
  }

  function stopCameraRelay() {
    clearInterval(frameTimer.current)
    frameTimer.current = null
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (cameraRef.current) cameraRef.current.srcObject = null
  }

  const isActive = status && !['completado', 'error', 'cancelado'].includes(status)
  const showVnc  = ['esperando_login', 'ejecutando'].includes(status)

  async function handleIniciar(e) {
    e.preventDefault()
    setApiError(null)
    setLogs([])
    setResultado(null)
    try {
      const data = await iniciarIBK({
        fechaInicio: toDisplayDate(fechaInicio),
        fechaFin:    toDisplayDate(fechaFin),
        maxPdfs:     maxPdfs !== '' ? Number(maxPdfs) : null,
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
      await confirmarLoginIBK(sessionId)
    } catch (err) {
      setApiError(err.message)
    }
  }

  async function handleCancelar() {
    if (sessionId) await cancelarIBK(sessionId)
    reset()
  }

  function reset() {
    esRef.current?.close()
    setSessionId(null)
    setStatus(null)
    setLogs([])
    setResultado(null)
    setApiError(null)
    setCameraError(null)
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
            <h2>Descarga de Comprobantes — Pagos Masivos</h2>
            <p>
              El bot procesará <strong>AHTC-01 (soles)</strong> y <strong>AHTC-02 (dólares)</strong>,
              generará las solicitudes PDF y descargará todos los comprobantes desde Mis Reportes.
            </p>
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
                  <label className="form-label">Fecha inicio</label>
                  <input
                    className="form-input"
                    type="date"
                    required
                    value={fechaInicio}
                    onChange={(e) => setFechaInicio(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Fecha fin</label>
                  <input
                    className="form-input"
                    type="date"
                    required
                    value={fechaFin}
                    onChange={(e) => setFechaFin(e.target.value)}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">
                    Máx. PDFs{' '}
                    <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(opcional)</span>
                  </label>
                  <input
                    className="form-input form-input--short"
                    type="number"
                    min={1}
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
              <li>En el visor de abajo, inicia sesión con tus credenciales de Interbank Empresas.</li>
              <li>Si IBK solicita verificación por cámara, <strong>tu cámara ya está activa</strong> y siendo retransmitida al navegador del bot.</li>
              <li>Una vez en el portal principal, haz clic en <strong>Confirmar login</strong>.</li>
            </ol>

            {/* Canvas oculto para capturar frames */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* Preview de cámara */}
            <div style={{ marginTop: '12px' }}>
              {cameraError ? (
                <p className="error-inline">
                  <i className="fa-solid fa-video-slash" />
                  {cameraError}
                </p>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '180px',
                    aspectRatio: '4/3',
                    background: '#000',
                    borderRadius: '6px',
                    overflow: 'hidden',
                    flexShrink: 0,
                  }}>
                    <video
                      ref={cameraRef}
                      autoPlay
                      playsInline
                      muted
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    />
                  </div>
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                    <span style={{ color: 'var(--success-text)', fontWeight: 600 }}>
                      <i className="fa-solid fa-circle" style={{ fontSize: '8px', marginRight: '5px' }} />
                      Cámara activa
                    </span>
                    <br />
                    Tu cámara está siendo transmitida al navegador remoto de IBK.
                  </div>
                </div>
              )}
            </div>

            {apiError && (
              <p className="error-inline" style={{ marginTop: '12px' }}>
                <i className="fa-solid fa-circle-xmark" />
                {apiError}
              </p>
            )}
            <div style={{ marginTop: '12px' }}>
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
            title="Visor de navegador remoto — Interbank"
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
                ? `${resultado} archivo(s) descargados y renombrados correctamente.`
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
