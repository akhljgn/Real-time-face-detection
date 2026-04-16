import { useEffect, useState } from 'react'
import { api, STREAM_URL, SNAP_BASE } from '../src/api'
import './LiveFeed.css'

export default function LiveFeed() {
  const [stats,     setStats]     = useState({ total:0, known:0, unknown:0 })
  const [events,    setEvents]    = useState([])
  const [filter,    setFilter]    = useState('all')
  const [fps,       setFps]       = useState(0)
  const [faceCount, setFaceCount] = useState(0)
  const [profiles,  setProfiles]  = useState(0)

  useEffect(() => {
    api.getPersons().then(r => setProfiles(r.data.persons.length)).catch(()=>{})
  }, [])

  useEffect(() => {
    const load = async () => {
      try {
        const r = await api.getEvents(filter)
        setEvents(r.data.events || [])
        setStats({ total: r.data.total, known: r.data.known, unknown: r.data.unknown })
      } catch {}
    }
    load()
    const t = setInterval(load, 2000)
    return () => clearInterval(t)
  }, [filter])

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const r = await api.getStatus()
        setFps(r.data.fps)
        setFaceCount(r.data.face_count)
      } catch {}
    }, 1000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="lf-page fade-in">
      {/* Stats bar */}
      <div className="lf-stats">
        {[
          { label:'PROFILES IN DB', value: profiles,      color:'var(--blue)' },
          { label:'TODAY ENTRIES',  value: stats.total,   color:'var(--txt)' },
          { label:'IDENTIFIED',     value: stats.known,   color:'var(--green)' },
          { label:'UNKNOWN',        value: stats.unknown, color:'var(--red)' },
          { label:'FPS',            value: fps,           color:'var(--amber)' },
          { label:'FACES NOW',      value: faceCount,     color:'var(--txt)' },
        ].map((s,i) => (
          <div className="lf-stat" key={i}>
            <span className="lf-stat-val" style={{ color: s.color }}>{s.value}</span>
            <span className="lf-stat-lbl">{s.label}</span>
          </div>
        ))}
      </div>

      <div className="lf-main">
        {/* Video feed */}
        <div className="lf-video-wrap">
          <div className="lf-video-header">
            <div className="lf-cam-info">
              <span className="live-dot"/>
              <span className="live-txt">LIVE</span>
              <span className="cam-name">CAM 01 · MAIN CAMERA</span>
            </div>
            <div className="lf-cam-meta">
              <span>{fps} FPS</span>
              <span>·</span>
              <span>{faceCount} FACE{faceCount!==1?'S':''}</span>
              <span>·</span>
              <span>1280×720</span>
            </div>
          </div>

          <div className="lf-video-body">
            <img
              src={STREAM_URL}
              className="lf-stream"
              alt="Live feed"
            />
            {/* Scan line effect */}
            <div className="scan-line"/>
            {/* Corner brackets */}
            <div className="corner tl"/><div className="corner tr"/>
            <div className="corner bl"/><div className="corner br"/>
          </div>

          <div className="lf-video-footer">
            <span className="monochip green">● SYSTEM ACTIVE</span>
            <span className="monochip">YOLO + MTCNN + ARCFACE</span>
            <span className="monochip">AES-256 ENCRYPTED</span>
          </div>
        </div>

        {/* Event log */}
        <div className="lf-events">
          <div className="lf-events-header">
            <span className="section-title">EVENT LOG</span>
            <span className="event-total">{stats.total} total</span>
          </div>

          <div className="lf-filters">
            {['all','known','unknown'].map(f => (
              <button key={f}
                className={`filter-pill ${filter===f?'filter-active':''}`}
                onClick={() => setFilter(f)}>
                {f === 'all' ? 'ALL' : f === 'known' ? 'IDENTIFIED' : 'UNKNOWN'}
              </button>
            ))}
          </div>

          <div className="lf-event-list">
            {events.length === 0
              ? <div className="events-empty">NO EVENTS RECORDED</div>
              : events.map((ev, i) => (
                <div key={i}
                  className={`event-row ${ev.matched ? 'ev-known' : 'ev-unknown'}`}
                  style={{ animationDelay: `${i * 0.03}s` }}>
                  <div className="ev-avatar">
                    {ev.snapshot_url
                      ? <img src={SNAP_BASE + ev.snapshot_url} alt=""/>
                      : <span>{(ev.name||'?')[0].toUpperCase()}</span>
                    }
                  </div>
                  <div className="ev-info">
                    <span className="ev-name">{ev.name}</span>
                    <span className="ev-sub">
                      {ev.matched
                        ? `${ev.role||'—'} · ${ev.department||'—'}`
                        : 'UNREGISTERED VISITOR'}
                    </span>
                  </div>
                  <div className="ev-right">
                    <span className={`ev-badge ${ev.matched?'badge-ok':'badge-warn'}`}>
                      {ev.matched ? 'GRANTED' : 'UNKNOWN'}
                    </span>
                    <span className="ev-time">{ev.date} {ev.timestamp}</span>
                  </div>
                </div>
              ))
            }
          </div>
        </div>
      </div>
    </div>
  )
}