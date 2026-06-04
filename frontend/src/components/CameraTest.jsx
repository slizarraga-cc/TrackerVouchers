/**
 * TEMPORAL — Prueba de cámara del navegador.
 * Valida que getUserMedia funcione desde este origen.
 * Remover este módulo una vez confirmado que la cámara opera en producción.
 */
import { useState, useRef, useEffect } from 'react'

export function CameraTest() {
  const videoRef  = useRef(null)
  const streamRef = useRef(null)

  const [estado,     setEstado]     = useState('idle')   // idle | solicitando | activa | error
  const [error,      setError]      = useState(null)
  const [deviceInfo, setDeviceInfo] = useState(null)
  const [devices,    setDevices]    = useState([])

  // Una vez que el video element se monta (estado = 'activa'), adjuntar el stream
  useEffect(() => {
    if (estado === 'activa' && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current
    }
  }, [estado])

  // Limpiar stream al desmontar
  useEffect(() => {
    return () => detener()
  }, [])

  async function iniciar() {
    setEstado('solicitando')
    setError(null)
    setDeviceInfo(null)

    // Listar cámaras disponibles antes de pedir stream
    try {
      const devs = await navigator.mediaDevices.enumerateDevices()
      setDevices(devs.filter((d) => d.kind === 'videoinput'))
    } catch (_) {}

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
      }

      const track = stream.getVideoTracks()[0]
      const settings = track.getSettings()
      setDeviceInfo({
        label:  track.label || 'Dispositivo desconocido',
        width:  settings.width,
        height: settings.height,
        fps:    settings.frameRate ? Math.round(settings.frameRate) : '?',
      })

      setEstado('activa')
    } catch (err) {
      setEstado('error')
      if (err.name === 'NotAllowedError') {
        setError('Permiso denegado. Permite el acceso a la cámara en tu navegador.')
      } else if (err.name === 'NotFoundError') {
        setError('No se encontró ninguna cámara conectada.')
      } else if (err.name === 'NotReadableError') {
        setError('La cámara está siendo usada por otra aplicación.')
      } else {
        setError(`${err.name}: ${err.message}`)
      }
    }
  }

  function detener() {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null
    }
    setEstado('idle')
    setDeviceInfo(null)
  }

  const isSecure = window.location.protocol === 'https:' || window.location.hostname === 'localhost'
  const apiSupported = !!navigator.mediaDevices?.getUserMedia

  return (
    <>
      <div className="bank-hero">
        <div className="hero-text">
          <h2>Prueba de Cámara — Temporal</h2>
          <p>
            Valida que <code>getUserMedia</code> funcione desde este origen antes de usar el flujo Interbank.
            El bot IBK usa una <strong>cámara virtual sintética</strong> en Chrome — este test
            verifica la misma API desde tu navegador cliente.
          </p>
        </div>
        <i className="fa-solid fa-video hero-icon" />
      </div>

      {/* Advertencias de entorno */}
      {!isSecure && (
        <div className="login-prompt" style={{ marginBottom: '16px' }}>
          <div className="login-prompt-header">
            <i className="fa-solid fa-triangle-exclamation" />
            Contexto no seguro (HTTP)
          </div>
          <div className="login-prompt-body">
            <p style={{ margin: 0 }}>
              Los navegadores modernos bloquean el acceso a la cámara en HTTP excepto en <code>localhost</code>.
              En producción asegúrate de servir la app con <strong>HTTPS</strong> o accede desde
              <code> localhost</code>. El bot de Selenium no tiene este problema porque accede
              directamente a <code>https://empresas.interbank.pe</code>.
            </p>
          </div>
        </div>
      )}

      {!apiSupported && (
        <div className="result-card result-card--error">
          <i className="fa-solid fa-circle-xmark result-icon" />
          <div className="result-content">
            <div className="result-title">API no disponible</div>
            <div className="result-detail">
              <code>navigator.mediaDevices.getUserMedia</code> no está disponible en este navegador/contexto.
            </div>
          </div>
        </div>
      )}

      {/* Panel principal */}
      {apiSupported && (
        <div className="card">
          <div className="card-header">
            <div className="card-header-row">
              <div>
                <div className="card-title">Control de cámara</div>
                <div className="card-subtitle">
                  Estado:{' '}
                  <span style={{
                    color: estado === 'activa'      ? 'var(--success-text)'
                         : estado === 'error'       ? 'var(--error-text)'
                         : estado === 'solicitando' ? 'var(--warn-text)'
                         : 'var(--text-muted)',
                    fontWeight: 600,
                  }}>
                    {{ idle: 'Inactiva', solicitando: 'Solicitando permiso...', activa: 'Activa', error: 'Error' }[estado]}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Botones */}
            <div style={{ display: 'flex', gap: '8px' }}>
              {estado !== 'activa' && (
                <button
                  className="btn-primary"
                  onClick={iniciar}
                  disabled={estado === 'solicitando' || !isSecure}
                >
                  <i className="fa-solid fa-video" />
                  {estado === 'solicitando' ? 'Solicitando...' : 'Activar cámara'}
                </button>
              )}
              {estado === 'activa' && (
                <button className="btn-outline" onClick={detener}>
                  <i className="fa-solid fa-video-slash" />
                  Detener
                </button>
              )}
            </div>

            {/* Error */}
            {estado === 'error' && error && (
              <p className="error-inline">
                <i className="fa-solid fa-circle-exclamation" />
                {error}
              </p>
            )}

            {/* Info del dispositivo */}
            {deviceInfo && (
              <div style={{
                background: 'var(--bg-secondary, #1e1e2e)',
                borderRadius: '8px',
                padding: '12px 16px',
                fontSize: '13px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
              }}>
                <div><strong>Dispositivo:</strong> {deviceInfo.label}</div>
                <div><strong>Resolución:</strong> {deviceInfo.width} × {deviceInfo.height} px</div>
                <div><strong>FPS:</strong> {deviceInfo.fps}</div>
              </div>
            )}

            {/* Video preview */}
            <div style={{
              width: '100%',
              maxWidth: '640px',
              background: '#000',
              borderRadius: '8px',
              overflow: 'hidden',
              aspectRatio: '4/3',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {estado !== 'activa' ? (
                <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center' }}>
                  <i className="fa-solid fa-video-slash" style={{ fontSize: '32px', display: 'block', marginBottom: '8px' }} />
                  Sin señal
                </div>
              ) : (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                />
              )}
            </div>
          </div>
        </div>
      )}

      {/* Cámaras detectadas */}
      {devices.length > 0 && (
        <div className="card" style={{ marginTop: '16px' }}>
          <div className="card-header">
            <div className="card-title">Cámaras detectadas ({devices.length})</div>
          </div>
          <div className="card-body">
            <ul style={{ margin: 0, padding: '0 0 0 20px', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {devices.map((d, i) => (
                <li key={d.deviceId || i}>
                  {d.label || `Cámara ${i + 1}`}
                  {d.label === '' && (
                    <span style={{ color: 'var(--text-muted)', marginLeft: '6px' }}>
                      (label oculto — otorga permiso para ver el nombre)
                    </span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Nota sobre el bot IBK */}
      <div className="card" style={{ marginTop: '16px' }}>
        <div className="card-header">
          <div className="card-title">Cómo funciona la cámara en el bot IBK</div>
        </div>
        <div className="card-body" style={{ fontSize: '13px', lineHeight: '1.7', display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <p style={{ margin: 0 }}>
            El bot usa Chrome con las flags <code>--use-fake-ui-for-media-stream</code> y{' '}
            <code>--use-fake-device-for-media-stream</code>. Esto le da a Chrome:
          </p>
          <ul style={{ margin: 0, paddingLeft: '20px' }}>
            <li><strong>Auto-aprobación</strong> del popup de permiso de cámara — nunca bloquea el flujo.</li>
            <li><strong>Cámara virtual sintética</strong> — genera un patrón de video animado sin necesidad de hardware.</li>
          </ul>
          <p style={{ margin: 0 }}>
            El permiso también se concede explícitamente vía CDP (<code>Browser.grantPermissions</code>)
            para <code>https://empresas.interbank.pe</code> antes de navegar, cubriendo tanto la fase
            de login manual como la fase automatizada.
          </p>
          <p style={{ margin: 0, color: 'var(--text-muted)' }}>
            En EC2 no se requiere ningún hardware de cámara ni módulo de kernel adicional.
          </p>
        </div>
      </div>
    </>
  )
}
