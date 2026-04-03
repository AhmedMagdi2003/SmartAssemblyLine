import cv2

def calculate_box_angle(frame, x1, y1, x2, y2):
    """
    Extracts the rotational angle of a bounding box region using Otsu's Binarization.
    """
    h, w = frame.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    
    roi = frame[y1:y2, x1:x2]
    if roi.size == 0: 
        return 0.0

    # Convert to grayscale and apply Otsu's thresholding
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Find contours inside the bounding box
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        c = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(c)
        angle = rect[2]
        
        # Normalize angle to a standard -45 to 45 degree range
        if angle > 45:
            angle -= 90
        return round(angle, 2)
        
    return 0.0