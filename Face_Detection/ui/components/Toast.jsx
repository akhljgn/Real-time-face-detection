import { useEffect, useState } from 'react'
import './Toast.css'

/*
  Usage:
    <Toast message="Employee registered successfully" type="success" onDone={() => setToast(null)} />
  
  Props:
    message  — string to display
    type     — 'success' | 'error'
    duration — ms before auto-dismiss (default 3500)
    onDone   — called after dismiss animation completes
*/

export default function Toast({ message, type = 'success', duration = 3500, onDone }) {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const hide  = setTimeout(() => setVisible(false), duration)
    const clear = setTimeout(() => onDone?.(), duration + 350)
    return () => { clearTimeout(hide); clearTimeout(clear) }
  }, [duration, onDone])

  return (
    <div className={`toast toast--${type} ${visible ? 'toast--in' : 'toast--out'}`}>
      <span className="toast-icon">{type === 'success' ? '✓' : '⚠'}</span>
      <span className="toast-msg">{message}</span>
    </div>
  )
}