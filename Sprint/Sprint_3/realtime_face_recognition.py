import os
import sqlite3
import time
import warnings
from datetime import datetime
import cv2 
import numpy as np
import torch
import onnxruntime as ort
from PIL import Image, ImageOps
from ultralytics import YOLO
from facenet_pytorch import MTCNN
from facenet_pytorch.models.mtcnn import PNet, RNet, ONet

warnings.filterwarnings("ignore")

# ============================================================
#  CONFIGURATIONS
# ============================================================

class Config:
    def __init__(self):
        # Base paths matching `modelTraining.ipynb` & `register_ppl.py`
        self.BASE_DIR = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs"
        self.YOLO_WEIGHTS   = os.path.join(self.BASE_DIR, "YOLO", "best.pt")
        self.PNET_WEIGHTS   = os.path.join(self.BASE_DIR, "faceCrop", "pnet.pt")
        self.RNET_WEIGHTS   = os.path.join(self.BASE_DIR, "faceCrop", "rnet.pt")
        self.ONET_WEIGHTS   = os.path.join(self.BASE_DIR, "faceCrop", "onet.pt")
        self.ARCFACE_PATH   = os.path.join(self.BASE_DIR, "InsightFace", "w600k_r50.onnx")
        self.DB_PATH        = os.path.join(self.BASE_DIR, "database", "face_database.db")
        
        self.MIN_FACE_SIZE = 20
        self.THRESHOLDS    = [0.6, 0.7, 0.8]
        self.PADDING       = 10
        
        self.YOLO_CONF     = 0.25
        self.YOLO_IOU      = 0.7
        self.YOLO_IMGSZ    = 640
        
        self.COSINE_THRESHOLD    = 0.40  # Generous matches
        self.EUCLIDEAN_THRESHOLD = 1.05
        
        self.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

cfg = Config()

# ============================================================
#  DATABASE & VERIFIER
# ============================================================

class FaceDatabase:
    def __init__(self):
        self.conn = sqlite3.connect(cfg.DB_PATH, check_same_thread=False)

    def load_all_embeddings(self) -> dict:
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(persons)")
        cols = [row[1] for row in cur.fetchall()]
        id_col = "person_id" if "person_id" in cols else "employee_id"

        cur.execute(f"""
            SELECT p.id, p.{id_col}, p.name, p.role,
                   p.department, p.access_level, e.embedding
            FROM persons p
            JOIN embeddings e ON e.person_id = p.id
        """)
        db = {}
        for pid, eid, name, role, dept, access, blob in cur.fetchall():
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            if pid not in db:
                db[pid] = {
                    "meta": {"person_id": eid, "name": name,
                             "role": role, "department": dept,
                             "access_level": access},
                    "embeddings": []
                }
            db[pid]["embeddings"].append(vec)
        for pid in db:
            db[pid]["embeddings"] = np.stack(db[pid]["embeddings"])
        return db

    def close(self):
        self.conn.close()

class IdentityVerifier:
    @staticmethod
    def cosine_sim(a, b):
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))

    @staticmethod
    def euclidean_dist(a, b):
        return float(np.linalg.norm(a - b))

    def verify(self, query_vec, db) -> dict:
        best = {"pid": None, "meta": None, "cos": -1.0, "euc": 9999.0}
        for pid, data in db.items():
            for stored in data["embeddings"]:
                cos = self.cosine_sim(query_vec, stored)
                euc = self.euclidean_dist(query_vec, stored)
                if cos > best["cos"]:
                    best = {"pid": pid, "meta": data["meta"],
                            "cos": cos, "euc": euc}

        cos_match = best["cos"] >= cfg.COSINE_THRESHOLD
        euc_match = best["euc"] <= cfg.EUCLIDEAN_THRESHOLD

        if cos_match and euc_match:
            m = best["meta"]
            return {
                "identity"      : m["name"],
                "person_id"     : m["person_id"],
                "role"          : m["role"],
                "department"    : m["department"],
                "access_level"  : m["access_level"],
                "cosine_score"  : round(best["cos"], 4),
                "euclidean_dist": round(best["euc"], 4),
                "matched"       : True,
            }
        return {
            "identity": "Unknown", "person_id": "", "role": "",
            "department": "", "access_level": "none",
            "cosine_score": round(best["cos"], 4),
            "euclidean_dist": round(best["euc"], 4),
            "matched": False,
        }

# ============================================================
#  MAIN SCRIPT START
# ============================================================

def main():
    print(f"[INFO] Initializing Real-Time Recognition on {cfg.DEVICE.upper()}")

    # 1. Load YOLO
    print("[INFO] Loading YOLO Face Detector...")
    yolo_model = YOLO(cfg.YOLO_WEIGHTS)

    # 2. Load MTCNN
    print("[INFO] Loading MTCNN...")
    pnet = PNet().to(cfg.DEVICE)
    rnet = RNet().to(cfg.DEVICE)
    onet = ONet().to(cfg.DEVICE)
    pnet.load_state_dict(torch.load(cfg.PNET_WEIGHTS, map_location=cfg.DEVICE))
    rnet.load_state_dict(torch.load(cfg.RNET_WEIGHTS, map_location=cfg.DEVICE))
    onet.load_state_dict(torch.load(cfg.ONET_WEIGHTS, map_location=cfg.DEVICE))
    pnet.eval(); rnet.eval(); onet.eval()
    
    mtcnn = MTCNN(keep_all=True, device=cfg.DEVICE, min_face_size=cfg.MIN_FACE_SIZE, thresholds=cfg.THRESHOLDS, post_process=False)
    mtcnn.pnet = pnet; mtcnn.rnet = rnet; mtcnn.onet = onet

    # 3. Load ArcFace
    print("[INFO] Loading ArcFace...")
    arcface_session = ort.InferenceSession(cfg.ARCFACE_PATH, providers=["CPUExecutionProvider"])
    arcface_input   = arcface_session.get_inputs()[0].name

    def get_embedding(pil_img):
        img = pil_img.convert("RGB").resize((112, 112), Image.BILINEAR)
        bgr = np.array(img)[:, :, ::-1].astype(np.float32)
        bgr = (bgr - 127.5) / 127.5
        inp = np.transpose(bgr, (2, 0, 1))[np.newaxis]
        try:
            feat = arcface_session.run(None, {arcface_input: inp})[0][0]
            feat = feat.astype(np.float32)
            norm = np.linalg.norm(feat)
            return feat / norm if norm > 0 else feat
        except Exception as e:
            return None

    # 4. Load Database
    print("[INFO] Loading Database...")
    db = FaceDatabase()
    db_cache = db.load_all_embeddings()
    verifier = IdentityVerifier()
    print(f"[INFO] Loaded {len(db_cache)} profiles from DB.")

    # 5. Start Webcam
    print("[INFO] Starting Webcam...")
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("[ERROR] Could not open webcam.")
        return

    # Tracking variables to reduce lag
    process_this_frame = 0
    PROCESS_EVERY_N_FRAMES = 5 # Run heavy ML every 5 frames
    tracked_faces = [] # Store recent bounding boxes and identities

    print("\n" + "="*50)
    print("   FACE RECOGNITION LIVE FEED IS RUNNING")
    print("   Press 'q' in the video window to quit")
    print("="*50 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[ERROR] Failed to grab frame.")
            break

        # OpenCV reads in BGR, we convert to RGB for Pil/Models
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # We only run the full pipeline periodically to maintain FPS
        if process_this_frame == 0:
            pil_frame = Image.fromarray(rgb_frame)
            tracked_faces = [] # Reset

            # YOLO predicts Human Boxes
            yolo_results = yolo_model.predict(source=pil_frame, conf=cfg.YOLO_CONF, iou=cfg.YOLO_IOU, imgsz=cfg.YOLO_IMGSZ, device=cfg.DEVICE, verbose=False)
            human_boxes = yolo_results[0].boxes

            for box in human_boxes:
                try:
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    
                    # Pad region
                    hx1, hy1 = max(0, x1 - cfg.PADDING), max(0, y1 - cfg.PADDING)
                    hx2, hy2 = min(pil_frame.width, x2 + cfg.PADDING), min(pil_frame.height, y2 + cfg.PADDING)
                    human_crop = pil_frame.crop((hx1, hy1, hx2, hy2))
                    
                    # MTCNN for precise face box
                    face_boxes, probs = mtcnn.detect(human_crop)
                    
                    if face_boxes is not None:
                        best_idx = int(np.argmax(probs))
                        fx1, fy1, fx2, fy2 = [int(v) for v in face_boxes[best_idx]]
                        
                        fx1, fy1 = max(0, fx1), max(0, fy1)
                        fx2, fy2 = min(human_crop.width, fx2), min(human_crop.height, fy2)
                        
                        face_crop = human_crop.crop((fx1, fy1, fx2, fy2)).resize((160, 160), Image.BILINEAR)
                        
                        # ArcFace Vector
                        vec = get_embedding(face_crop)
                        
                        # Verify against DB
                        identity = verifier.verify(vec, db_cache) if vec is not None else {"matched": False, "identity": "Unknown"}
                        
                        # Store total coordinate back to full frame
                        final_x1, final_y1 = hx1 + fx1, hy1 + fy1
                        final_x2, final_y2 = hx1 + fx2, hy1 + fy2
                        
                        tracked_faces.append({
                            "box": (final_x1, final_y1, final_x2, final_y2),
                            "info": identity
                        })
                except Exception as e:
                    pass

        process_this_frame = (process_this_frame + 1) % PROCESS_EVERY_N_FRAMES

        # Draw the cached tracking results very fast on every frame
        for face in tracked_faces:
            x1, y1, x2, y2 = face["box"]
            info = face["info"]
            
            # Colors: Green for match, Red for unknown (BGR format)
            color = (0, 255, 0) if info.get("matched") else (0, 0, 255)
            
            # Draw Box
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            
            # Draw Title Background & Text
            title = info.get("identity", "Unknown")
            cv2.rectangle(frame, (x1, y1 - 35), (x2, y1), color, cv2.FILLED)
            cv2.putText(frame, title, (x1 + 6, y1 - 6), cv2.FONT_HERSHEY_DUPLEX, 0.8, (255, 255, 255), 1)

            # Optional: Display Role & Dept if matched
            if info.get("matched"):
                role = info.get("role", "")
                dept = info.get("department", "")
                sub_text = f"{role} | {dept}"
                cv2.putText(frame, sub_text, (x1 + 6, y2 + 25), cv2.FONT_HERSHEY_DUPLEX, 0.6, color, 1)

        # Show the Video Stream
        cv2.imshow('Real-Time Face Recognition', frame)

        # Hit 'q' to quit
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release resources
    print("[INFO] Shutting down...")
    cap.release()
    cv2.destroyAllWindows()
    db.close()

if __name__ == "__main__":
    main()
