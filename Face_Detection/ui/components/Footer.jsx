import './Footer.css'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-left">
          <span className="footer-logo">⬡ SECUREVISION</span>
          <span className="footer-sep">·</span>
          <span className="footer-txt">Access Control & Face Recognition System</span>
        </div>
        <div className="footer-right">
          <span className="footer-txt">CAM 01 · MAIN ENTRANCE</span>
          <span className="footer-sep">·</span>
          <span className="footer-txt">v1.0.0</span>
          <span className="footer-sep">·</span>
          <span className="footer-txt" style={{color:'var(--green)'}}>● SYSTEM OPERATIONAL</span>
        </div>
      </div>
    </footer>
  )
}