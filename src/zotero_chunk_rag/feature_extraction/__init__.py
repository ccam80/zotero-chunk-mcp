"""Table extraction pipeline — composable multi-method extraction with confidence-weighted boundary combination."""

from .captions import DetectedCaption, find_all_captions

__all__ = ["DetectedCaption", "find_all_captions"]
