import { useState, useEffect } from 'react'
import { api, SNAP_BASE } from '../src/api'
import './Events.css'

export default function Events() {
  const [events,  setEvents]  = useState([])
  const [stats,   setStats]   = useState({ total:0, known:0, unknown:0 })
  const [filter,  setFilter]  = useState('all')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const r = await api.getEvents(filter)
        setEvents(r.data.events || [])
        setStats({ total:r.data.total, known:r.data.known, unknown:r.data.unknown })
      } catch {} finally { setLoading(false) }
    }
    load()
    const t = setInterval(load, 3000)
    return () => clearInterval(t)
  }, [filter])

  return (
    <div className="evp-page fade-in">
      <div className="page-header">
        <div>
          <h1 className="page-title">EVENT LOG</h1>
          <p className="page-sub">All detection events this session</p>
        </div>
        <div className="evp-stats">
          {[
            { label:'TOTAL',      value: stats.total,   color:'var(--txt)' },
            { label:'IDENTIFIED', value: stats.known,   color:'var(--green)' },
            { label:'UNKNOWN',    value: stats.unknown, color:'var(--red)' },
          ].map(s => (
            <div className="evp-stat" key={s.label}>
              <span className="evp-stat-val" style={{color:s.color}}>{s.value}</span>
              <span className="evp-stat-lbl">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="evp-filters">
        {['all','known','unknown'].map(f => (
          <button key={f}
            className={`filter-pill ${filter===f?'filter-active':''}`}
            onClick={() => setFilter(f)}>
            {f==='all'?'ALL EVENTS':f==='known'?'IDENTIFIED ONLY':'UNKNOWN ONLY'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-state"><span className="loading-spinner"/>LOADING EVENTS...</div>
      ) : events.length === 0 ? (
        <div className="empty-state">NO EVENTS RECORDED</div>
      ) : (
        <div className="evp-list">
          {events.map((ev, i) => (
            <div key={i}
              className={`evp-card ${ev.matched?'evc-known':'evc-unknown'}`}
              style={{animationDelay:`${i*0.02}s`}}>

              <div className="evc-avatar">
                {ev.snapshot_url
                  ? <img src={SNAP_BASE+ev.snapshot_url} alt=""/>
                  : <span>{(ev.name||'?')[0].toUpperCase()}</span>
                }
              </div>

              <div className="evc-body">
                <div className="evc-top">
                  <span className="evc-name">{ev.name}</span>
                  <span className={`ev-badge ${ev.matched?'badge-ok':'badge-warn'}`}>
                    {ev.matched ? '✓ ACCESS GRANTED' : '⚠ UNKNOWN VISITOR'}
                  </span>
                </div>
                <div className="evc-meta">
                  {ev.matched && ev.role && <span className="meta-chip">{ev.role}</span>}
                  {ev.matched && ev.department && <span className="meta-chip">{ev.department}</span>}
                  {ev.matched && ev.access_level && (
                    <span className="meta-chip chip-access">{ev.access_level.toUpperCase()}</span>
                  )}
                  {ev.cosine_score > 0 && (
                    <span className="meta-chip chip-score">
                      SCORE: {ev.cosine_score.toFixed(3)}
                    </span>
                  )}
                </div>
              </div>

              <div className="evc-time">
                <span className="evc-clock">{ev.timestamp}</span>
                <span className="evc-date">{ev.date}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}