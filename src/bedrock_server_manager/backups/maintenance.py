"""Compatibility alias; application scheduling lives in scheduler.service."""

from ..scheduler.service import Scheduler as BackupMaintenance

__all__ = ["BackupMaintenance"]
