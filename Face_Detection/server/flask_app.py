import os
import time
import threading
from flask import Flask, Response, jsonify, request, send_from_directory, session
from flask_cors import CORS
import config

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
        session["logged_in"] = True
        return jsonify({"success": True})
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
    while True:
        frame = state.get_frame()
        if frame:
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame +
                b"\r\n"
            )
        time.sleep(0.033)   # 30fps cap

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
@require_auth
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
@require_auth
def get_persons():
    from ml.database import list_persons
    return jsonify({"persons": list_persons()})

@app.route("/api/persons/<person_id>", methods=["DELETE"])
@require_auth
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
@require_auth
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
@require_auth
def serve_snapshot(filename):
    return send_from_directory(config.PATHS["SNAPSHOTS"], filename)


# ── Serve React app ───────────────────────────────────────
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    full = os.path.join(config.PATHS["UI"], path)
    if path and os.path.exists(full):
        return send_from_directory(config.PATHS["UI"], path)
    return send_from_directory(config.PATHS["UI"], "index.html")

def run_flask():
    app.run(
        host="0.0.0.0",    # ← 0.0.0.0 so any device on network can access
        port=config.FLASK_PORT,
        debug=False,
        use_reloader=False,
        threaded=True,
    )