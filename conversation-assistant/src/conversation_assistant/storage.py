#!/usr/bin/env python3
"""
File storage utilities for Conversation Assistant MCP
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import tempfile
import uuid

try:
    import fcntl
except ImportError:
    # Windows doesn't have fcntl
    fcntl = None

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Storage-related errors"""
    pass


class FileStorage:
    """Handles atomic file operations with backup support"""

    def __init__(self, file_path: Path, backup_dir: Path):
        self.file_path = file_path
        self.backup_dir = backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def read_json(self) -> Dict[str, Any]:
        """
        Read JSON file with backup fallback

        Returns:
            Dict with JSON content or empty structure if file doesn't exist
        """
        try:
            if not self.file_path.exists():
                return self._empty_structure()

            with open(self.file_path, 'r', encoding='utf-8') as f:
                # Try to acquire shared lock for reading
                if fcntl:
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                    except (OSError, AttributeError):
                        # Continue without locking if not supported
                        pass

                data = json.load(f)

                # Validate structure
                if not isinstance(data, dict) or "version" not in data:
                    logger.warning(f"Invalid JSON structure in {self.file_path}")
                    return self._load_from_backup()

                return data

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {self.file_path}: {e}")
            return self._load_from_backup()
        except Exception as e:
            logger.error(f"Error reading {self.file_path}: {e}")
            return self._load_from_backup()

    def write_json(self, data: Dict[str, Any]) -> bool:
        """
        Atomically write JSON file with backup

        Args:
            data: Dictionary to write as JSON

        Returns:
            True if successful, False otherwise
        """
        try:
            # Update timestamp
            data["last_updated"] = datetime.now().isoformat()

            # Create backup before writing
            if self.file_path.exists():
                self._create_backup()

            # Atomic write using temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.tmp',
                dir=self.file_path.parent,
                delete=False,
                encoding='utf-8'
            ) as tmp_file:
                json.dump(data, tmp_file, indent=2, ensure_ascii=False)
                tmp_file.flush()
                temp_path = Path(tmp_file.name)

            # Atomic move
            shutil.move(str(temp_path), str(self.file_path))

            # Set restrictive permissions
            self.file_path.chmod(0o600)

            logger.debug(f"Successfully wrote {self.file_path}")
            return True

        except Exception as e:
            logger.error(f"Error writing {self.file_path}: {e}")
            # Cleanup temp file if it exists
            try:
                if 'temp_path' in locals() and temp_path.exists():
                    temp_path.unlink()
            except:
                pass
            return False

    def _empty_structure(self) -> Dict[str, Any]:
        """Return empty structure for rules file"""
        return {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "rules": []
        }

    def _create_backup(self) -> None:
        """Create timestamped backup of current file"""
        if not self.file_path.exists():
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{self.file_path.stem}_{timestamp}.json"
        backup_path = self.backup_dir / backup_name

        try:
            shutil.copy2(self.file_path, backup_path)
            logger.debug(f"Created backup: {backup_path}")

            # Keep only last 5 backups
            self._cleanup_old_backups()

        except Exception as e:
            logger.warning(f"Failed to create backup: {e}")

    def _cleanup_old_backups(self) -> None:
        """Keep only the 5 most recent backups"""
        try:
            pattern = f"{self.file_path.stem}_*.json"
            backups = list(self.backup_dir.glob(pattern))
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Remove old backups (keep 5)
            for backup in backups[5:]:
                backup.unlink()
                logger.debug(f"Removed old backup: {backup}")

        except Exception as e:
            logger.warning(f"Error cleaning up backups: {e}")

    def _load_from_backup(self) -> Dict[str, Any]:
        """Try to load from most recent backup"""
        try:
            pattern = f"{self.file_path.stem}_*.json"
            backups = list(self.backup_dir.glob(pattern))

            if not backups:
                logger.info("No backups available, returning empty structure")
                return self._empty_structure()

            # Sort by modification time, newest first
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            for backup in backups:
                try:
                    with open(backup, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        logger.info(f"Loaded from backup: {backup}")
                        return data
                except Exception as e:
                    logger.warning(f"Backup {backup} also corrupted: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error loading from backup: {e}")

        # If all backups fail, return empty structure
        logger.warning("All backups failed, returning empty structure")
        return self._empty_structure()