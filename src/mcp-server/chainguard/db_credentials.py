"""
CHAINGUARD MCP Server - Database Credential Store

Persistente, obfuskierte DB-Credentials pro Projekt.

Features:
- Pro Projekt (working_dir) separate Credentials
- XOR + Base64 Obfuskation (keine externen Dependencies)
- Automatisches Laden bei db_connect
- Automatisches Speichern nach erfolgreicher Verbindung

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
"""

import json
import base64
import hashlib
import uuid
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass, asdict

from .config import logger

if TYPE_CHECKING:
    from .db_inspector import DBConfig

# Credential storage directory
CREDENTIALS_DIR = Path.home() / ".chainguard" / "credentials"


def _get_machine_key() -> bytes:
    """
    Generate machine-specific key from MAC address + salt.
    This ensures credentials can only be decrypted on the same machine.
    """
    machine_id = str(uuid.getnode())  # MAC address as int
    salt = "chainguard-db-creds-v1"
    return hashlib.sha256(f"{machine_id}{salt}".encode()).digest()


def _xor_obfuscate(data: str, key: bytes) -> str:
    """XOR obfuscation + Base64 encoding."""
    data_bytes = data.encode('utf-8')
    obfuscated = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))
    return base64.b64encode(obfuscated).decode('ascii')


def _xor_deobfuscate(obfuscated: str, key: bytes) -> str:
    """XOR deobfuscation from Base64."""
    data_bytes = base64.b64decode(obfuscated)
    original = bytes(b ^ key[i % len(key)] for i, b in enumerate(data_bytes))
    return original.decode('utf-8')


def _project_hash(working_dir: str) -> str:
    """Generate unique hash for project path."""
    # Normalize path for consistent hashing
    normalized = str(Path(working_dir).resolve())
    return hashlib.md5(normalized.encode()).hexdigest()[:12]


@dataclass
class StoredCredentials:
    """Stored credential data structure."""
    host: str
    port: int
    user: str
    password_obfuscated: str  # Obfuscated, not plaintext!
    database: str
    db_type: str


class CredentialStore:
    """
    Stores DB credentials per project with XOR obfuscation.

    Usage:
        store = get_credential_store()
        store.save(working_dir, config)  # After successful connection
        config = store.load(working_dir)  # On next session
        store.delete(working_dir)  # To forget credentials
    """

    def __init__(self):
        self._key = _get_machine_key()
        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    def _get_path(self, working_dir: str) -> Path:
        """Get credential file path for project."""
        project_hash = _project_hash(working_dir)
        return CREDENTIALS_DIR / f"{project_hash}.json"

    def save(self, working_dir: str, config: "DBConfig") -> bool:
        """
        Save credentials after successful connection.

        Args:
            working_dir: Project working directory
            config: Database configuration with credentials

        Returns:
            True if saved successfully
        """
        try:
            creds = StoredCredentials(
                host=config.host,
                port=config.port,
                user=config.user,
                password_obfuscated=_xor_obfuscate(config.password, self._key),
                database=config.database,
                db_type=config.db_type
            )

            path = self._get_path(working_dir)
            with open(path, 'w') as f:
                json.dump(asdict(creds), f, indent=2)

            logger.info(f"DB credentials saved for {_project_hash(working_dir)}")
            return True

        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def load(self, working_dir: str) -> Optional["DBConfig"]:
        """
        Load stored credentials for project.

        Args:
            working_dir: Project working directory

        Returns:
            DBConfig if credentials exist, None otherwise
        """
        from .db_inspector import DBConfig

        path = self._get_path(working_dir)
        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            password = _xor_deobfuscate(data['password_obfuscated'], self._key)

            logger.debug(f"DB credentials loaded for {_project_hash(working_dir)}")

            return DBConfig(
                host=data['host'],
                port=data['port'],
                user=data['user'],
                password=password,
                database=data['database'],
                db_type=data['db_type']
            )

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    def delete(self, working_dir: str) -> bool:
        """
        Delete stored credentials for project.

        Args:
            working_dir: Project working directory

        Returns:
            True if deleted, False if not found
        """
        path = self._get_path(working_dir)
        if path.exists():
            path.unlink()
            logger.info(f"DB credentials deleted for {_project_hash(working_dir)}")
            return True
        return False

    def exists(self, working_dir: str) -> bool:
        """Check if credentials exist for project."""
        return self._get_path(working_dir).exists()

    def get_info(self, working_dir: str) -> Optional[dict]:
        """
        Get non-sensitive info about stored credentials.

        Returns dict with host, database, user (no password) or None.
        """
        path = self._get_path(working_dir)
        if not path.exists():
            return None

        try:
            with open(path, 'r') as f:
                data = json.load(f)

            return {
                'host': data['host'],
                'port': data['port'],
                'user': data['user'],
                'database': data['database'],
                'db_type': data['db_type']
            }
        except Exception:
            return None


# =============================================================================
# Global instance
# =============================================================================

_store: Optional[CredentialStore] = None


def get_credential_store() -> CredentialStore:
    """Get global credential store instance."""
    global _store
    if _store is None:
        _store = CredentialStore()
    return _store
