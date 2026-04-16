import os
import sqlite3
import numpy as np
from datetime import datetime
from PIL import Image, ImageOps
import config

def get_conn():
    conn = sqlite3.connect(config.PATHS["DB"], check_same_thread=False)
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

def load_embeddings():
    """Load all embeddings into memory with pre-normalized matrix for fast cosine."""
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT p.id, p.person_id, p.name, p.role,
                   p.department, p.access_level, e.embedding
            FROM persons p JOIN embeddings e ON e.person_id = p.id
        """)
        db = {}
        for pid, eid, name, role, dept, access, blob in cur.fetchall():
            vec = np.frombuffer(blob, dtype=np.float32).copy()
            if pid not in db:
                db[pid] = {
                    "meta": {
                        "person_id"   : eid,
                        "name"        : name,
                        "role"        : role,
                        "department"  : dept,
                        "access_level": access,
                    },
                    "embeddings": [],
                }
            db[pid]["embeddings"].append(vec)

        for pid in db:
            mat   = np.stack(db[pid]["embeddings"])
            norms = np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
            db[pid]["emb_matrix"] = mat / norms

        print(f"[DB] Loaded {len(db)} profiles")
        return db
    finally:
        conn.close()

def list_persons():
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            SELECT p.person_id, p.name, p.role, p.department,
                   p.access_level, p.date_registered,
                   COUNT(e.id) as emb_count
            FROM persons p
            LEFT JOIN embeddings e ON e.person_id = p.id
            GROUP BY p.id
            ORDER BY p.date_registered DESC
        """)
        cols = ["person_id","name","role","department",
                "access_level","date_registered","embedding_count"]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

def delete_person(person_id: str):
    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("SELECT id FROM persons WHERE person_id=?", (person_id,))
        row = cur.fetchone()
        if not row:
            return False
        pid = row[0]
        cur.execute("DELETE FROM embeddings WHERE person_id=?", (pid,))
        cur.execute("DELETE FROM persons WHERE id=?", (pid,))
        conn.commit()
        return True
    finally:
        conn.close()

def register_person(person_id, name, role, department, access_level, pil_images):
    """
    Takes list of PIL Images, extracts embeddings, saves to DB.
    Returns dict with result info.
    """
    from ml.loader import get_models

    models  = get_models()
    mtcnn   = models["mtcnn"]
    arcface = models["arcface"]

    face_vecs = []
    failed    = 0

    for i, pil in enumerate(pil_images):
        try:
            pil  = ImageOps.exif_transpose(pil.convert("RGB"))
            # Crop face
            boxes, probs = mtcnn.detect(pil)
            if boxes is not None:
                idx      = int(np.argmax(probs))
                x1,y1,x2,y2 = [int(v) for v in boxes[idx]]
                x1=max(0,x1); y1=max(0,y1)
                x2=min(pil.width,x2); y2=min(pil.height,y2)
                face = pil.crop((x1,y1,x2,y2)).resize((160,160), Image.BILINEAR)
            else:
                face = pil.resize((160,160), Image.BILINEAR)

            # Embedding
            img  = face.convert("RGB").resize((112,112), Image.BILINEAR)
            bgr  = np.array(img)[:,:,::-1].astype(np.float32)
            bgr  = (bgr - 127.5) / 127.5
            inp  = np.transpose(bgr,(2,0,1))[np.newaxis]
            iname = arcface.get_inputs()[0].name
            feat  = arcface.run(None, {iname: inp})[0][0].astype(np.float32)
            norm  = np.linalg.norm(feat)
            vec   = feat / norm if norm > 0 else feat
            face_vecs.append(vec)
        except Exception as e:
            print(f"[REG] Image {i} failed: {e}")
            failed += 1

    if not face_vecs:
        return {"success": False, "error": "No valid embeddings from images"}

    conn = get_conn()
    cur  = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO persons
                (person_id, name, role, department, access_level, date_registered)
            VALUES (?,?,?,?,?,?)
        """, (person_id, name, role, department,
              access_level, datetime.now().isoformat()))
        conn.commit()
        pid = cur.lastrowid
    except sqlite3.IntegrityError:
        cur.execute("SELECT id FROM persons WHERE person_id=?", (person_id,))
        pid = cur.fetchone()[0]

    for vec in face_vecs:
        conn.execute("""
            INSERT INTO embeddings (person_id, embedding, source_image, created_at)
            VALUES (?,?,?,?)
        """, (pid, vec.tobytes(), "upload", datetime.now().isoformat()))

    # Aggregate embedding
    agg  = np.stack(face_vecs).mean(axis=0)
    norm = np.linalg.norm(agg)
    agg  = agg / norm if norm > 0 else agg
    conn.execute("""
        INSERT INTO embeddings (person_id, embedding, source_image, created_at)
        VALUES (?,?,?,?)
    """, (pid, agg.tobytes(), "AGGREGATE", datetime.now().isoformat()))

    conn.commit()
    conn.close()

    return {
        "success"   : True,
        "name"      : name,
        "person_id" : person_id,
        "embeddings": len(face_vecs),
        "failed"    : failed,
    }


def update_person_info(person_id: str, updates: dict) -> bool:
    """Update editable fields on a person row by person_id (text ID)."""
    if not updates:
        return False
    cols   = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [person_id]
    try:
        conn = get_conn()
        conn.execute(f"UPDATE persons SET {cols} WHERE person_id = ?", values)
        conn.commit()
        return True
    except Exception as e:
        print(f"[DB] update_person_info error: {e}")
        return False