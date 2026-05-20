import { useState, useEffect, useCallback } from 'react'
import {
  listarDocumentos,
  urlDescargarTodos,
  urlDescargarArchivo,
  eliminarTodosDocumentos,
} from '../api/client'

const BANK_LABELS = {
  BCP:        'BCP Telecredito',
  BBVA:       'BBVA Net Cash',
  SCOTIABANK: 'Scotiabank',
  INTERBANK:  'Interbank',
  OTRO:       'Sin banco asignado',
}

const BANK_ICONS = {
  BCP:        'fa-building-columns',
  BBVA:       'fa-university',
  SCOTIABANK: 'fa-credit-card',
  INTERBANK:  'fa-landmark',
  OTRO:       'fa-file-pdf',
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatFecha(timestamp) {
  return new Date(timestamp * 1000).toLocaleString('es-PE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'America/Lima',
  })
}

function triggerDownload(url, filename) {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

export function DocumentosPanel() {
  const [docs,    setDocs]    = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  const cargar = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listarDocumentos()
      setDocs(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { cargar() }, [cargar])

  async function handleEliminarTodos() {
    if (!window.confirm(`¿Eliminar los ${docs.length} documento(s) descargado(s)? Esta acción no se puede deshacer.`)) return
    try {
      await eliminarTodosDocumentos()
      setDocs([])
    } catch (e) {
      setError(e.message)
    }
  }

  // Agrupar por banco
  const grupos = docs.reduce((acc, doc) => {
    const b = doc.banco
    if (!acc[b]) acc[b] = []
    acc[b].push(doc)
    return acc
  }, {})

  const totalSize = docs.reduce((s, d) => s + d.size, 0)

  return (
    <>
      {/* ---------------------------------------------------------------- */}
      {/* Hero                                                              */}
      {/* ---------------------------------------------------------------- */}
      <div className="bank-hero">
        <div className="hero-text">
          <h2>Documentos Descargados</h2>
          <p>
            {docs.length > 0
              ? `${docs.length} archivo(s) · ${formatSize(totalSize)} en total`
              : 'No hay archivos descargados aún.'}
          </p>
        </div>
        <i className="fa-solid fa-folder-open hero-icon" />
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Acciones globales                                                 */}
      {/* ---------------------------------------------------------------- */}
      <div className="card">
        <div className="card-body" style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button
            className="btn-primary"
            disabled={docs.length === 0}
            onClick={() => triggerDownload(urlDescargarTodos(), 'comprobantes.zip')}
          >
            <i className="fa-solid fa-download" />
            Descargar todo (ZIP)
          </button>
          <button
            className="btn-ghost danger"
            disabled={docs.length === 0}
            onClick={handleEliminarTodos}
          >
            <i className="fa-solid fa-trash" />
            Eliminar todo
          </button>
          <button className="btn-ghost" style={{ marginLeft: 'auto' }} onClick={cargar}>
            <i className="fa-solid fa-rotate-right" />
            Actualizar
          </button>
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Loading                                                           */}
      {/* ---------------------------------------------------------------- */}
      {loading && (
        <div className="loading-overlay">
          <div className="spinner" />
          <div className="loading-title">Cargando documentos...</div>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Error                                                             */}
      {/* ---------------------------------------------------------------- */}
      {error && (
        <div className="result-card result-card--error">
          <i className="fa-solid fa-circle-xmark result-icon" />
          <div className="result-content">
            <div className="result-title">Error al cargar documentos</div>
            <div className="result-detail">{error}</div>
          </div>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Empty state                                                       */}
      {/* ---------------------------------------------------------------- */}
      {!loading && !error && docs.length === 0 && (
        <div className="empty-state">
          <i className="fa-solid fa-folder-open" />
          <p>No hay documentos descargados aún.<br />Ejecuta una descarga desde la sección BCP.</p>
        </div>
      )}

      {/* ---------------------------------------------------------------- */}
      {/* Tablas por banco                                                  */}
      {/* ---------------------------------------------------------------- */}
      {!loading && Object.entries(grupos).map(([banco, archivos]) => (
        <div className="card" key={banco}>
          <div className="card-header">
            <div className="card-header-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <i className={`fa-solid ${BANK_ICONS[banco] ?? 'fa-file-pdf'}`}
                   style={{ color: 'var(--blue-primary)', fontSize: '15px' }} />
                <div>
                  <div className="card-title">{BANK_LABELS[banco] ?? banco}</div>
                  <div className="card-subtitle">
                    {archivos.length} archivo(s) · {formatSize(archivos.reduce((s, d) => s + d.size, 0))}
                  </div>
                </div>
              </div>
              <span className="pill pill-tipo">{banco}</span>
            </div>
          </div>
          <div className="card-body" style={{ padding: '0 0 4px' }}>
            <table className="tabla">
              <thead>
                <tr>
                  <th>Archivo</th>
                  <th>Tamaño</th>
                  <th>Fecha</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {archivos.map((doc) => (
                  <tr key={doc.nombre}>
                    <td className="tabla-cell-nombre">
                      <i className="fa-solid fa-file-pdf" style={{ color: '#E53E3E', marginRight: '8px' }} />
                      {doc.nombre}
                    </td>
                    <td className="tabla-cell-meta">{formatSize(doc.size)}</td>
                    <td className="tabla-cell-meta">{formatFecha(doc.modificado)}</td>
                    <td className="tabla-cell-action">
                      <button
                        className="btn-ghost"
                        style={{ padding: '5px 10px', fontSize: '12px' }}
                        onClick={() => triggerDownload(urlDescargarArchivo(doc.nombre), doc.nombre)}
                      >
                        <i className="fa-solid fa-download" />
                        Descargar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </>
  )
}
