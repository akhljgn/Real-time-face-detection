import { useState } from 'react'
import { api } from '../src/api'
import './AuthModal.css'

export default function AuthModal({ onSuccess, onClose, action = 'continue' }) {
  const [user, setUser]   = useState('')
  const [pass, setPass]   = useState('')
  const [err,  setErr]    = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true); setErr('')
    try {
      await api.login(user, pass)
      onSuccess()
    } catch {
      setErr('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-icon">⬡</span>
          <div>
            <h2 className="modal-title">ADMIN ACCESS</h2>
            <p className="modal-sub">Authentication required to {action}</p>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <form onSubmit={submit} className="modal-form">
          <div className="field-group">
            <label>USERNAME</label>
            <input
              className="modal-input"
              value={user}
              onChange={e => setUser(e.target.value)}
              placeholder="admin"
              autoFocus
            />
          </div>
          <div className="field-group">
            <label>PASSWORD</label>
            <input
              className="modal-input"
              type="password"
              value={pass}
              onChange={e => setPass(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          {err && <div className="modal-err">⚠ {err}</div>}
          <button className="modal-btn" disabled={loading}>
            {loading ? 'VERIFYING...' : 'AUTHENTICATE'}
          </button>
        </form>
      </div>
    </div>
  )
}