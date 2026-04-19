# Smart Assembly Camera Bridge

This folder gives you a future-ready ROS2 bridge for the Raspberry Pi 4 camera side without changing the current PC pipeline.

You asked for the fast and efficient options. Here is the practical order:

## Recommended Options

### Option A. RTSP / H.264 stream from Raspberry Pi to PC

Best choice when your PC will run YOLO/tracking and the Pi only provides camera + ROS.

Why:

- efficient bandwidth usage
- easy to test with VLC
- easy for OpenCV on the PC later
- keeps heavy inference off the Pi

Use this as the final production path for Option 1 local-PC mode.

### Option B. ROS2 compressed image topic

Best choice when you want ROS-native testing first.

Why:

- integrates well with ROS2
- fast enough for validation and robotics workflows
- good for proving Pi-to-PC communication before switching to RTSP

This package includes code for this option now.

### Option C. UDP / GStreamer

Best for very low latency, but more complex to tune.

Why:

- lower latency
- more difficult setup and debugging
- use later only if you outgrow RTSP

## What This Package Contains

- `camera_publisher.py`
  Raspberry Pi side ROS2 node that captures frames and publishes:
  - `/smart_assembly/camera/image_raw`
  - `/smart_assembly/camera/image_compressed`
- `stream_receiver.py`
  PC side ROS2 node that subscribes and previews the stream
- `pi_camera_bridge.launch.py`
  Launch file for the Raspberry Pi
- `pc_stream_receiver.launch.py`
  Launch file for the PC

## ROS2 Flow

### Raspberry Pi

Camera -> OpenCV capture -> ROS2 topic publish

### PC

ROS2 topic subscribe -> preview / validation

This does not change `scripts/run_pipeline.py` yet.
It is only the bridge layer for when the Raspberry Pi arrives.

## Suggested Real Deployment Path

1. First test ROS2 connectivity with this package
2. Confirm PC can receive frames from the Pi
3. Then move to RTSP for the real pipeline input
4. Keep ROS2 on the Pi for robotics integration
5. Keep heavy inference on the PC

## Folder Layout

```text
ros2/smart_assembly_camera_bridge/
├── launch/
│   ├── pc_stream_receiver.launch.py
│   └── pi_camera_bridge.launch.py
├── resource/
│   └── smart_assembly_camera_bridge
├── smart_assembly_camera_bridge/
│   ├── __init__.py
│   ├── camera_publisher.py
│   └── stream_receiver.py
├── package.xml
├── setup.cfg
└── setup.py
```

## Raspberry Pi Setup Steps

### 1. Install ROS2 and camera dependencies

You will need ROS2 plus:

- `python3-opencv`
- `python3-numpy`
- `cv_bridge`
- `sensor_msgs`
- `rclpy`

### 2. Copy this package into your ROS2 workspace

Example:

```bash
mkdir -p ~/ros2_ws/src
cp -r smart_assembly_camera_bridge ~/ros2_ws/src/
cd ~/ros2_ws
colcon build
source install/setup.bash
```

### 3. Run the Raspberry Pi publisher

```bash
ros2 launch smart_assembly_camera_bridge pi_camera_bridge.launch.py
```

Useful overrides:

```bash
ros2 launch smart_assembly_camera_bridge pi_camera_bridge.launch.py camera_device:=0 width:=1280 height:=720 fps:=15 publish_raw:=false publish_compressed:=true
```

## PC Setup Steps

### 1. Put the PC on the same network as the Raspberry Pi

Recommended:

- same router / switch
- stable IPs
- same ROS domain

### 2. Match the ROS domain on both devices

Example on both Pi and PC:

```bash
export ROS_DOMAIN_ID=30
```

### 3. Confirm the PC can see the Pi

From the PC:

```bash
ping <raspberry-pi-ip>
```

### 4. Run the receiver on the PC

```bash
ros2 launch smart_assembly_camera_bridge pc_stream_receiver.launch.py
```

If the preview opens and frames are moving, the bridge is working.

## Important Notes

- This package is for future Raspberry Pi integration only.
- Your current pipeline still uses the local test video file.
- No pipeline code was changed by this package.
- When the Raspberry Pi arrives, use this package first to validate network + ROS2 communication.
- After that, move to RTSP for the real PC pipeline input.

## Fastest Practical Future Workflow

When the Raspberry Pi arrives:

1. run this ROS2 bridge and validate PC reception
2. set up RTSP stream on the Pi
3. test RTSP with VLC on the PC
4. only then switch the PC pipeline input from local test video to the Pi stream
