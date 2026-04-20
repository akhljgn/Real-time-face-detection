import os
import torch

BASE_DIR      = r"C:\Main Project\Models"
APP_DIR       = r"C:\Main Project\Face_Detection"

PATHS = {
    "YOLO"     : os.path.join(BASE_DIR, "YOLO",       "best.pt"),
    "PNET"     : os.path.join(BASE_DIR, "faceCrop",   "pnet.pt"),
    "RNET"     : os.path.join(BASE_DIR, "faceCrop",   "rnet.pt"),
    "ONET"     : os.path.join(BASE_DIR, "faceCrop",   "onet.pt"),
    "ARCFACE"  : os.path.join(BASE_DIR, "InsightFace", "w600k_r50.onnx"),
    "DB"       : os.path.join(APP_DIR,  "data",       "face_database.db"),
    "SNAPSHOTS": os.path.join(APP_DIR,  "data",       "snapshots"),
    "UI"       : os.path.join(APP_DIR,  "ui",         "dist"),
}

os.makedirs(os.path.dirname(PATHS["DB"]),  exist_ok=True)
os.makedirs(PATHS["SNAPSHOTS"],            exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Detection config
YOLO_CONF           = 0.25
YOLO_IOU            = 0.70
YOLO_IMGSZ          = 416  #640
MIN_FACE_SIZE       = 20
MTCNN_THRESHOLDS    = [0.6, 0.7, 0.8]
PADDING             = 10
COSINE_THRESHOLD    = 0.40
EUCLIDEAN_THRESHOLD = 1.05
SKIP_FRAMES         = 7   # run ML every N frames 5

# Flask
FLASK_PORT = 5000

# Admin credentials (change these!)
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# ── OTP / SMTP (Gmail App Password) ─────────────────────
OTP_GMAIL_SENDER      = "vgross3318@gmail.com"   # Gmail that sends the code
OTP_GMAIL_APP_PASSWORD = "peeh qdus rzbn xlrz"         # 16-char App Password (with or without spaces)
OTP_ADMIN_EMAIL       = "a46681091@gmail.com"      # Where the OTP is delivered