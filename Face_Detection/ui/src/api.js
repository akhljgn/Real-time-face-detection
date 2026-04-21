import axios from 'axios'
 
const BASE = 'http://127.0.0.1:5000/api'
const ax   = axios.create({ baseURL: BASE, withCredentials: true })
 
export const api = {
  login        : (u, p) => ax.post('/login',  { username: u, password: p }),
  logout       : ()     => ax.post('/logout'),
  authCheck    : ()     => ax.get('/auth/check'),
  getStatus    : ()     => ax.get('/status'),
  getEvents    : (f='all') => ax.get(`/events?filter=${f}`),
  getPersons   : ()     => ax.get('/persons'),
  deletePerson : (id)   => ax.delete(`/persons/${id}`),
  getSnapshots : ()     => ax.get('/snapshots'),
  register     : (fd)   => ax.post('/register', fd, {
  headers: { 'Content-Type': 'multipart/form-data' }
  }),
  sendOtp: ()     => ax.post('/otp/send'),
  verifyOtp: (code) => ax.post('/otp/verify', { code }),
  updatePerson: (person_id, data) => ax.put(`/persons/${person_id}`, data),
}
 
export const STREAM_URL = 'http://127.0.0.1:5000/api/stream'
export const SNAP_BASE  = 'http://127.0.0.1:5000'