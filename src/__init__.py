__all__ = ["AssemblyLineTracker", "calculate_box_angle"]


def __getattr__(name):
    if name == "AssemblyLineTracker":
        from .core.tracking import AssemblyLineTracker

        return AssemblyLineTracker
    if name == "calculate_box_angle":
        from .core.orientation import calculate_box_angle

        return calculate_box_angle
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
