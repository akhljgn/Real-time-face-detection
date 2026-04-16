import os, sqlite3, json, warnings, io
from datetime import datetime


import numpy as np
import torch
import onnxruntime as ort
from PIL import Image, ImageOps
from facenet_pytorch import MTCNN
from facenet_pytorch.models.mtcnn import PNet, RNet, ONet

warnings.filterwarnings("ignore")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"[INFO] Device : {DEVICE.upper()}")

DB_PATH   = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\database\face_database.db"
JSON_PATH = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\database\face_database.json"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)

PNET_W = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\faceCrop\pnet.pt"
RNET_W = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\faceCrop\rnet.pt"
ONET_W = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\faceCrop\onet.pt"

print("[INFO] Loading MTCNN ...")
pnet = PNet().to(DEVICE)
rnet = RNet().to(DEVICE)
onet = ONet().to(DEVICE)

pnet.load_state_dict(torch.load(PNET_W, map_location=DEVICE))
rnet.load_state_dict(torch.load(RNET_W, map_location=DEVICE))
onet.load_state_dict(torch.load(ONET_W, map_location=DEVICE))
pnet.eval(); rnet.eval(); onet.eval()

mtcnn = MTCNN(keep_all=True, device=DEVICE,
              min_face_size=20, thresholds=[0.6, 0.7, 0.8],
              post_process=False)
mtcnn.pnet = pnet
mtcnn.rnet = rnet
mtcnn.onet = onet
print("[INFO] MTCNN ready ✓")

ARCFACE_PATH = r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\InsightFace\w600k_r50.onnx"

if not os.path.exists(ARCFACE_PATH):
    print("[INFO] Downloading ArcFace ONNX model ...")
    import urllib.request
    urllib.request.urlretrieve(
        "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip",
        r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\InsightFace\buffalo_l.zip"
    )
    import zipfile
    with zipfile.ZipFile(r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\InsightFace\buffalo_l.zip", "r") as z:
        z.extractall(r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\InsightFace\buffalo_l")
    # find the recognition onnx
    for root, dirs, fnames in os.walk(r"C:\Users\rakhi\Downloads\Main Project\code\models\runs\InsightFace\buffalo_l"):
        for f in fnames:
            if f.endswith(".onnx") and "rec" in f.lower() or "r50" in f.lower() or "w600" in f.lower():
                import shutil
                shutil.copy(os.path.join(root, f), ARCFACE_PATH)
                print(f"[INFO] Found model: {f}")
                break

# providers = ["CUDAExecutionProvider"] if DEVICE == "cuda" else ["CPUExecutionProvider"]
providers = ["CPUExecutionProvider"]
arcface_session = ort.InferenceSession(ARCFACE_PATH, providers=providers)
arcface_input   = arcface_session.get_inputs()[0].name
print("[INFO] ArcFace ready ✓")

def get_embedding(pil_img):
    img = pil_img.convert("RGB").resize((112, 112), Image.BILINEAR)
    bgr = np.array(img)[:, :, ::-1].astype(np.float32)
    # normalize to [-1, 1]
    bgr = (bgr - 127.5) / 127.5
    inp = np.transpose(bgr, (2, 0, 1))[np.newaxis]  # (1, 3, 112, 112)
    try:
        feat = arcface_session.run(None, {arcface_input: inp})[0][0]
        feat = feat.astype(np.float32)
        norm = np.linalg.norm(feat)
        return feat / norm if norm > 0 else feat
    except Exception as e:
        print(f"  [WARN] Embedding failed: {e}")
        return None

def crop_face(pil_img):
    boxes, probs = mtcnn.detect(pil_img)
    if boxes is not None:
        idx          = int(np.argmax(probs))
        x1, y1, x2, y2 = [int(v) for v in boxes[idx]]
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(pil_img.width, x2)
        y2 = min(pil_img.height, y2)
        return pil_img.crop((x1, y1, x2, y2)).resize((160, 160), Image.BILINEAR)
    else:
        return pil_img.resize((160, 160), Image.BILINEAR)

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS persons (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id       TEXT    UNIQUE NOT NULL,
            name            TEXT    NOT NULL,
            role            TEXT,
            department      TEXT,
            access_level    TEXT,
            date_registered TEXT
        );
        CREATE TABLE IF NOT EXISTS embeddings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id    INTEGER NOT NULL REFERENCES persons(id),
            embedding    BLOB    NOT NULL,
            source_image TEXT,
            created_at   TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_person_id ON embeddings(person_id);
    """)
    conn.commit()
    return conn

def insert_person(conn, person_id, name, role, department, access_level):
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO persons
                (person_id, name, role, department, access_level, date_registered)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (person_id, name, role, department,
              access_level, datetime.now().isoformat()))
        conn.commit()
        pid = cur.lastrowid
        print(f"[DB] Inserted '{name}'  (row={pid})")
        return pid
    except sqlite3.IntegrityError:
        cur.execute("SELECT id FROM persons WHERE person_id=?", (person_id,))
        pid = cur.fetchone()[0]
        print(f"[DB] '{name}' already exists — appending embeddings")
        return pid

def insert_embedding(conn, person_id, vec, source=""):
    conn.execute("""
        INSERT INTO embeddings (person_id, embedding, source_image, created_at)
        VALUES (?, ?, ?, ?)
    """, (person_id, vec.astype(np.float32).tobytes(),
          source, datetime.now().isoformat()))
    conn.commit()

def export_json(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.person_id, p.name, p.role,
               p.department, p.access_level, e.embedding
        FROM persons p JOIN embeddings e ON e.person_id = p.id
    """)
    out = {}
    for pid, eid, name, role, dept, access, blob in cur.fetchall():
        vec = np.frombuffer(blob, dtype=np.float32).tolist()
        if str(pid) not in out:
            out[str(pid)] = {
                "meta": {"person_id": eid, "name": name, "role": role,
                         "department": dept, "access_level": access},
                "embeddings": []
            }
        out[str(pid)]["embeddings"].append(vec)
    with open(JSON_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"[DB] JSON saved → {JSON_PATH}")

def register_person_colab():
    print("\n" + "="*55)
    print("  PERSON REGISTRATION")
    print("="*55)

    # ── Step 1: person details ────────────────────────────
    PERSON_ID    = input("Person ID       : ").strip()
    NAME         = input("Full Name       : ").strip()
    ROLE         = input("Role            : ").strip()
    DEPARTMENT   = input("Department      : ").strip()
    ACCESS_LEVEL = input("Access Level (standard/restricted) [standard]: ").strip() or "standard"

    if not PERSON_ID or not NAME:
        print("[REG] Person ID and Name are required.")
        return

    print(f"\n[REG] Registering: {NAME} ({PERSON_ID})")

    # ── Step 2: Ensure database exists ───────────
    if os.path.exists(DB_PATH):
        print("[DB] Existing database loaded ✓")
    else:
        print("[DB] Starting fresh database")

    # ── Step 3: Local images folder ──────────────────
    img_dir = input(f"\nEnter the path to a folder containing 10+ reference images for {NAME}: ").strip()
    
    if not os.path.isdir(img_dir):
        print(f"[REG] Invalid directory: {img_dir}. Aborting.")
        return

    image_files = [os.path.join(img_dir, f) for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not image_files:
        print("[REG] No valid images found in the directory.")
        return

    print(f"[REG] {len(image_files)} image(s) found in {img_dir}")

    # ── Step 4: process → face crop → embedding ──────────
    face_vecs = []
    for fpath in image_files:
        fname = os.path.basename(fpath)
        try:
            pil  = ImageOps.exif_transpose(Image.open(fpath).convert("RGB"))
            face = crop_face(pil)
            vec  = get_embedding(face)
            if vec is not None:
                face_vecs.append((vec, fname))
                print(f"  ✅ {fname}")
            else:
                print(f"  ⚠️  {fname} — embedding failed")
        except Exception as e:
            print(f"  ❌ {fname} — {e}")

    if not face_vecs:
        print("[REG] No valid embeddings. Aborting.")
        return

    # ── Step 5: save to DB ────────────────────────────────
    conn = get_db()
    pid  = insert_person(conn, PERSON_ID, NAME, ROLE, DEPARTMENT, ACCESS_LEVEL)

    for vec, path in face_vecs:
        insert_embedding(conn, pid, vec, path)

    # aggregate embedding
    all_vecs = np.stack([v for v, _ in face_vecs])
    agg      = all_vecs.mean(axis=0)
    norm     = np.linalg.norm(agg)
    agg      = agg / norm if norm > 0 else agg
    insert_embedding(conn, pid, agg, "AGGREGATE")

    export_json(conn)
    conn.close()

    print(f"\n[REG] Done ✓")
    print(f"  Name        : {NAME}")
    print(f"  Person ID   : {PERSON_ID}")
    print(f"  Embeddings  : {len(face_vecs)} individual + 1 aggregate")
    print(f"  Files saved : {DB_PATH}, {JSON_PATH}")

    again = input("\nRegister another person? (y/n): ").strip().lower()
    if again == 'y':
        register_person_colab()

register_person_colab()