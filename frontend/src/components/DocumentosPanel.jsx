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

/** Convierte 'YYYY-MM-DD' a 'DD/MM/YYYY' para mostrar al usuario. */
function formatFechaChip(yyyymmdd) {
  const [y, m, d] = yyyymmdd.split('-')
  return `${d}/${m}/${y}`
}

function triggerDownload(url, filename) {
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
}

function TablaArchivos({ archivos }) {
  return (
    <table className="tabla">
      <thead>
        <tr>
          <th>Archivo</th>
          <th>Tamaño</th>
          <th>Descargado</th>
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
  )
}

export function DocumentosPanel() {
  const [docs,        setDocs]        = useState([])
  const [loading,     setLoading]     = useState(true)
  const [error,       setError]       = useState(null)
  const [fechaFiltro, setFechaFiltro] = useState(null) // null = Todas

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
      setFechaFiltro(null)
    } catch (e) {
      setError(e.message)
    }
  }

  // Fechas únicas disponibles (ordenadas)
  const fechasDisponibles = [...new Set(docs.map(d => d.fecha))].sort()

  // Docs filtrados por fecha seleccionada
  const docsFiltrados = fechaFiltro
    ? docs.filter(d => d.fecha === fechaFiltro)
    : docs

  // Agrupar por banco
  const grupos = docsFiltrados.reduce((acc, doc) => {
    if (!acc[doc.banco]) acc[doc.banco] = []
    acc[doc.banco].push(doc)
    return acc
  }, {})

  const totalSize = docsFiltrados.reduce((s, d) => s + d.size, 0)

  const nombreZip = fechaFiltro
    ? `comprobantes_${formatFechaChip(fechaFiltro).replace(/\//g, '-')}.zip`
    : 'comprobantes.zip'

  return (
    <>
      {/* ---------------------------------------------------------------- */}
      {/* Hero                                                              */}
      {/* ---------------------------------------------------------------- */}
      <div className="bank-hero">
        <div className="hero-text">
          <h2>Documentos Descargados</h2>
          <p>
            {docsFiltrados.length > 0
              ? `${docsFiltrados.length} archivo(s) · ${formatSize(totalSize)} en total`
              : docs.length > 0
                ? 'Sin archivos para la fecha seleccionada.'
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
            disabled={docsFiltrados.length === 0}
            onClick={() => triggerDownload(urlDescargarTodos(fechaFiltro), nombreZip)}
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
      {/* Filtro de fecha                                                   */}
      {/* ---------------------------------------------------------------- */}
      {fechasDisponibles.length > 0 && (
        <div className="card">
          <div className="card-body" style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-secondary)', marginRight: '4px', whiteSpace: 'nowrap' }}>
              <i className="fa-regular fa-calendar-days" style={{ marginRight: '6px' }} />
              Filtrar por fecha:
            </span>
            <button
              className={fechaFiltro === null ? 'btn-primary' : 'btn-ghost'}
              style={{ padding: '4px 14px', fontSize: '13px' }}
              onClick={() => setFechaFiltro(null)}
            >
              Todas
            </button>
            {fechasDisponibles.map(fecha => (
              <button
                key={fecha}
                className={fechaFiltro === fecha ? 'btn-primary' : 'btn-ghost'}
                style={{ padding: '4px 14px', fontSize: '13px' }}
                onClick={() => setFechaFiltro(fecha)}
              >
                {formatFechaChip(fecha)}
              </button>
            ))}
          </div>
        </div>
      )}

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
      {/* Tablas por banco con subgrupos por fecha                          */}
      {/* ---------------------------------------------------------------- */}
      {!loading && Object.entries(grupos).map(([banco, archivos]) => {
        // Subgrupar por fecha dentro de este banco
        const porFecha = archivos.reduce((acc, doc) => {
          if (!acc[doc.fecha]) acc[doc.fecha] = []
          acc[doc.fecha].push(doc)
          return acc
        }, {})
        const fechasEnBanco = Object.keys(porFecha).sort()
        // Mostrar subgrupos solo si hay más de una fecha (en vista "Todas")
        const mostrarSubgrupos = fechaFiltro === null && fechasEnBanco.length > 1

        return (
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
              {mostrarSubgrupos
                ? fechasEnBanco.map(fecha => (
                    <div key={fecha}>
                      <div style={{
                        padding: '7px 16px',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        background: 'var(--bg-subtle, #f8f9fa)',
                        borderTop: '1px solid var(--border)',
                        borderBottom: '1px solid var(--border)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}>
                        <i className="fa-regular fa-calendar" />
                        {formatFechaChip(fecha)}
                        <span style={{ opacity: 0.6 }}>— {porFecha[fecha].length} archivo(s)</span>
                      </div>
                      <TablaArchivos archivos={porFecha[fecha]} />
                    </div>
                  ))
                : <TablaArchivos archivos={archivos} />
              }
            </div>
          </div>
        )
      })}
    </>
  )
}
