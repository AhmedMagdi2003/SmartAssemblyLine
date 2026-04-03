import datetime
import uuid

class ProductionAnalytics:
    def __init__(self, shift_config):
        self.shifts = shift_config
        self.current_shift = None
        self.shift_box_count = 0
        self.current_date = datetime.date.today()

    def _update_shift_status(self, now):
        """Determines the current shift and resets counters if a new shift starts."""
        hour = now.hour
        active_shift = "Unknown"

        for shift in self.shifts:
            start = shift['start_hour']
            end = shift['end_hour']
            
            # Handle shifts that wrap around midnight (e.g., 22:00 to 06:00)
            if start < end:
                if start <= hour < end:
                    active_shift = shift['name']
            else: 
                if hour >= start or hour < end:
                    active_shift = shift['name']

        # Reset logic: If shift changes or day changes
        if active_shift != self.current_shift or self.current_date != now.date():
            self.current_shift = active_shift
            self.current_date = now.date()
            self.shift_box_count = 0  # Reset counter for the new shift

    def generate_dashboard_payload(self, yolo_id, lifespan_sec, angle):
        """
        Generates a standardized dictionary payload ready for a time-series database.
        """
        now = datetime.datetime.now()
        self._update_shift_status(now)
        
        self.shift_box_count += 1

        # Create a professional, traceable ID: e.g., BOX-20260403-0322-Morning-0001
        date_str = now.strftime("%Y%m%d-%H%M")
        unique_box_id = f"BOX-{date_str}-{self.current_shift}-{self.shift_box_count:04d}"

        payload = {
            "uuid": unique_box_id,
            "yolo_session_id": yolo_id,
            "timestamp_iso": now.isoformat(),
            "shift": self.current_shift,
            "shift_count": self.shift_box_count,
            "transit_time_sec": round(lifespan_sec, 2),
            "orientation_deg": angle,
            "status": "COMPLETED"
        }

        return payload