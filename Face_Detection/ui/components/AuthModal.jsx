import { useState, useRef, useEffect } from 'react'
import { api } from '../src/api'
import './AuthModal.css'

/*
  Two-step mandatory authentication:
    Step 1 — Admin password (POST /api/login)
    Step 2 — Email OTP     (POST /api/otp/send → POST /api/otp/verify)
  Both steps are required; neither can be skipped.
*/

const STEP = { PASSWORD: 1, OTP: 2 }

export default function AuthModal({ onSuccess, onClose, action = 'continue' }) {
  const [step, setStep] = useState(STEP.PASSWORD)

  // Step 1 state
  const [user,    setUser]    = useState('')
  const [pass,    setPass]    = useState('')

  // Step 2 state
  const [otpSent,   setOtpSent]   = useState(false)
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', ''])
  const [otpEmail,  setOtpEmail]  = useState('')
  const [cooldown,  setCooldown]  = useState(0)
  const cooldownRef = useRef(null)
  const digitRefs   = useRef([])

  // Shared
  const [err,     setErr]     = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)

  /* ── Cooldown timer ─────────────────────────────────── */
  useEffect(() => {
    if (cooldown > 0) {
      cooldownRef.current = setTimeout(() => setCooldown(c => c - 1), 1000)
    }
    return () => clearTimeout(cooldownRef.current)
  }, [cooldown])

  /* ── Step 1: Password verify ────────────────────────── */
  const submitPassword = async (e) => {
    e.preventDefault()
    if (!user || !pass) { setErr('Both fields are required'); return }
    setLoading(true); setErr('')
    try {
      await api.login(user, pass)
      // Password passed → auto-send OTP and move to step 2
      await triggerOtp()
      setStep(STEP.OTP)
    } catch {
      setErr('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  /* ── OTP: send (also called internally after password) ─ */
  const triggerOtp = async () => {
    const r = await api.sendOtp()
    setOtpSent(true)
    setOtpEmail(r.data.masked_email || 'your admin email')
    setOtpDigits(['', '', '', '', '', ''])
    setCooldown(60)
    setTimeout(() => digitRefs.current[0]?.focus(), 80)
  }

  const resendOtp = async () => {
    if (cooldown > 0 || loading) return
    setLoading(true); setErr('')
    try {
      await triggerOtp()
    } catch {
      setErr('Failed to resend OTP. Check SMTP config.')
    } finally {
      setLoading(false)
    }
  }

  /* ── OTP: digit input ───────────────────────────────── */
  const handleDigit = (i, val) => {
    const clean = val.replace(/\D/g, '').slice(-1)
    const next = [...otpDigits]
    next[i] = clean
    setOtpDigits(next)
    if (clean && i < 5) digitRefs.current[i + 1]?.focus()
  }

  const handleDigitKey = (i, e) => {
    if (e.key === 'Backspace' && !otpDigits[i] && i > 0) {
      digitRefs.current[i - 1]?.focus()
    }
    if (e.key === 'Enter') submitOtp()
  }

  const handleDigitPaste = (e) => {
    e.preventDefault()
    const digits = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (!digits) return
    const next = [...otpDigits]
    for (let i = 0; i < 6; i++) next[i] = digits[i] || ''
    setOtpDigits(next)
    digitRefs.current[Math.min(digits.length, 5)]?.focus()
  }

  /* ── Step 2: OTP verify ─────────────────────────────── */
  const submitOtp = async () => {
    const code = otpDigits.join('')
    if (code.length < 6) { setErr('Enter all 6 digits'); return }
    setLoading(true); setErr('')
    try {
      await api.verifyOtp(code)
      setSuccess(true)
      setTimeout(onSuccess, 700)
    } catch (e) {
      setErr(e?.response?.data?.error || 'Invalid or expired OTP')
      setOtpDigits(['', '', '', '', '', ''])
      setTimeout(() => digitRefs.current[0]?.focus(), 80)
    } finally {
      setLoading(false)
    }
  }

  /* ── Render ─────────────────────────────────────────── */
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className={`modal-box ${success ? 'modal-box--success' : ''}`}
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ──────────────────────────────────── */}
        <div className="modal-header">
          <span className="modal-icon">⬡</span>
          <div>
            <h2 className="modal-title">ADMIN ACCESS</h2>
            <p className="modal-sub">Authentication required to {action}</p>
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {/* ── Step indicators ─────────────────────────── */}
        <div className="modal-steps">
          <div className={`modal-step ${step === STEP.PASSWORD ? 'step--active' : ''} ${step > STEP.PASSWORD ? 'step--done' : ''}`}>
            <span className="step-num">{step > STEP.PASSWORD ? '✓' : '1'}</span>
            <span className="step-label">PASSWORD</span>
          </div>
          <div className="step-connector" />
          <div className={`modal-step ${step === STEP.OTP ? 'step--active' : ''}`}>
            <span className="step-num">2</span>
            <span className="step-label">EMAIL OTP</span>
          </div>
        </div>

        {/* ─────────────────────────────────────────────
            STEP 1 — PASSWORD
        ───────────────────────────────────────────── */}
        {step === STEP.PASSWORD && (
          <form onSubmit={submitPassword} className="modal-form">
            <div className="step-desc">
              Enter your admin credentials to proceed to OTP verification.
            </div>
            <div className="field-group">
              <label>USERNAME</label>
              <input
                className="modal-input"
                value={user}
                onChange={e => setUser(e.target.value)}
                placeholder="admin"
                autoFocus
                autoComplete="username"
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
                autoComplete="current-password"
              />
            </div>
            {err && <div className="modal-err">⚠ {err}</div>}
            <button className="modal-btn" disabled={loading || success}>
              {loading ? 'VERIFYING...' : 'CONTINUE TO OTP →'}
            </button>
          </form>
        )}

        {/* ─────────────────────────────────────────────
            STEP 2 — OTP
        ───────────────────────────────────────────── */}
        {step === STEP.OTP && (
          <div className="modal-form">
            <div className="otp-sent-banner">
              <span className="otp-sent-dot" />
              Code sent to <strong>{otpEmail}</strong>
            </div>

            <div className="step-desc">
              Enter the 6-digit code sent to your admin email. The code expires in <strong>5 minutes</strong>.
            </div>

            {/* 6-digit boxes */}
            <div className="otp-digits" onPaste={handleDigitPaste}>
              {otpDigits.map((d, i) => (
                <input
                  key={i}
                  ref={el => digitRefs.current[i] = el}
                  className={`otp-digit ${d ? 'otp-digit--filled' : ''}`}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={d}
                  onChange={e => handleDigit(i, e.target.value)}
                  onKeyDown={e => handleDigitKey(i, e)}
                />
              ))}
            </div>

            {err && <div className="modal-err">⚠ {err}</div>}

            <button
              className="modal-btn"
              onClick={submitOtp}
              disabled={loading || success || otpDigits.join('').length < 6}
            >
              {success ? '✓ VERIFIED' : loading ? 'VERIFYING...' : 'VERIFY & AUTHENTICATE'}
            </button>

            <div className="otp-resend-row">
              <span>Didn&apos;t receive it?</span>
              <button
                className="otp-resend-btn"
                onClick={resendOtp}
                disabled={cooldown > 0 || loading}
              >
                {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend OTP'}
              </button>
            </div>
          </div>
        )}

        {/* ── Success overlay flash ────────────────────── */}
        {success && (
          <div className="modal-success-flash">
            <span className="modal-success-icon">✓</span>
          </div>
        )}
      </div>
    </div>
  )
}