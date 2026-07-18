import cv2
import numpy as np
import time
import yaml
from pathlib import Path

from .orientation import calculate_box_angle
from src.comms.streamer import ProductionStreamer
from src.utils.analytics import ProductionAnalytics


class AssemblyLineTracker:
    def __init__(
        self,
        config_path="config/tracker_params.yaml",
        model=None,
        analytics=None,
        streamer=None,
        time_fn=None,
    ):
        """Initialize the tracker using parameters from a YAML config."""
        self.config_path = self._resolve_path(config_path)
        with open(self.config_path, "r", encoding="utf-8") as file:
            self.config = yaml.safe_load(file)

        self.model = model or self._build_model()
        self.conf = self.config["model"]["confidence"]
        self.tracker = str(self._resolve_path(self.config["model"]["tracker_config"]))

        self.belt_polygon = np.array(self.config["roi"]["polygon"], np.int32)
        self.finish_line_y = self.config["roi"]["finish_line_y"]
        self.min_area = self.config["filters"]["min_box_area"]
        self.min_lifespan = self.config["filters"]["min_lifespan_sec"]

        self.box_entry_times = {}
        self.box_exit_times = {}
        self.total_boxes_counted = 0

        self.analytics = analytics or ProductionAnalytics(self.config["shifts"])
        self.streamer = streamer or ProductionStreamer()
        self.time_fn = time_fn or time.monotonic
        if hasattr(self.analytics, "sync_with_time"):
            self.analytics.sync_with_time()
            self.total_boxes_counted = getattr(
                self.analytics,
                "shift_box_count",
                self.total_boxes_counted,
            )

    def _resolve_path(self, candidate):
        candidate_path = Path(candidate)
        if candidate_path.is_absolute() and candidate_path.exists():
            return candidate_path

        search_roots = [
            Path.cwd(),
            Path(__file__).resolve().parents[2],
            Path(__file__).resolve().parents[2] / "config",
        ]
        config_path = getattr(self, "config_path", None)
        if config_path is not None:
            search_roots.insert(1, config_path.parent)

        for root in search_roots:
            resolved = (root / candidate_path).resolve()
            if resolved.exists():
                return resolved

        return candidate_path

    def _build_model(self):
        from ultralytics import YOLO

        weights_path = str(self._resolve_path(self.config["model"]["weights_path"]))
        return YOLO(weights_path)

    def process_frame(self, frame, draw_annotations=True, frame_timestamp=None):
        """Process a single frame and return annotations plus active box data."""
        if hasattr(self.analytics, "sync_with_time"):
            self.analytics.sync_with_time()
            self.total_boxes_counted = getattr(
                self.analytics,
                "shift_box_count",
                self.total_boxes_counted,
            )

        results = self.model.track(
            frame,
            persist=True,
            conf=self.conf,
            tracker=self.tracker,
            verbose=False,
        )

        active_boxes_data = []
        if draw_annotations:
            cv2.polylines(frame, [self.belt_polygon], True, (255, 0, 255), 2)
            cv2.line(
                frame,
                (0, self.finish_line_y),
                (frame.shape[1], self.finish_line_y),
                (0, 255, 255),
                2,
            )

        if not results or results[0].boxes.id is None:
            return frame, active_boxes_data

        boxes = results[0].boxes.xyxy.int().cpu().tolist()
        track_ids = results[0].boxes.id.int().cpu().tolist()

        for box, track_id in zip(boxes, track_ids):
            x1, y1, x2, y2 = box
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            if cv2.pointPolygonTest(self.belt_polygon, (cx, cy), False) < 0:
                continue

            if (x2 - x1) * (y2 - y1) < self.min_area:
                continue

            if track_id not in self.box_entry_times:
                self.box_entry_times[track_id] = (
                    self.time_fn() if frame_timestamp is None else frame_timestamp
                )

            current_time = self.time_fn() if frame_timestamp is None else frame_timestamp
            lifespan = current_time - self.box_entry_times[track_id]
            try:
                angle = calculate_box_angle(frame, x1, y1, x2, y2)
            except Exception as exc:
                angle = 0.0
                print(
                    f"[WARNING] Orientation failed for track {track_id}; "
                    f"using 0.0 deg. Error: {exc}",
                    flush=True,
                )

            if cy > self.finish_line_y and track_id not in self.box_exit_times:
                if lifespan > self.min_lifespan:
                    self.box_exit_times[track_id] = lifespan
                    self.total_boxes_counted += 1
                    print(f"[METRIC] Box {track_id} processed in {lifespan:.2f}s")
                    payload = self.analytics.generate_dashboard_payload(
                        yolo_id=track_id,
                        lifespan_sec=lifespan,
                        angle=angle,
                    )
                    self.streamer.broadcast(payload)
                    print(f"[STREAM] Dispatched: {payload['uuid']}")

            box_data = {
                "id": track_id,
                "center": (cx, cy),
                "angle": angle,
                "lifespan": lifespan,
                "counted": track_id in self.box_exit_times,
            }
            active_boxes_data.append(box_data)

            if draw_annotations:
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)
                label = f"ID:{track_id} | {angle} deg"
                cv2.putText(
                    frame,
                    label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )

        if draw_annotations:
            cv2.putText(
                frame,
                f"Total Count: {self.total_boxes_counted}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (255, 255, 255),
                3,
            )

        return frame, active_boxes_data
