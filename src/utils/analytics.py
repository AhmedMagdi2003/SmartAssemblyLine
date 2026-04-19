import datetime

try:
    from src.db.repositories import get_shift_event_count
except Exception:
    get_shift_event_count = None

class ProductionAnalytics:
    def __init__(self, shift_config, clock=None, shift_count_loader=None):
        self.shifts = shift_config
        self.current_shift = None
        self.current_shift_date = None
        self.shift_box_count = 0
        self.clock = clock or datetime.datetime.now
        self.shift_count_loader = shift_count_loader or get_shift_event_count

    def _resolve_active_shift(self, now):
        active_shift = "Unknown"
        shift_date = now.date()

        hour = now.hour

        for shift in self.shifts:
            start = shift['start_hour']
            end = shift['end_hour']

            if start < end:
                if start <= hour < end:
                    active_shift = shift['name']
                    shift_date = now.date()
                    break
            else: 
                if hour >= start or hour < end:
                    active_shift = shift['name']
                    shift_date = now.date()
                    if hour < end:
                        shift_date = now.date() - datetime.timedelta(days=1)
                    break

        return active_shift, shift_date

    def _load_shift_count(self, shift_name, shift_date):
        if self.shift_count_loader is None or shift_name == "Unknown":
            return 0

        try:
            return int(self.shift_count_loader(shift_name, shift_date) or 0)
        except Exception:
            return 0

    def sync_with_time(self, now=None):
        """Align the in-memory counter with the current operational shift."""
        now = now or self.clock()
        active_shift, shift_date = self._resolve_active_shift(now)
        if active_shift != self.current_shift or shift_date != self.current_shift_date:
            self.current_shift = active_shift
            self.current_shift_date = shift_date
            self.shift_box_count = self._load_shift_count(active_shift, shift_date)
        return self.current_shift, self.current_shift_date, self.shift_box_count

    def generate_dashboard_payload(self, yolo_id, lifespan_sec, angle):
        """
        Generates a standardized dictionary payload ready for a time-series database.
        """
        now = self.clock()
        _, shift_date, _ = self.sync_with_time(now)

        self.shift_box_count += 1

        date_str = shift_date.strftime("%Y%m%d")
        unique_box_id = f"BOX-{date_str}-{self.current_shift}-{self.shift_box_count:04d}"

        payload = {
            "uuid": unique_box_id,
            "yolo_session_id": yolo_id,
            "timestamp_iso": now.isoformat(),
            "shift": self.current_shift,
            "shift_date": shift_date.isoformat(),
            "shift_count": self.shift_box_count,
            "transit_time_sec": round(lifespan_sec, 2),
            "orientation_deg": angle,
            "status": "COMPLETED"
        }

        return payload
