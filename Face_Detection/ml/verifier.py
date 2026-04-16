import numpy as np
import config

def verify(query_vec, db):
    """Vectorized cosine — fast batch match against all embeddings."""
    if not db:
        return {"identity":"Unknown","matched":False,"cosine_score":0,"euclidean_dist":9999}

    best_cos  = -1.0
    best_euc  = 9999.0
    best_meta = None

    for pid, data in db.items():
        mat        = data["emb_matrix"]       # pre-normalized (N,512)
        cos_scores = mat @ query_vec           # batch cosine
        idx        = int(np.argmax(cos_scores))
        cos        = float(cos_scores[idx])
        euc        = float(np.linalg.norm(query_vec - data["embeddings"][idx]))
        if cos > best_cos:
            best_cos  = cos
            best_euc  = euc
            best_meta = data["meta"]

    if best_cos >= config.COSINE_THRESHOLD and best_euc <= config.EUCLIDEAN_THRESHOLD:
        return {
            "identity"      : best_meta["name"],
            "person_id"     : best_meta["person_id"],
            "role"          : best_meta["role"],
            "department"    : best_meta["department"],
            "access_level"  : best_meta["access_level"],
            "cosine_score"  : round(best_cos, 4),
            "euclidean_dist": round(best_euc, 4),
            "matched"       : True,
        }
    return {
        "identity"      : "Unknown",
        "matched"       : False,
        "cosine_score"  : round(best_cos, 4),
        "euclidean_dist": round(best_euc, 4),
    }