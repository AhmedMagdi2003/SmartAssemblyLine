import cv2
import numpy as np


def _normalize_axis_angle(angle):
    """Normalize an unoriented image-axis angle to [-90, 90)."""
    while angle >= 90:
        angle -= 180
    while angle < -90:
        angle += 180
    return round(float(angle), 2)


def _find_best_contour(mask):
    """Return the largest contour that looks like a carton, not the ROI background."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    roi_area = mask.shape[0] * mask.shape[1]
    plausible = [
        contour for contour in contours
        if 0.01 * roi_area <= cv2.contourArea(contour) <= 0.95 * roi_area
    ]
    candidates = plausible or contours
    return max(candidates, key=cv2.contourArea)


def _normalize_rect_angle(rect):
    """
    Convert OpenCV's minAreaRect angle into the long-axis rotation in [-90, 90).
    """
    (_, _), (width, height), angle = rect
    normalized = angle if width >= height else angle - 90

    return _normalize_axis_angle(normalized)


def _weighted_axial_mean(angles, weights):
    """
    Average line angles where +180 degrees is the same physical direction.
    Returns (angle, strength), where strength is 0..1 confidence in one dominant axis.
    """
    if not angles:
        return None, 0.0

    theta = np.deg2rad(np.asarray(angles, dtype=np.float64))
    line_weights = np.asarray(weights, dtype=np.float64)
    total_weight = float(line_weights.sum())
    if total_weight <= 0:
        return None, 0.0

    x = float(np.sum(line_weights * np.cos(2.0 * theta)))
    y = float(np.sum(line_weights * np.sin(2.0 * theta)))
    strength = float(np.hypot(x, y) / total_weight)
    angle = np.rad2deg(0.5 * np.arctan2(y, x))
    return _normalize_axis_angle(angle), strength


def _hough_line_angle(enhanced):
    """
    Estimate carton angle from dominant straight edges.
    This is better for a moving belt because it does not require one clean closed contour.
    """
    height, width = enhanced.shape[:2]
    if height < 12 or width < 12:
        return None

    blur = cv2.GaussianBlur(enhanced, (5, 5), 0)
    edges = cv2.Canny(blur, 60, 180, apertureSize=3)

    min_dimension = min(width, height)
    min_line_length = max(12, int(min_dimension * 0.25))
    max_line_gap = max(4, int(min_dimension * 0.08))
    threshold = max(12, int(min_dimension * 0.12))

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=threshold,
        minLineLength=min_line_length,
        maxLineGap=max_line_gap,
    )
    if lines is None:
        return None

    angles = []
    weights = []
    for line in lines[:, 0, :]:
        x1, y1, x2, y2 = [int(value) for value in line]
        dx = x2 - x1
        dy = y2 - y1
        length = float(np.hypot(dx, dy))
        if length < min_line_length:
            continue

        angle = np.degrees(np.arctan2(dy, dx))
        angles.append(_normalize_axis_angle(angle))
        # Squaring length makes the carton's long edges dominate short-edge noise.
        weights.append(length * length)

    angle, strength = _weighted_axial_mean(angles, weights)
    if angle is None or strength < 0.35:
        return None

    return angle


def calculate_box_angle(frame, x1, y1, x2, y2):
    """
    Extract the carton rotation angle from the cropped ROI.
    Prefer dominant Hough lines for moving cartons, then fall back to contour geometry.
    """
    h, w = frame.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))

    roi = frame[y1:y2, x1:x2]
    if roi.size == 0:
        return 0.0

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    hough_angle = _hough_line_angle(enhanced)
    if hough_angle is not None:
        return hough_angle

    edge_map = cv2.Canny(cv2.GaussianBlur(enhanced, (5, 5), 0), 50, 150)
    contour = _find_best_contour(edge_map)
    if contour is not None:
        rect = cv2.minAreaRect(contour)
        return _normalize_rect_angle(rect)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    _, otsu_binary = cv2.threshold(
        enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    _, otsu_inverse = cv2.threshold(
        enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    adaptive_binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    adaptive_inverse = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
    )

    contour = None
    best_area = 0.0
    for mask in (otsu_binary, otsu_inverse, adaptive_binary, adaptive_inverse):
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        candidate = _find_best_contour(cleaned)
        if candidate is None:
            continue

        area = cv2.contourArea(candidate)
        if area > best_area:
            contour = candidate
            best_area = area

    if contour is not None:
        rect = cv2.minAreaRect(contour)
        return _normalize_rect_angle(rect)

    return 0.0
