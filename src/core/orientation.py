import cv2
import numpy as np


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

    while normalized >= 90:
        normalized -= 180
    while normalized < -90:
        normalized += 180

    return round(normalized, 2)


def calculate_box_angle(frame, x1, y1, x2, y2):
    """
    Extract the carton rotation angle from the cropped ROI.
    Multiple threshold variants are tried so the math stays stable across lighting changes.
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
