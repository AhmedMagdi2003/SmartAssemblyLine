from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

BASE_MODEL_PATH = PROJECT_ROOT / "models" / "best.pt"
if not BASE_MODEL_PATH.exists():
    raise FileNotFoundError(f"Training base model not found: {BASE_MODEL_PATH}")

model = YOLO(str(BASE_MODEL_PATH))

print("Starting additional training...")

# 2. Train for more epochs
results = model.train(
    data=str(PROJECT_ROOT / "data" / "conv_data" / "data.yaml"),
    epochs=30,
    imgsz=(640, 480),
    batch=16,
    cache=True,
    workers=2,
    project=str(PROJECT_ROOT / "runs" / "v_17_conv"),
    name="box_tracker_v17",
    device=0,
)
