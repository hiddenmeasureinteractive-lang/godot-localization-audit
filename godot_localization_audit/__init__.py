"""Conservative, read-only localization inspection. No Godot project code is run."""

from .scanner import scan_source, scan_path, proposed_patch
from .catalog import check_catalog

__version__ = "0.1.0"
__all__ = ["scan_source", "scan_path", "proposed_patch", "check_catalog"]
