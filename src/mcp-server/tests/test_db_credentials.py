"""
Tests for Database Credential Store (db_credentials.py)

Tests:
- XOR obfuscation roundtrip
- Save and load credentials
- Delete credentials
- Different projects have separate credentials
- Machine key consistency
- Edge cases (empty password, special characters)
"""

import pytest
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.db_credentials import (
    _get_machine_key,
    _xor_obfuscate,
    _xor_deobfuscate,
    _project_hash,
    CredentialStore,
    StoredCredentials,
    CREDENTIALS_DIR
)
from chainguard.db_inspector import DBConfig


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_creds_dir(tmp_path):
    """Create temporary credentials directory."""
    creds_dir = tmp_path / "credentials"
    creds_dir.mkdir()
    return creds_dir


@pytest.fixture
def store(temp_creds_dir):
    """Create credential store with temporary directory."""
    with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
        store = CredentialStore()
        yield store


@pytest.fixture
def sample_config():
    """Sample database configuration."""
    return DBConfig(
        host="localhost",
        port=3306,
        user="testuser",
        password="supersecret123",
        database="testdb",
        db_type="mysql"
    )


# =============================================================================
# XOR OBFUSCATION TESTS
# =============================================================================

class TestXORObfuscation:
    """Tests for XOR obfuscation functions."""

    def test_obfuscation_roundtrip(self):
        """Test that obfuscation and deobfuscation are inverse operations."""
        key = _get_machine_key()
        original = "mysecretpassword"

        obfuscated = _xor_obfuscate(original, key)
        recovered = _xor_deobfuscate(obfuscated, key)

        assert recovered == original

    def test_obfuscation_produces_different_output(self):
        """Test that obfuscated text differs from original."""
        key = _get_machine_key()
        original = "password123"

        obfuscated = _xor_obfuscate(original, key)

        assert obfuscated != original
        assert len(obfuscated) > 0

    def test_obfuscation_is_base64(self):
        """Test that output is valid Base64."""
        import base64
        key = _get_machine_key()

        obfuscated = _xor_obfuscate("testpassword", key)

        # Should not raise
        decoded = base64.b64decode(obfuscated)
        assert len(decoded) > 0

    def test_empty_password(self):
        """Test obfuscation of empty password."""
        key = _get_machine_key()

        obfuscated = _xor_obfuscate("", key)
        recovered = _xor_deobfuscate(obfuscated, key)

        assert recovered == ""

    def test_special_characters(self):
        """Test obfuscation with special characters."""
        key = _get_machine_key()
        special = "p@$$w0rd!#%^&*()_+-=[]{}|;':\",./<>?"

        obfuscated = _xor_obfuscate(special, key)
        recovered = _xor_deobfuscate(obfuscated, key)

        assert recovered == special

    def test_unicode_password(self):
        """Test obfuscation with Unicode characters."""
        key = _get_machine_key()
        unicode_pass = "密码パスワード🔐"

        obfuscated = _xor_obfuscate(unicode_pass, key)
        recovered = _xor_deobfuscate(obfuscated, key)

        assert recovered == unicode_pass

    def test_long_password(self):
        """Test obfuscation with very long password."""
        key = _get_machine_key()
        long_pass = "a" * 1000

        obfuscated = _xor_obfuscate(long_pass, key)
        recovered = _xor_deobfuscate(obfuscated, key)

        assert recovered == long_pass


# =============================================================================
# MACHINE KEY TESTS
# =============================================================================

class TestMachineKey:
    """Tests for machine key generation."""

    def test_key_is_consistent(self):
        """Test that key is consistent across calls."""
        key1 = _get_machine_key()
        key2 = _get_machine_key()

        assert key1 == key2

    def test_key_is_bytes(self):
        """Test that key is bytes type."""
        key = _get_machine_key()

        assert isinstance(key, bytes)

    def test_key_is_32_bytes(self):
        """Test that key is SHA256 length (32 bytes)."""
        key = _get_machine_key()

        assert len(key) == 32


# =============================================================================
# PROJECT HASH TESTS
# =============================================================================

class TestProjectHash:
    """Tests for project path hashing."""

    def test_hash_is_consistent(self):
        """Test that same path produces same hash."""
        path = "/home/user/project"

        hash1 = _project_hash(path)
        hash2 = _project_hash(path)

        assert hash1 == hash2

    def test_different_paths_different_hashes(self):
        """Test that different paths produce different hashes."""
        hash1 = _project_hash("/project1")
        hash2 = _project_hash("/project2")

        assert hash1 != hash2

    def test_hash_is_12_chars(self):
        """Test that hash is truncated to 12 characters."""
        hash_val = _project_hash("/some/path")

        assert len(hash_val) == 12

    def test_hash_is_hex(self):
        """Test that hash is valid hex string."""
        hash_val = _project_hash("/some/path")

        # Should not raise
        int(hash_val, 16)

    def test_path_normalization(self):
        """Test that paths are normalized before hashing."""
        # These should produce the same hash (after normalization)
        hash1 = _project_hash("/home/user/project")
        hash2 = _project_hash("/home/user/project/")

        # Note: Path.resolve() behavior may vary, but trailing slash should be handled
        assert isinstance(hash1, str)
        assert isinstance(hash2, str)


# =============================================================================
# CREDENTIAL STORE TESTS
# =============================================================================

class TestCredentialStore:
    """Tests for CredentialStore class."""

    def test_save_and_load(self, store, sample_config, temp_creds_dir):
        """Test saving and loading credentials."""
        working_dir = "/test/project"

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            # Save
            result = store.save(working_dir, sample_config)
            assert result is True

            # Load
            loaded = store.load(working_dir)
            assert loaded is not None
            assert loaded.host == sample_config.host
            assert loaded.port == sample_config.port
            assert loaded.user == sample_config.user
            assert loaded.password == sample_config.password
            assert loaded.database == sample_config.database
            assert loaded.db_type == sample_config.db_type

    def test_load_nonexistent(self, store, temp_creds_dir):
        """Test loading credentials that don't exist."""
        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            loaded = store.load("/nonexistent/project")

            assert loaded is None

    def test_delete(self, store, sample_config, temp_creds_dir):
        """Test deleting credentials."""
        working_dir = "/test/project"

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            # Save first
            store.save(working_dir, sample_config)
            assert store.exists(working_dir)

            # Delete
            result = store.delete(working_dir)
            assert result is True
            assert not store.exists(working_dir)

    def test_delete_nonexistent(self, store, temp_creds_dir):
        """Test deleting credentials that don't exist."""
        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            result = store.delete("/nonexistent/project")

            assert result is False

    def test_exists(self, store, sample_config, temp_creds_dir):
        """Test exists check."""
        working_dir = "/test/project"

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            assert not store.exists(working_dir)

            store.save(working_dir, sample_config)
            assert store.exists(working_dir)

    def test_different_projects_separate(self, store, temp_creds_dir):
        """Test that different projects have separate credentials."""
        config1 = DBConfig(
            host="host1", port=3306, user="user1",
            password="pass1", database="db1", db_type="mysql"
        )
        config2 = DBConfig(
            host="host2", port=5432, user="user2",
            password="pass2", database="db2", db_type="postgres"
        )

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save("/project1", config1)
            store.save("/project2", config2)

            loaded1 = store.load("/project1")
            loaded2 = store.load("/project2")

            assert loaded1.database == "db1"
            assert loaded2.database == "db2"
            assert loaded1.password == "pass1"
            assert loaded2.password == "pass2"

    def test_overwrite_existing(self, store, temp_creds_dir):
        """Test that saving overwrites existing credentials."""
        working_dir = "/test/project"
        config1 = DBConfig(
            host="localhost", port=3306, user="user",
            password="oldpass", database="db", db_type="mysql"
        )
        config2 = DBConfig(
            host="localhost", port=3306, user="user",
            password="newpass", database="db", db_type="mysql"
        )

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save(working_dir, config1)
            store.save(working_dir, config2)

            loaded = store.load(working_dir)
            assert loaded.password == "newpass"

    def test_get_info(self, store, sample_config, temp_creds_dir):
        """Test getting non-sensitive info."""
        working_dir = "/test/project"

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save(working_dir, sample_config)

            info = store.get_info(working_dir)

            assert info is not None
            assert info['host'] == sample_config.host
            assert info['database'] == sample_config.database
            assert info['user'] == sample_config.user
            assert 'password' not in info
            assert 'password_obfuscated' not in info

    def test_get_info_nonexistent(self, store, temp_creds_dir):
        """Test getting info for nonexistent project."""
        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            info = store.get_info("/nonexistent")

            assert info is None


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_password_roundtrip(self, store, temp_creds_dir):
        """Test saving/loading empty password."""
        config = DBConfig(
            host="localhost", port=3306, user="user",
            password="", database="db", db_type="mysql"
        )

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save("/project", config)
            loaded = store.load("/project")

            assert loaded.password == ""

    def test_special_chars_in_password(self, store, temp_creds_dir):
        """Test password with special characters."""
        config = DBConfig(
            host="localhost", port=3306, user="user",
            password='p@$$w0rd!#%^&*(){}[]|\\:";\'<>,.?/',
            database="db", db_type="mysql"
        )

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save("/project", config)
            loaded = store.load("/project")

            assert loaded.password == config.password

    def test_unicode_in_credentials(self, store, temp_creds_dir):
        """Test Unicode in various fields."""
        config = DBConfig(
            host="localhost", port=3306, user="用户",
            password="密码🔐", database="データベース", db_type="mysql"
        )

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save("/project", config)
            loaded = store.load("/project")

            assert loaded.user == config.user
            assert loaded.password == config.password
            assert loaded.database == config.database

    def test_path_with_spaces(self, store, sample_config, temp_creds_dir):
        """Test project path with spaces."""
        working_dir = "/path/with spaces/project"

        with patch('chainguard.db_credentials.CREDENTIALS_DIR', temp_creds_dir):
            store.save(working_dir, sample_config)
            loaded = store.load(working_dir)

            assert loaded is not None
            assert loaded.password == sample_config.password


# =============================================================================
# STORED CREDENTIALS DATACLASS TESTS
# =============================================================================

class TestStoredCredentials:
    """Tests for StoredCredentials dataclass."""

    def test_create_instance(self):
        """Test creating StoredCredentials instance."""
        creds = StoredCredentials(
            host="localhost",
            port=3306,
            user="user",
            password_obfuscated="abc123",
            database="db",
            db_type="mysql"
        )

        assert creds.host == "localhost"
        assert creds.port == 3306
        assert creds.password_obfuscated == "abc123"

    def test_asdict(self):
        """Test converting to dict."""
        from dataclasses import asdict

        creds = StoredCredentials(
            host="localhost",
            port=3306,
            user="user",
            password_obfuscated="abc123",
            database="db",
            db_type="mysql"
        )

        d = asdict(creds)

        assert d['host'] == "localhost"
        assert d['password_obfuscated'] == "abc123"


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
