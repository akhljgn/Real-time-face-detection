import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header   from '../components/Header'
import Footer   from '../components/Footer'
import LiveFeed   from '../pages/LiveFeed'
import Events     from '../pages/Events'
import Employees  from '../pages/Employees'
import Register   from '../pages/Register'
import Snapshots  from '../pages/Snapshots'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{display:'flex',flexDirection:'column',minHeight:'100vh'}}>
        <Header/>
        <main style={{flex:1}}>
          <Routes>
            <Route path="/"          element={<LiveFeed/>}  />
            <Route path="/events"    element={<Events/>}    />
            <Route path="/employees" element={<Employees/>} />
            <Route path="/register"  element={<Register/>}  />
            <Route path="/snapshots" element={<Snapshots/>} />
          </Routes>
        </main>
        <Footer/>
      </div>
    </BrowserRouter>
  )
}