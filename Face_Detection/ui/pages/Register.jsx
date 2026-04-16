import { useState, useRef } from 'react'
import { api } from '../src/api'
import AuthModal from '../components/AuthModal'
import './Register.css'

export default function Register() {
  const [form, setForm] = useState({
    person_id:'', name:'', role:'', department:'', access_level:'standard'
  })
  const [images,   setImages]   = useState([])
  const [previews, setPreviews] = useState([])
  const [showAuth, setShowAuth] = useState(false)
  const [loading,  setLoading]  = useState(false)
  const [result,   setResult]   = useState(null)
  const [error,    setError]    = useState('')
  const fileRef = useRef(null)

  const change = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }))

  const handleFiles = (files) => {
    const arr = Array.from(files).filter(f => f.type.startsWith('image/'))
    setImages(arr)
    setPreviews(arr.map(f => URL.createObjectURL(f)))
    setResult(null); setError('')
  }

  const onDrop = e => {
    e.preventDefault()
    handleFiles(e.dataTransfer.files)
  }

  // Clicking Register triggers auth modal first
  const handleRegisterClick = () => {
    if (!form.person_id || !form.name) { setError('Employee ID and Name are required.'); return }
    if (images.length === 0)           { setError('Please upload at least one image.'); return }
    setError('')
    setShowAuth(true)
  }

  const handleAuthSuccess = async () => {
    setShowAuth(false)
    setLoading(true); setError(''); setResult(null)
    const fd = new FormData()
    Object.entries(form).forEach(([k,v]) => fd.append(k,v))
    images.forEach(img => fd.append('images', img))
    try {
      const res = await api.register(fd)
      setResult(res.data)
      setForm({ person_id:'', name:'', role:'', department:'', access_level:'standard' })
      setImages([]); setPreviews([])
    } catch(e) {
      setError(e.response?.data?.error || 'Registration failed.')
    } finally { setLoading(false) }
  }

  return (
    <div className="reg-page fade-in">
      {showAuth && (
        <AuthModal
          action="register a new employee"
          onSuccess={handleAuthSuccess}
          onClose={() => setShowAuth(false)}
        />
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">REGISTER EMPLOYEE</h1>
          <p className="page-sub">Add a new person to the face recognition database</p>
        </div>
      </div>

      <div className="reg-grid">
        {/* Form */}
        <div className="reg-card">
          <div className="reg-card-header">
            <span className="card-label">EMPLOYEE DETAILS</span>
          </div>
          <div className="reg-fields">
            {[
              { name:'person_id',  label:'EMPLOYEE ID *',  placeholder:'e.g. EMP001' },
              { name:'name',       label:'FULL NAME *',    placeholder:'e.g. John Doe' },
              { name:'role',       label:'ROLE',           placeholder:'e.g. Engineer' },
              { name:'department', label:'DEPARTMENT',     placeholder:'e.g. IT' },
            ].map(f => (
              <div className="field-group" key={f.name}>
                <label>{f.label}</label>
                <input
                  className="reg-input"
                  name={f.name}
                  placeholder={f.placeholder}
                  value={form[f.name]}
                  onChange={change}
                />
              </div>
            ))}

            <div className="field-group full">
              <label>ACCESS LEVEL</label>
              <div className="access-pills">
                {['standard','admin','restricted'].map(lvl => (
                  <button
                    key={lvl}
                    type="button"
                    className={`access-pill ${form.access_level===lvl?'pill-active':''} pill-${lvl}`}
                    onClick={() => setForm(f=>({...f,access_level:lvl}))}
                  >
                    {lvl.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Upload */}
        <div className="reg-card">
          <div className="reg-card-header">
            <span className="card-label">FACE IMAGES</span>
            <span className="card-hint">10+ recommended for best accuracy</span>
          </div>

          <div
            className={`dropzone ${images.length>0?'dz-filled':''}`}
            onClick={() => fileRef.current.click()}
            onDrop={onDrop}
            onDragOver={e => e.preventDefault()}
          >
            <input ref={fileRef} type="file" multiple accept="image/*"
              style={{display:'none'}} onChange={e=>handleFiles(e.target.files)} />
            {images.length === 0 ? (
              <>
                <div className="dz-icon">⊡</div>
                <p className="dz-txt">DROP IMAGES HERE</p>
                <p className="dz-sub">or click to browse · JPG, PNG supported</p>
              </>
            ) : (
              <div className="preview-grid">
                {previews.slice(0,12).map((src,i) => (
                  <img key={i} src={src} className="preview-img" alt=""/>
                ))}
                {images.length > 12 && (
                  <div className="preview-more">+{images.length-12}</div>
                )}
              </div>
            )}
          </div>

          <div className="img-count">
            <span className={images.length>0?'count-ok':'count-none'}>
              {images.length > 0 ? `✓ ${images.length} IMAGE${images.length>1?'S':''} SELECTED` : 'NO IMAGES SELECTED'}
            </span>
            {images.length > 0 && (
              <button className="clear-btn"
                onClick={() => { setImages([]); setPreviews([]) }}>
                CLEAR
              </button>
            )}
          </div>
        </div>
      </div>

      {error  && <div className="reg-err">⚠ {error}</div>}
      {result && (
        <div className="reg-success">
          <span className="suc-icon">✓</span>
          <div>
            <strong>{result.name}</strong> registered successfully ·{' '}
            {result.embeddings} embeddings stored
            {result.failed > 0 && ` · ${result.failed} images skipped`}
          </div>
        </div>
      )}

      <button
        className="reg-submit"
        onClick={handleRegisterClick}
        disabled={loading}
      >
        {loading ? (
          <><span className="loading-spinner"/>PROCESSING...</>
        ) : (
          '⊞ REGISTER EMPLOYEE'
        )}
      </button>
    </div>
  )
}