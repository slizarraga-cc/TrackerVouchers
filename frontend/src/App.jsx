import { useState } from 'react'
import { BCPPanel }        from './components/BCPPanel'
import { BBVAPanel }       from './components/BBVAPanel'
import { DocumentosPanel } from './components/DocumentosPanel'

const MODULES = [
  // Bancos
  { id: 'bcp',        label: 'BCP',        icon: 'fa-building-columns', section: 'bancos',       component: BCPPanel },
  { id: 'bbva',       label: 'BBVA',       icon: 'fa-university',       section: 'bancos',       component: BBVAPanel },
  { id: 'scotiabank', label: 'Scotiabank',  icon: 'fa-credit-card',      section: 'bancos',       component: null },
  { id: 'interbank',  label: 'Interbank',   icon: 'fa-landmark',         section: 'bancos',       component: null },
  // Herramientas
  { id: 'documentos', label: 'Documentos',  icon: 'fa-folder-open',      section: 'herramientas', component: DocumentosPanel },
]

const SECTIONS = [
  { id: 'bancos',       label: 'Bancos' },
  { id: 'herramientas', label: 'Herramientas' },
]

const TOPBAR_TITLES = {
  bcp:        'Descarga de Comprobantes — BCP Telecredito',
  bbva:       'Seguimiento de Pagos Masivos — BBVA Net Cash',
  scotiabank: 'Descarga de Comprobantes — Scotiabank',
  interbank:  'Descarga de Comprobantes — Interbank',
  documentos: 'Documentos Descargados',
}

export default function App() {
  const [active, setActive] = useState('bcp')
  const ActivePanel = MODULES.find((m) => m.id === active)?.component

  return (
    <div className="app">
      {/* ---------------------------------------------------------------- */}
      {/* Sidebar                                                           */}
      {/* ---------------------------------------------------------------- */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">
            <i className="fa-solid fa-download" />
          </div>
          <div>
            <div className="brand-name">CreceCapital</div>
            <div className="brand-sub">Tesoreria RPA</div>
          </div>
        </div>

        {SECTIONS.map((section) => (
          <div key={section.id}>
            <div className="sidebar-section-label">{section.label}</div>
            <nav className="sidebar-nav">
              {MODULES.filter((m) => m.section === section.id).map((mod) => (
                <button
                  key={mod.id}
                  className={`nav-btn${active === mod.id ? ' active' : ''}`}
                  onClick={() => mod.component && setActive(mod.id)}
                  disabled={!mod.component}
                >
                  <i className={`fa-solid ${mod.icon} nav-icon`} />
                  <span className="nav-label">{mod.label}</span>
                  {!mod.component && <span className="pill pill-muted">Pronto</span>}
                </button>
              ))}
            </nav>
          </div>
        ))}
      </aside>

      {/* ---------------------------------------------------------------- */}
      {/* Main                                                              */}
      {/* ---------------------------------------------------------------- */}
      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <span className="topbar-badge">Tesoreria RPA</span>
            <span className="topbar-title">{TOPBAR_TITLES[active]}</span>
          </div>
        </header>

        <div className="content-area">
          {ActivePanel ? <ActivePanel /> : <p>No disponible aún.</p>}
        </div>
      </div>
    </div>
  )
}
