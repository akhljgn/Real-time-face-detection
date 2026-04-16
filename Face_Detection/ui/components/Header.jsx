import { useState, useEffect } from 'react'
import { NavLink } from 'react-router-dom'
import { api } from '../src/api'
import './Header.css'

export default function Header() {
  const [time,    setTime]    = useState(new Date())
  const [fps,     setFps]     = useState(0)
  const [faces,   setFaces]   = useState(0)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    const t = setInterval(() => setTime(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  useEffect(() => {
    const t = setInterval(async () => {
      try {
        const r = await api.getStatus()
        setFps(r.data.fps)
        setFaces(r.data.face_count)
        setRunning(r.data.running)
      } catch {}
    }, 1000)
    return () => clearInterval(t)
  }, [])

  const pad = n => String(n).padStart(2,'0')
  const timeStr = `${pad(time.getHours())}:${pad(time.getMinutes())}:${pad(time.getSeconds())}`
  const dateStr = time.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}).toUpperCase()

  return (
    <header className="header">
      {/* Left: brand */}
      <div className="hdr-left">
        <div className="hdr-logo">
          <span className="logo-hex">⬡</span>
          <div>
            <span className="logo-name">SECUREVISION</span>
            <span className="logo-tag">ACCESS CONTROL SYSTEM</span>
          </div>
        </div>
      </div>

      {/* Center: nav */}
      <nav className="hdr-nav">
        {[
          { to:'/',           label:'LIVE FEED',  icon:'◉' },
          { to:'/events',     label:'EVENTS',     icon:'≡' },
          { to:'/employees',  label:'EMPLOYEES',  icon:'⊞' },
          { to:'/register',   label:'REGISTER',   icon:'＋' },
          { to:'/snapshots',  label:'SNAPSHOTS',  icon:'◎' },
        ].map(({ to, label, icon }) => (
          <NavLink key={to} to={to} className={({isActive}) =>
            `nav-link ${isActive ? 'nav-active' : ''}`
          }>
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Right: status */}
      <div className="hdr-right">
        <div className="hdr-stat">
          <span className="hdr-stat-label">CAM</span>
          <span className={`hdr-stat-val ${running?'val-green':'val-red'}`}>
            <span className={`status-dot ${running?'dot-green':'dot-red'}`}/>
            {running ? 'LIVE' : 'OFF'}
          </span>
        </div>
        <div className="hdr-stat">
          <span className="hdr-stat-label">FPS</span>
          <span className="hdr-stat-val val-mono">{fps}</span>
        </div>
        <div className="hdr-stat">
          <span className="hdr-stat-label">FACES</span>
          <span className="hdr-stat-val val-mono">{faces}</span>
        </div>
        <div className="hdr-time">
          <span className="time-clock">{timeStr}</span>
          <span className="time-date">{dateStr}</span>
        </div>
      </div>
    </header>
  )
}