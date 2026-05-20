import { useEffect, useRef } from 'react'

export function LogsPanel({ logs }) {
  const ref = useRef(null)

  useEffect(() => {
    if (ref.current) {
      ref.current.scrollTop = ref.current.scrollHeight
    }
  }, [logs])

  if (!logs.length) return null

  return (
    <div className="logs-panel" ref={ref}>
      {logs.map((line, i) => (
        <div key={i} className="log-line">{line}</div>
      ))}
    </div>
  )
}
