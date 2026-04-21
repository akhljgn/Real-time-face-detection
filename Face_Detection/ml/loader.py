import torch
import onnxruntime as ort
from ultralytics import YOLO
from facenet_pytorch import MTCNN
from facenet_pytorch.models.mtcnn import PNet, RNet, ONet
import config

_models = {}

def _arcface_providers():
    # Prefer GPU when ONNX Runtime CUDA is available.
    # Important: this is independent from PyTorch's CUDA availability.
    # (You can have torch CPU-only but still have onnxruntime-gpu working.)
    avail = set(ort.get_available_providers())
    preferred = []
    if "CUDAExecutionProvider" in avail:
        preferred.append("CUDAExecutionProvider")
    # Keep CPU as a safe fallback.
    if "CPUExecutionProvider" in avail:
        preferred.append("CPUExecutionProvider")
    if not preferred:
        preferred = ["CPUExecutionProvider"]
    return preferred

def get_models():
    global _models
    if _models:
        return _models

    print(f"[ML] Loading models on {config.DEVICE.upper()} ...")

    # YOLO
    yolo = YOLO(config.PATHS["YOLO"])
    print("[ML] YOLO ready ✓")

    # MTCNN with custom weights
    pnet = PNet().to(config.DEVICE)
    rnet = RNet().to(config.DEVICE)
    onet = ONet().to(config.DEVICE)
    pnet.load_state_dict(torch.load(config.PATHS["PNET"], map_location=config.DEVICE))
    rnet.load_state_dict(torch.load(config.PATHS["RNET"], map_location=config.DEVICE))
    onet.load_state_dict(torch.load(config.PATHS["ONET"], map_location=config.DEVICE))
    pnet.eval(); rnet.eval(); onet.eval()

    mtcnn = MTCNN(
        keep_all=True, device=config.DEVICE,
        min_face_size=config.MIN_FACE_SIZE,
        thresholds=config.MTCNN_THRESHOLDS,
        post_process=False
    )
    mtcnn.pnet = pnet
    mtcnn.rnet = rnet
    mtcnn.onet = onet
    print("[ML] MTCNN ready ✓")

    # ArcFace
    providers = _arcface_providers()
    arcface = ort.InferenceSession(
        config.PATHS["ARCFACE"],
        providers=providers
    )
    try:
        print(f"[ML] ArcFace providers: {arcface.get_providers()}")
    except Exception:
        print(f"[ML] ArcFace providers requested: {providers}")
    print("[ML] ArcFace ready ✓")

    _models = {
        "yolo"   : yolo,
        "mtcnn"  : mtcnn,
        "arcface": arcface,
        "device" : config.DEVICE,
    }
    return _models