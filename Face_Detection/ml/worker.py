import os
import time
import threading
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import config
from ml.loader   import get_models
from ml.database import load_embeddings
from ml.verifier import verify

class SharedState:
    """Thread-safe container shared between worker and Flask."""
    def __init__(self):
        self._lock       = threading.Lock()
        self.latest_jpeg = None
        self.fps         = 0
        self.face_count  = 0
        self.event_log   = []
        self._seen_timer = {}

    def set_frame(self, jpeg_bytes):
        with self._lock:
            self.latest_jpeg = jpeg_bytes

    def get_frame(self):
        with self._lock:
            return self.latest_jpeg

    def add_event(self, info, snapshot_url=None):
        now = time.time()
        key = info.get("person_id") or "unknown"
        with self._lock:
            last = self._seen_timer.get(key, 0)
            if now - last < 10:
                return
            self._seen_timer[key] = now
            self.event_log.insert(0, {
                "timestamp"   : datetime.now().strftime("%H:%M:%S"),
                "date"        : datetime.now().strftime("%Y-%m-%d"),
                "matched"     : info.get("matched", False),
                "name"        : info.get("identity", "Unknown"),
                "person_id"   : info.get("person_id", ""),
                "role"        : info.get("role", ""),
                "department"  : info.get("department", ""),
                "access_level": info.get("access_level", "none"),
                "cosine_score": info.get("cosine_score", 0),
                "snapshot_url": snapshot_url,
            })
            if len(self.event_log) > 500:
                self.event_log.pop()

    def get_events(self, filter_by="all"):
        with self._lock:
            evts = self.event_log
            if filter_by == "known":
                evts = [e for e in evts if e["matched"]]
            elif filter_by == "unknown":
                evts = [e for e in evts if not e["matched"]]
            return list(evts[:200])

    def get_stats(self):
        with self._lock:
            total   = len(self.event_log)
            known   = sum(1 for e in self.event_log if e["matched"])
            unknown = total - known
            return {"total": total, "known": known, "unknown": unknown}


# Global shared state
state = SharedState()


class RecognitionWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self._running  = False
        self._db_cache = {}

    def reload_db(self):
        self._db_cache = load_embeddings()

    def stop(self):
        self._running = False

    def run(self):
        print("[ML] Loading models...")
        models  = get_models()
        yolo    = models["yolo"]
        mtcnn   = models["mtcnn"]
        arcface = models["arcface"]
        device  = models["device"]

        self._db_cache = load_embeddings()
        print(f"[ML] Ready · {len(self._db_cache)} profiles loaded")

        cap = cv2.VideoCapture(0) #0 for default webcam, 1 for external
        if not cap.isOpened():
            print("[ML] ERROR: webcam unavailable")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_FPS,          30)
        cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

        idx           = 0
        tracked       = []
        fps_count     = 0
        fps_time      = time.time()
        arcface_input = arcface.get_inputs()[0].name
        self._running = True

        while self._running:
            ret, frame = cap.read()
            if not ret:
                break

            fps_count += 1
            now = time.time()
            if now - fps_time >= 1.0:
                state.fps = fps_count
                fps_count = 0
                fps_time  = now

            if idx % config.SKIP_FRAMES == 0:
                rgb     = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil     = Image.fromarray(rgb)
                tracked = []

                results = yolo.predict(
                    source=pil, conf=config.YOLO_CONF,
                    iou=config.YOLO_IOU, imgsz=config.YOLO_IMGSZ,
                    device=device, verbose=False
                )

                for box in results[0].boxes:
                    try:
                        x1,y1,x2,y2 = [int(v) for v in box.xyxy[0].tolist()]
                        hx1=max(0,x1-config.PADDING); hy1=max(0,y1-config.PADDING)
                        hx2=min(pil.width, x2+config.PADDING)
                        hy2=min(pil.height,y2+config.PADDING)
                        crop = pil.crop((hx1,hy1,hx2,hy2))

                        fboxes, probs = mtcnn.detect(crop)
                        if fboxes is None:
                            continue

                        bi = int(np.argmax(probs))
                        fx1,fy1,fx2,fy2 = [int(v) for v in fboxes[bi]]
                        fx1=max(0,fx1); fy1=max(0,fy1)
                        fx2=min(crop.width,fx2); fy2=min(crop.height,fy2)

                        fface = crop.crop(
                            (fx1,fy1,fx2,fy2)
                        ).resize((160,160), Image.BILINEAR)

                        img  = fface.convert("RGB").resize((112,112), Image.BILINEAR)
                        bgr  = np.array(img)[:,:,::-1].astype(np.float32)
                        bgr  = (bgr-127.5)/127.5
                        inp  = np.transpose(bgr,(2,0,1))[np.newaxis]
                        feat = arcface.run(None,{arcface_input:inp})[0][0].astype(np.float32)
                        norm = np.linalg.norm(feat)
                        vec  = feat/norm if norm > 0 else feat

                        info = verify(vec, self._db_cache)

                        snapshot_url = None
                        if not info.get("matched"):
                            try:
                                fname = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
                                fpath = os.path.join(config.PATHS["SNAPSHOTS"], fname)
                                fface.save(fpath, quality=85)
                                snapshot_url = f"/snapshots/{fname}"
                            except:
                                pass

                        state.add_event(info, snapshot_url)

                        tracked.append({
                            "box" : (hx1+fx1, hy1+fy1, hx1+fx2, hy1+fy2),
                            "info": info,
                        })
                    except:
                        continue

                state.face_count = len(tracked)

            idx += 1

            # Draw on every frame
            out = frame.copy()
            for face in tracked:
                ax1,ay1,ax2,ay2 = face["box"]
                info = face["info"]
                if info.get("matched"):
                    col = (20,140,255) if info.get("access_level") == "restricted" else (45,200,100)
                else:
                    col = (50,50,220)
                cv2.rectangle(out,(ax1,ay1),(ax2,ay2),col,2)
                label = info.get("identity","Unknown")
                (tw,th),_ = cv2.getTextSize(label,cv2.FONT_HERSHEY_DUPLEX,0.65,1)
                cv2.rectangle(out,(ax1,ay1-th-14),(ax1+tw+12,ay1),col,cv2.FILLED)
                cv2.putText(out,label,(ax1+6,ay1-6),
                    cv2.FONT_HERSHEY_DUPLEX,0.65,(255,255,255),1,cv2.LINE_AA)
                if info.get("matched"):
                    role = info.get('role','').strip()
                    dept = info.get('department','').strip()
                    sub  = f"{role} | {dept}" if role and dept else role or dept
                    cv2.putText(out,sub,(ax1+4,ay2+20),
                        cv2.FONT_HERSHEY_DUPLEX,0.5,col,1,cv2.LINE_AA)

            _, jpeg = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY,80])
            state.set_frame(jpeg.tobytes())

        cap.release()
        self._running = False
        print("[ML] Worker stopped")