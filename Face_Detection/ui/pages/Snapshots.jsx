import { useState, useEffect } from 'react'
import { api, SNAP_BASE } from '../src/api'
import './Snapshots.css'

export default function Snapshots() {
  const [snaps,   setSnaps]   = useState([])
  const [loading, setLoading] = useState(true)
  const [selected,setSelected]= useState(null)

  const load = async () => {
    try {
      const r = await api.getSnapshots()
      setSnaps(r.data.snapshots || [])
    } catch {} finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const formatName = filename => {
    const parts = filename.replace('unknown_','').replace('.jpg','').split('_')
    if (parts.length >= 2) {
      const d = parts[0]
      const t = parts[1]
      const date = `${d.slice(6,8)}/${d.slice(4,6)}/${d.slice(0,4)}`
      const time = `${t.slice(0,2)}:${t.slice(2,4)}:${t.slice(4,6)}`
      return { date, time }
    }
    return { date: '—', time: '—' }
  }

  return (
    <div className="snp-page fade-in">
      {/* Lightbox */}
      {selected && (
        <div className="lightbox" onClick={() => setSelected(null)}>
          <div className="lb-box" onClick={e => e.stopPropagation()}>
            <img src={SNAP_BASE + selected.url} alt="snapshot" className="lb-img"/>
            <div className="lb-info">
              <span className="lb-label">UNKNOWN VISITOR</span>
              <span className="lb-time">
                {formatName(selected.filename).date} · {formatName(selected.filename).time}
              </span>
            </div>
            <button className="lb-close" onClick={() => setSelected(null)}>✕ CLOSE</button>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">UNKNOWN VISITOR SNAPSHOTS</h1>
          <p className="page-sub">{snaps.length} captures stored · auto-saved on detection</p>
        </div>
        <button className="btn-ghost" onClick={load}>↻ REFRESH</button>
      </div>

      {loading ? (
        <div className="loading-state"><span className="loading-spinner"/>LOADING SNAPSHOTS...</div>
      ) : snaps.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">◎</div>
          <p>NO UNKNOWN VISITORS CAPTURED</p>
          <p className="empty-sub">Snapshots are automatically saved when an unregistered face is detected</p>
        </div>
      ) : (
        <div className="snp-grid">
          {snaps.map((s, i) => {
            const { date, time } = formatName(s.filename)
            return (
              <div key={i} className="snp-card" onClick={() => setSelected(s)}
                style={{animationDelay:`${i*0.04}s`}}>
                <div className="snp-img-wrap">
                  <img src={SNAP_BASE + s.url} alt="unknown" className="snp-img"/>
                  <div className="snp-overlay">
                    <span>⊡ VIEW</span>
                  </div>
                  <div className="snp-badge">UNKNOWN</div>
                </div>
                <div className="snp-info">
                  <span className="snp-time">{time}</span>
                  <span className="snp-date">{date}</span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}