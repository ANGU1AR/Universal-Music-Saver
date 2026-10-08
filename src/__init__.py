"""
Universal Music Saver Source Package.
"""
from .core import download_collection, detect_service
from .sync_manager import SyncManager
from .vk_engine import AVAILABLE_BROWSERS

__all__ = ["download_collection", "detect_service", "SyncManager", "AVAILABLE_BROWSERS"]
