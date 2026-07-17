import cv2
import numpy as np
import unittest

from src.core.orientation import calculate_box_angle


def make_test_frame(angle):
    frame = np.zeros((240, 240, 3), dtype=np.uint8)
    rect = ((120, 120), (120, 60), angle)
    box = cv2.boxPoints(rect).astype(int)
    cv2.drawContours(frame, [box], 0, (255, 255, 255), -1)
    return frame


class OrientationTests(unittest.TestCase):
    def test_rotated_carton_angles_are_recovered(self):
        for expected in (15, 30, 60, -20, -45):
            with self.subTest(expected=expected):
                frame = make_test_frame(expected)
                angle = calculate_box_angle(frame, 20, 20, 220, 220)
                self.assertAlmostEqual(angle, expected, delta=2.5)

    def test_motion_blurred_carton_angle_is_recovered(self):
        blur_kernel = np.zeros((1, 19), dtype=np.float32)
        blur_kernel[0, :] = 1.0 / blur_kernel.shape[1]

        for expected in (15, 30, -20, -45):
            with self.subTest(expected=expected):
                frame = make_test_frame(expected)
                blurred = cv2.filter2D(frame, -1, blur_kernel)
                angle = calculate_box_angle(blurred, 20, 20, 220, 220)
                self.assertAlmostEqual(angle, expected, delta=3.0)

    def test_empty_roi_returns_zero(self):
        frame = np.zeros((120, 120, 3), dtype=np.uint8)
        self.assertEqual(calculate_box_angle(frame, 150, 150, 200, 200), 0.0)


if __name__ == "__main__":
    unittest.main()
