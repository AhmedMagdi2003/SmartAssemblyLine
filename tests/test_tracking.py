from pathlib import Path
import unittest
import uuid
from unittest.mock import patch

import numpy as np
import yaml

from src.core.tracking import AssemblyLineTracker

TEMP_ROOT = Path(__file__).resolve().parents[1] / "data" / "test_tmp"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


class FakeTensor:
    def __init__(self, values):
        self.values = values

    def int(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.values


class FakeBoxes:
    def __init__(self, boxes, track_ids):
        self.xyxy = FakeTensor(boxes)
        self.id = FakeTensor(track_ids) if track_ids is not None else None


class FakeResult:
    def __init__(self, boxes, track_ids):
        self.boxes = FakeBoxes(boxes, track_ids)


class SequenceModel:
    def __init__(self, outputs):
        self._outputs = iter(outputs)

    def track(self, frame, persist, conf, tracker, verbose):
        return next(self._outputs)


class FakeAnalytics:
    def __init__(self):
        self.calls = []

    def generate_dashboard_payload(self, yolo_id, lifespan_sec, angle):
        payload = {
            "uuid": f"BOX-{yolo_id:04d}",
            "yolo_session_id": yolo_id,
            "timestamp_iso": "2026-04-04T08:15:00",
            "shift": "Morning_Shift",
            "shift_count": len(self.calls) + 1,
            "transit_time_sec": round(lifespan_sec, 2),
            "orientation_deg": angle,
            "status": "COMPLETED",
        }
        self.calls.append(payload)
        return payload


class FakeStreamer:
    def __init__(self):
        self.broadcasts = []

    def broadcast(self, payload):
        self.broadcasts.append(payload)


class AssemblyLineTrackerTests(unittest.TestCase):
    def test_tracker_filters_noise_and_counts_each_box_once(self):
        config = {
            "model": {
                "weights_path": "models/best.pt",
                "tracker_config": "botsort.yaml",
                "confidence": 0.5,
            },
            "roi": {
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "finish_line_y": 50,
            },
            "filters": {
                "min_box_area": 100,
                "min_lifespan_sec": 1.0,
            },
            "shifts": [
                {"name": "Morning_Shift", "start_hour": 6, "end_hour": 14},
            ],
        }

        model = SequenceModel(
            [
                [FakeResult([[10, 10, 40, 40], [110, 10, 130, 30], [10, 10, 15, 15]], [7, 8, 9])],
                [FakeResult([[10, 60, 40, 90]], [7])],
                [FakeResult([[10, 70, 40, 100]], [7])],
            ]
        )
        analytics = FakeAnalytics()
        streamer = FakeStreamer()
        frame = np.zeros((120, 140, 3), dtype=np.uint8)

        config_path = TEMP_ROOT / f"tracker_case_{uuid.uuid4().hex}.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        tracker = AssemblyLineTracker(
            config_path=str(config_path),
            model=model,
            analytics=analytics,
            streamer=streamer,
        )

        self.assertTrue(str(tracker.tracker).endswith(str(Path("config") / "botsort.yaml")))

        with patch("src.core.tracking.calculate_box_angle", return_value=12.5):
            _, active_boxes = tracker.process_frame(frame.copy(), draw_annotations=False, frame_timestamp=0.0)
            self.assertEqual(len(active_boxes), 1)
            self.assertFalse(active_boxes[0]["counted"])

            _, active_boxes = tracker.process_frame(frame.copy(), draw_annotations=False, frame_timestamp=1.5)
            self.assertEqual(len(streamer.broadcasts), 1)
            self.assertEqual(tracker.total_boxes_counted, 1)
            self.assertTrue(active_boxes[0]["counted"])
            self.assertEqual(streamer.broadcasts[0]["transit_time_sec"], 1.5)

            tracker.process_frame(frame.copy(), draw_annotations=False, frame_timestamp=2.5)
            self.assertEqual(len(streamer.broadcasts), 1)

    def test_static_overlays_remain_visible_without_active_tracks(self):
        config = {
            "model": {
                "weights_path": "models/best.pt",
                "tracker_config": "botsort.yaml",
                "confidence": 0.5,
            },
            "roi": {
                "polygon": [[10, 10], [110, 10], [110, 80], [10, 80]],
                "finish_line_y": 60,
            },
            "filters": {
                "min_box_area": 100,
                "min_lifespan_sec": 1.0,
            },
            "shifts": [
                {"name": "Morning_Shift", "start_hour": 6, "end_hour": 14},
            ],
        }

        model = SequenceModel([[FakeResult([], None)]])
        frame = np.zeros((120, 140, 3), dtype=np.uint8)

        config_path = TEMP_ROOT / f"tracker_overlay_case_{uuid.uuid4().hex}.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        tracker = AssemblyLineTracker(
            config_path=str(config_path),
            model=model,
            analytics=FakeAnalytics(),
            streamer=FakeStreamer(),
        )

        annotated_frame, active_boxes = tracker.process_frame(
            frame.copy(),
            draw_annotations=True,
            frame_timestamp=0.0,
        )

        self.assertEqual(active_boxes, [])
        self.assertGreater(int(np.count_nonzero(annotated_frame)), 0)

    def test_orientation_failure_does_not_stop_counting(self):
        config = {
            "model": {
                "weights_path": "models/best.pt",
                "tracker_config": "botsort.yaml",
                "confidence": 0.5,
            },
            "roi": {
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "finish_line_y": 50,
            },
            "filters": {
                "min_box_area": 100,
                "min_lifespan_sec": 0.0,
            },
            "shifts": [
                {"name": "Morning_Shift", "start_hour": 6, "end_hour": 14},
            ],
        }

        model = SequenceModel(
            [
                [FakeResult([[10, 10, 40, 40]], [7])],
                [FakeResult([[10, 60, 40, 90]], [7])],
            ]
        )
        analytics = FakeAnalytics()
        streamer = FakeStreamer()
        frame = np.zeros((120, 140, 3), dtype=np.uint8)

        config_path = TEMP_ROOT / f"tracker_orientation_error_{uuid.uuid4().hex}.yaml"
        config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

        tracker = AssemblyLineTracker(
            config_path=str(config_path),
            model=model,
            analytics=analytics,
            streamer=streamer,
        )

        with patch("src.core.tracking.calculate_box_angle", side_effect=RuntimeError("bad crop")):
            tracker.process_frame(
                frame.copy(),
                draw_annotations=False,
                frame_timestamp=0.0,
            )
            _, active_boxes = tracker.process_frame(
                frame.copy(),
                draw_annotations=False,
                frame_timestamp=1.0,
            )

        self.assertEqual(len(streamer.broadcasts), 1)
        self.assertEqual(streamer.broadcasts[0]["orientation_deg"], 0.0)
        self.assertEqual(active_boxes[0]["angle"], 0.0)

if __name__ == "__main__":
    unittest.main()
