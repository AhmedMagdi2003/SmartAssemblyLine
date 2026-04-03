from ultralytics import YOLO

# 1. Load YOUR trained model 
model = YOLO('../models/best_v6.pt')

print("Starting additional training...")

# 2. Train for more epochs
results = model.train(
    data='../data/conv_data/data.yaml',
    epochs=30,
    imgsz=(640,480),
    batch=16,
    cache=True,
    workers=2,
    project='../runs/v_17_conv',
    name='box_tracker_v17',
    device=0
)