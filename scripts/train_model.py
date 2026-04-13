from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ultralytics import YOLO

# 1. Load YOUR trained model 
model = YOLO(str(PROJECT_ROOT / 'models' / 'best_v6.pt'))

print("Starting additional training...")

# 2. Train for more epochs
results = model.train(
    data=str(PROJECT_ROOT / 'data' / 'conv_data' / 'data.yaml'),
    epochs=30,
    imgsz=(640,480),
    batch=16,
    cache=True,
    workers=2,
    project=str(PROJECT_ROOT / 'runs' / 'v_17_conv'),
    name='box_tracker_v17',
    device=0
)
