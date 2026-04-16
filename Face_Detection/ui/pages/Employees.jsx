import { useState, useEffect } from 'react'
import { api } from '../src/api'
import AuthModal from '../components/AuthModal'
import './Employees.css'

export default function Employees() {
  const [persons,   setPersons]   = useState([])
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [showAuth,  setShowAuth]  = useState(false)
  const [pendingDel,setPendingDel]= useState(null)
  const [deleting,  setDeleting]  = useState(null)
  const [toast,     setToast]     = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.getPersons()
      setPersons(r.data.persons)
    } catch { showToast('Failed to load employees', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const showToast = (msg, type='success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const handleDeleteClick = (person_id) => {
    setPendingDel(person_id)
    setShowAuth(true)
  }

  const handleAuthSuccess = async () => {
    setShowAuth(false)
    if (!pendingDel) return
    setDeleting(pendingDel)
    try {
      await api.deletePerson(pendingDel)
      setPersons(p => p.filter(x => x.person_id !== pendingDel))
      showToast(`${pendingDel} removed from database`)
    } catch { showToast('Delete failed', 'error') }
    finally { setDeleting(null); setPendingDel(null) }
  }

  const filtered = persons.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.person_id.toLowerCase().includes(search.toLowerCase()) ||
    (p.department||'').toLowerCase().includes(search.toLowerCase()) ||
    (p.role||'').toLowerCase().includes(search.toLowerCase())
  )

  const accessColor = { admin:'acc-admin', standard:'acc-std', restricted:'acc-rest' }

  return (
    <div className="emp-page fade-in">
      {showAuth && (
        <AuthModal
          action="remove an employee"
          onSuccess={handleAuthSuccess}
          onClose={() => { setShowAuth(false); setPendingDel(null) }}
        />
      )}

      {toast && (
        <div className={`toast ${toast.type==='error'?'toast-err':'toast-ok'}`}>
          {toast.type==='error' ? '⚠' : '✓'} {toast.msg}
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">REGISTERED EMPLOYEES</h1>
          <p className="page-sub">{persons.length} profiles in database</p>
        </div>
        <button className="btn-ghost" onClick={load}>↻ REFRESH</button>
      </div>

      <div className="emp-toolbar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input
            className="search-input"
            placeholder="SEARCH BY NAME, ID, ROLE, DEPARTMENT..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <span className="result-count">
          {filtered.length} RESULT{filtered.length!==1?'S':''}
        </span>
      </div>

      {loading ? (
        <div className="loading-state">
          <span className="loading-spinner"/>
          LOADING DATABASE...
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">NO EMPLOYEES FOUND</div>
      ) : (
        <div className="emp-table-wrap">
          <table className="emp-table">
            <thead>
              <tr>
                {['EMPLOYEE ID','NAME','ROLE','DEPARTMENT','ACCESS','EMBEDDINGS','REGISTERED',''].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => (
                <tr key={p.person_id} className="emp-row">
                  <td><span className="id-chip">{p.person_id}</span></td>
                  <td className="td-name">{p.name}</td>
                  <td className="td-muted">{p.role||'—'}</td>
                  <td className="td-muted">{p.department||'—'}</td>
                  <td>
                    <span className={`acc-badge ${accessColor[p.access_level]||'acc-std'}`}>
                      {(p.access_level||'standard').toUpperCase()}
                    </span>
                  </td>
                  <td className="td-mono">{p.embedding_count}</td>
                  <td className="td-date">
                    {p.date_registered
                      ? new Date(p.date_registered).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'})
                      : '—'}
                  </td>
                  <td>
                    <button
                      className="del-btn"
                      onClick={() => handleDeleteClick(p.person_id)}
                      disabled={deleting === p.person_id}
                    >
                      {deleting === p.person_id ? '...' : 'REMOVE'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}