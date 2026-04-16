import { useState, useEffect, useRef } from 'react'
import { api } from '../src/api'
import AuthModal from '../components/AuthModal'
import './Employees.css'

export default function Employees() {
  const [persons,    setPersons]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [search,     setSearch]     = useState('')
  const [showAuth,   setShowAuth]   = useState(false)
  const [authAction, setAuthAction] = useState(null)   // { type: 'delete'|'edit', person_id, draft? }
  const [deleting,   setDeleting]   = useState(null)
  const [editingId,  setEditingId]  = useState(null)   // person_id being edited
  const [editDraft,  setEditDraft]  = useState({})     // live form values
  const [saving,     setSaving]     = useState(false)
  const [toast,      setToast]      = useState(null)

  const load = async () => {
    setLoading(true)
    try {
      const r = await api.getPersons()
      setPersons(r.data.persons)
    } catch { showToast('Failed to load employees', 'error') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3500)
  }

  /* ── Delete flow ─────────────────────────────────────── */
  const handleDeleteClick = (person_id) => {
    setAuthAction({ type: 'delete', person_id })
    setShowAuth(true)
  }

  /* ── Edit flow ───────────────────────────────────────── */
  const handleEditClick = (person) => {
    setAuthAction({
      type: 'edit',
      person_id: person.person_id,
      draft: {
        name:         person.name         || '',
        role:         person.role         || '',
        department:   person.department   || '',
        access_level: person.access_level || 'standard',
      }
    })
    setShowAuth(true)
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditDraft({})
  }

  const handleSaveEdit = async () => {
    setSaving(true)
    try {
      await api.updatePerson(editingId, editDraft)
      setPersons(prev =>
        prev.map(p =>
          p.person_id === editingId ? { ...p, ...editDraft } : p
        )
      )
      showToast(`${editingId} updated successfully`)
      setEditingId(null)
      setEditDraft({})
    } catch {
      showToast('Update failed. Check backend.', 'error')
    } finally {
      setSaving(false)
    }
  }

  /* ── Auth modal success dispatcher ──────────────────── */
  const handleAuthSuccess = async () => {
    setShowAuth(false)
    if (!authAction) return

    if (authAction.type === 'delete') {
      const { person_id } = authAction
      setDeleting(person_id)
      try {
        await api.deletePerson(person_id)
        setPersons(p => p.filter(x => x.person_id !== person_id))
        showToast(`${person_id} removed from database`)
      } catch { showToast('Delete failed', 'error') }
      finally { setDeleting(null); setAuthAction(null) }

    } else if (authAction.type === 'edit') {
      // Auth passed → open the inline editor
      setEditingId(authAction.person_id)
      setEditDraft(authAction.draft)
      setAuthAction(null)
    }
  }

  const filtered = persons.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) ||
    p.person_id.toLowerCase().includes(search.toLowerCase()) ||
    (p.department || '').toLowerCase().includes(search.toLowerCase()) ||
    (p.role || '').toLowerCase().includes(search.toLowerCase())
  )

  const accessOptions = ['standard', 'admin', 'restricted']
  const accessColor   = { admin: 'acc-admin', standard: 'acc-std', restricted: 'acc-rest' }

  return (
    <div className="emp-page fade-in">

      {/* ── Auth Modal ─────────────────────────────────── */}
      {showAuth && (
        <AuthModal
          action={
            authAction?.type === 'edit'
              ? `edit ${authAction.person_id}`
              : 'remove an employee'
          }
          onSuccess={handleAuthSuccess}
          onClose={() => { setShowAuth(false); setAuthAction(null) }}
        />
      )}

      {/* ── Toast ──────────────────────────────────────── */}
      {toast && (
        <div className={`toast ${toast.type === 'error' ? 'toast-err' : 'toast-ok'}`}>
          {toast.type === 'error' ? '⚠' : '✓'} {toast.msg}
        </div>
      )}

      {/* ── Header ─────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <h1 className="page-title">REGISTERED EMPLOYEES</h1>
          <p className="page-sub">{persons.length} profiles in database</p>
        </div>
        <button className="btn-ghost" onClick={load}>↻ REFRESH</button>
      </div>

      {/* ── Search bar ─────────────────────────────────── */}
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
          {filtered.length} RESULT{filtered.length !== 1 ? 'S' : ''}
        </span>
      </div>

      {/* ── Table ──────────────────────────────────────── */}
      {loading ? (
        <div className="loading-state">
          <span className="loading-spinner" />
          LOADING DATABASE...
        </div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">NO EMPLOYEES FOUND</div>
      ) : (
        <div className="emp-table-wrap">
          <table className="emp-table">
            <thead>
              <tr>
                {['EMPLOYEE ID', 'NAME', 'ROLE', 'DEPARTMENT', 'ACCESS', 'EMBEDDINGS', 'REGISTERED', ''].map(h => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(p => {
                const isEditing = editingId === p.person_id

                return (
                  <tr
                    key={p.person_id}
                    className={`emp-row ${isEditing ? 'emp-row--editing' : ''}`}
                  >
                    {/* ── Employee ID (never editable) ── */}
                    <td><span className="id-chip">{p.person_id}</span></td>

                    {/* ── Name ── */}
                    <td className="td-name">
                      {isEditing ? (
                        <input
                          className="inline-input"
                          value={editDraft.name}
                          onChange={e => setEditDraft(d => ({ ...d, name: e.target.value }))}
                          placeholder="Full name"
                        />
                      ) : p.name}
                    </td>

                    {/* ── Role ── */}
                    <td className="td-muted">
                      {isEditing ? (
                        <input
                          className="inline-input"
                          value={editDraft.role}
                          onChange={e => setEditDraft(d => ({ ...d, role: e.target.value }))}
                          placeholder="Role"
                        />
                      ) : (p.role || '—')}
                    </td>

                    {/* ── Department ── */}
                    <td className="td-muted">
                      {isEditing ? (
                        <input
                          className="inline-input"
                          value={editDraft.department}
                          onChange={e => setEditDraft(d => ({ ...d, department: e.target.value }))}
                          placeholder="Department"
                        />
                      ) : (p.department || '—')}
                    </td>

                    {/* ── Access level ── */}
                    <td>
                      {isEditing ? (
                        <select
                          className="inline-select"
                          value={editDraft.access_level}
                          onChange={e => setEditDraft(d => ({ ...d, access_level: e.target.value }))}
                        >
                          {accessOptions.map(opt => (
                            <option key={opt} value={opt}>{opt.toUpperCase()}</option>
                          ))}
                        </select>
                      ) : (
                        <span className={`acc-badge ${accessColor[p.access_level] || 'acc-std'}`}>
                          {(p.access_level || 'standard').toUpperCase()}
                        </span>
                      )}
                    </td>

                    {/* ── Embeddings (read-only) ── */}
                    <td className="td-mono">{p.embedding_count}</td>

                    {/* ── Date ── */}
                    <td className="td-date">
                      {p.date_registered
                        ? new Date(p.date_registered).toLocaleDateString('en-GB', {
                            day: '2-digit', month: 'short', year: 'numeric'
                          })
                        : '—'}
                    </td>

                    {/* ── Actions ── */}
                    <td>
                      {isEditing ? (
                        <div className="action-group">
                          <button
                            className="save-btn"
                            onClick={handleSaveEdit}
                            disabled={saving}
                          >
                            {saving ? '...' : '✓ SAVE'}
                          </button>
                          <button
                            className="cancel-btn"
                            onClick={handleCancelEdit}
                            disabled={saving}
                          >
                            ✕
                          </button>
                        </div>
                      ) : (
                        <div className="action-group">
                          <button
                            className="edit-btn"
                            onClick={() => handleEditClick(p)}
                            disabled={deleting === p.person_id}
                          >
                            ✎ EDIT
                          </button>
                          <button
                            className="del-btn"
                            onClick={() => handleDeleteClick(p.person_id)}
                            disabled={deleting === p.person_id}
                          >
                            {deleting === p.person_id ? '...' : 'REMOVE'}
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}