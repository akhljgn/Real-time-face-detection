import os
import time
import threading
from flask import Flask, Response, jsonify, request, send_from_directory, session
from flask_cors import CORS
import config
import secrets
import smtplib
import time as _time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from waitress import serve

app = Flask(
    __name__,
    static_folder=config.PATHS["UI"],
    static_url_path=""
)
app.secret_key = "securevision_secret_key_2024"
CORS(app, supports_credentials=True)

# Worker reference — set from main.py
_worker = None

def set_worker(worker):
    global _worker
    _worker = worker


# ── Auth ─────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    if (data.get("username") == config.ADMIN_USER and
            data.get("password") == config.ADMIN_PASS):
        # Password step OK; OTP (if enabled) comes next.
        session["pw_ok"] = True
        return jsonify({"success": True})
    session.pop("pw_ok", None)
    session.pop("logged_in", None)
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/api/auth/check")
def auth_check():
    return jsonify({"logged_in": session.get("logged_in", False)})

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


# ── MJPEG stream ─────────────────────────────────────────
def _generate_frames():
    from ml.worker import state
    last = None
    last_sent = 0.0
    while True:
        frame = state.get_frame()
        if frame and frame is not last:
            if config.STREAM_FPS_CAP and config.STREAM_FPS_CAP > 0:
                now = time.time()
                min_dt = 1.0 / float(config.STREAM_FPS_CAP)
                if now - last_sent < min_dt:
                    time.sleep(min_dt - (now - last_sent))
                last_sent = time.time()
            last = frame
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame +
                b"\r\n"
            )
        else:
            time.sleep(0.005)

@app.route("/api/stream")
def stream():
    return Response(
        _generate_frames(),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )


# ── Status ───────────────────────────────────────────────
@app.route("/api/status")
def status():
    from ml.worker import state
    return jsonify({
        "fps"       : state.fps,
        "face_count": state.face_count,
        "running"   : _worker._running if _worker else False,
    })


# ── Events ───────────────────────────────────────────────
@app.route("/api/events")
# @require_auth
def events():
    from ml.worker import state
    f     = request.args.get("filter", "all")
    evts  = state.get_events(f)
    stats = state.get_stats()
    return jsonify({
        "events" : evts,
        "total"  : stats["total"],
        "known"  : stats["known"],
        "unknown": stats["unknown"],
    })


# ── Persons ──────────────────────────────────────────────
@app.route("/api/persons")
# @require_auth
def get_persons():
    from ml.database import list_persons
    return jsonify({"persons": list_persons()})

@app.route("/api/persons/<person_id>", methods=["DELETE"])
# @require_auth
def del_person(person_id):
    from ml.database import delete_person
    ok = delete_person(person_id)
    if ok and _worker:
        _worker.reload_db()
    return jsonify({"success": ok})


# ── Register ─────────────────────────────────────────────
@app.route("/api/register", methods=["POST"])
@require_auth
def register():
    from ml.database import register_person
    from PIL import Image
    import io

    person_id    = request.form.get("person_id","").strip()
    name         = request.form.get("name","").strip()
    role         = request.form.get("role","").strip()
    department   = request.form.get("department","").strip()
    access_level = request.form.get("access_level","standard").strip()
    files        = request.files.getlist("images")

    if not person_id or not name:
        return jsonify({"error": "person_id and name required"}), 400
    if not files:
        return jsonify({"error": "No images uploaded"}), 400

    pil_images = []
    for f in files:
        try:
            pil_images.append(Image.open(io.BytesIO(f.read())).convert("RGB"))
        except:
            pass

    if not pil_images:
        return jsonify({"error": "No valid images"}), 400

    result = register_person(
        person_id, name, role, department, access_level, pil_images
    )

    if result["success"] and _worker:
        _worker.reload_db()

    status_code = 201 if result["success"] else 400
    return jsonify(result), status_code


# ── Snapshots ────────────────────────────────────────────
@app.route("/api/snapshots")
# @require_auth
def list_snapshots():
    snap_dir = config.PATHS["SNAPSHOTS"]
    files    = sorted(
        [f for f in os.listdir(snap_dir) if f.endswith(".jpg")],
        reverse=True
    )[:100]
    return jsonify({
        "snapshots": [{"filename": f, "url": f"/snapshots/{f}"} for f in files]
    })

@app.route("/snapshots/<filename>")
# @require_auth
def serve_snapshot(filename):
    return send_from_directory(config.PATHS["SNAPSHOTS"], filename)


# ─── OTP STORE (in-memory, single-server) ────────────────────────────────────
# Format: { otp_code: str, expires_at: float, attempts: int }
_otp_store = {}
_OTP_TTL        = 300   # 5 minutes
_OTP_MAX_TRIES  = 5
 
 
def _mask_email(email: str) -> str:
    """Turn 'admin@gmail.com' → 'ad***@gmail.com'"""
    try:
        local, domain = email.split("@", 1)
        visible = local[:2] if len(local) > 2 else local[0]
        return f"{visible}***@{domain}"
    except Exception:
        return "***"
 
 
def _send_gmail_otp(code: str) -> None:
    """
    Send OTP via Gmail SMTP using an App Password.
    Raises smtplib.SMTPException or ConnectionRefusedError on failure.
    """
    sender   = config.OTP_GMAIL_SENDER        # e.g. "youraccount@gmail.com"
    password = config.OTP_GMAIL_APP_PASSWORD  # 16-char App Password (no spaces)
    receiver = config.OTP_ADMIN_EMAIL         # where the code is delivered
 
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"SecureVision Admin OTP: {code}"
    msg["From"]    = f"SecureVision <{sender}>"
    msg["To"]      = receiver
 
    plain = (
        f"Your SecureVision admin one-time code is: {code}\n\n"
        f"This code expires in 5 minutes.\n"
        f"If you did not request this, ignore this email."
    )
    html = f"""
    <div style="font-family:monospace;background:#0a0a0b;color:#e8e8f0;
                padding:32px;border-radius:8px;max-width:420px;margin:auto;">
      <div style="color:#00ff88;font-size:0.8rem;letter-spacing:.12em;
                  margin-bottom:18px;">⬡ SECUREVISION</div>
      <div style="font-size:0.85rem;color:#7a7a90;margin-bottom:24px;">
        Admin authentication code
      </div>
      <div style="background:#13131a;border:1px solid #1e1e28;border-radius:6px;
                  padding:24px;text-align:center;margin-bottom:24px;">
        <div style="font-size:2.4rem;letter-spacing:.35em;color:#00ff88;
                    font-weight:700;">{code}</div>
      </div>
      <div style="font-size:0.72rem;color:#3a3a50;line-height:1.6;">
        This code expires in <strong style="color:#7a7a90">5 minutes</strong>.<br>
        If you did not request this, ignore this email.
      </div>
    </div>
    """
 
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))
 
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as srv:
        srv.login(sender, password)
        srv.sendmail(sender, receiver, msg.as_string())
 
 
# ─── PASTE THESE ROUTES into flask_app.py (before serve_react) ───────────────
 
@app.route("/api/otp/send", methods=["POST"])
def otp_send():
    """Generate and email a fresh OTP. Rate-limited by cooldown on frontend."""
    if not session.get("pw_ok"):
        return jsonify({"error": "Password step required"}), 401

    code = "".join([str(secrets.randbelow(10)) for _ in range(6)])
    _otp_store.clear()  # invalidate any previous code
    _otp_store.update({
        "code"      : code,
        "expires_at": _time.time() + _OTP_TTL,
        "attempts"  : 0,
    })
    try:
        _send_gmail_otp(code)
    except Exception as e:
        _otp_store.clear()
        return jsonify({"error": f"SMTP error: {e}"}), 500
 
    masked = _mask_email(config.OTP_ADMIN_EMAIL)
    return jsonify({"success": True, "masked_email": masked})
 
 
@app.route("/api/otp/verify", methods=["POST"])
def otp_verify():
    """Verify submitted OTP code and set session on success."""
    if not session.get("pw_ok"):
        return jsonify({"error": "Password step required"}), 401

    data = request.get_json(silent=True) or {}
    submitted = str(data.get("code", "")).strip()
 
    store = _otp_store
    if not store:
        return jsonify({"error": "No OTP requested"}), 400
 
    if _time.time() > store.get("expires_at", 0):
        _otp_store.clear()
        return jsonify({"error": "OTP has expired"}), 400
 
    store["attempts"] = store.get("attempts", 0) + 1
    if store["attempts"] > _OTP_MAX_TRIES:
        _otp_store.clear()
        return jsonify({"error": "Too many attempts. Request a new code."}), 429
 
    if not secrets.compare_digest(submitted, store.get("code", "")):
        remaining = _OTP_MAX_TRIES - store["attempts"]
        return jsonify({"error": f"Invalid code. {remaining} attempts left."}), 401
 
    # Code is correct → authenticate the session exactly like /api/login does
    _otp_store.clear()
    session["logged_in"] = True
    return jsonify({"success": True})

@app.route("/api/persons/<person_id>", methods=["PUT"])
@require_auth
def update_person(person_id):
    from ml.database import update_person_info
    data = request.get_json(silent=True) or {}
    allowed = {"name", "role", "department", "access_level"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid fields"}), 400
    ok = update_person_info(person_id, updates)
    if ok and _worker:
        _worker.reload_db() 
    return jsonify({"success": ok})
 

# ── Serve React app ───────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    full = os.path.join(config.PATHS["UI"], path)
    if path and os.path.exists(full):
        return send_from_directory(config.PATHS["UI"], path)
    return send_from_directory(config.PATHS["UI"], "index.html")

def run_flask():
    import flask.cli as _cli
    _cli.show_server_banner = lambda *a, **k: None
    app.run(
        host="0.0.0.0",
        port=config.FLASK_PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )