"""Feature extraction: caption detection, figure detection, cell cleaning, ground truth comparison."""

from .captions import DetectedCaption, find_all_captions

__all__ = ["DetectedCaption", "find_all_captions"]
