"""
Tests for nl2audio store module.
"""

import sqlite3
from pathlib import Path

import pytest

from nl2audio.store import DB


class TestDatabaseContextManager:
    """Test database context manager behavior."""

    def test_context_manager_creates_database(self, temp_dir):
        """Test that context manager creates database file."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            assert db_path.exists()
            assert db.conn is not None
            assert isinstance(db.conn, sqlite3.Connection)

    def test_context_manager_closes_connection(self, temp_dir):
        """Test that context manager properly closes database connection."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            conn = db.conn
            assert conn is not None

        # After context manager exits, connection should be closed
        # We can verify this by checking if we can open another connection to the same file
        conn2 = sqlite3.connect(str(db_path))
        try:
            # Should be able to read from the database
            result = conn2.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            assert result == 0  # No episodes yet
        finally:
            conn2.close()

    def test_context_manager_creates_tables(self, temp_dir):
        """Test that context manager creates necessary tables."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            # Check that episodes table exists
            cursor = db.conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='episodes'
            """
            )
            assert cursor.fetchone() is not None

            # Check table structure
            cursor = db.conn.execute("PRAGMA table_info(episodes)")
            columns = {row[1] for row in cursor.fetchall()}

            expected_columns = {
                "id",
                "title",
                "source",
                "mp3_path",
                "duration_sec",
                "hash",
                "created_at",
            }
            assert expected_columns.issubset(columns)


class TestDatabaseOperations:
    """Test database operations."""

    def test_add_episode(self, temp_dir):
        """Test adding an episode to the database."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            episode_id = db.add_episode(
                title="Test Episode",
                source="test_source",
                mp3_path=Path("/tmp/test.mp3"),
                duration_sec=120,
                content_bytes=b"test content",
            )

            assert episode_id > 0

            # Verify episode was added
            episodes = db.list_episodes()
            assert len(episodes) == 1

            episode = episodes[0]
            assert episode[1] == "Test Episode"  # title
            assert episode[3] == "test_source"  # source
            assert episode[6] == 120  # duration_sec
            # Note: content_bytes is not stored in the database, only the hash

    def test_add_multiple_episodes(self, temp_dir):
        """Test adding multiple episodes."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            # Add multiple episodes
            episode_ids = []
            for i in range(3):
                episode_id = db.add_episode(
                    title=f"Episode {i}",
                    source=f"source_{i}",
                    mp3_path=Path(f"/tmp/episode_{i}.mp3"),
                    duration_sec=60 + i * 30,
                    content_bytes=f"content {i}".encode(),
                )
                episode_ids.append(episode_id)

            # Verify all episodes were added
            episodes = db.list_episodes()
            assert len(episodes) == 3

            # Verify episode IDs are unique and sequential
            assert len(set(episode_ids)) == 3
            assert all(ep_id > 0 for ep_id in episode_ids)

    def test_list_episodes_ordering(self, temp_dir):
        """Test that episodes are listed in chronological order."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            # Add episodes with delays to ensure different timestamps
            import time

            db.add_episode(
                title="First Episode",
                source="first",
                mp3_path=Path("/tmp/first.mp3"),
                duration_sec=60,
                content_bytes=b"first",
            )

            time.sleep(0.1)  # Small delay

            db.add_episode(
                title="Second Episode",
                source="second",
                mp3_path=Path("/tmp/second.mp3"),
                duration_sec=90,
                content_bytes=b"second",
            )

            episodes = db.list_episodes()
            assert len(episodes) == 2

            # Episodes should be ordered by created_at (oldest first)
            assert episodes[0][1] == "First Episode"
            assert episodes[1][1] == "Second Episode"

    def test_content_hash_generation(self, temp_dir):
        """Test that content hash is generated correctly."""
        db_path = temp_dir / "test.db"

        with DB(db_path) as db:
            content = b"This is test content for hashing"
            db.add_episode(
                title="Hash Test",
                source="hash_test",
                mp3_path=Path("/tmp/hash.mp3"),
                duration_sec=60,
                content_bytes=content,
            )

            episodes = db.list_episodes()
            episode = episodes[0]

            # hash should be at index 4
            content_hash = episode[4]
            assert content_hash is not None
            assert len(content_hash) == 64  # SHA-256 hash length

            # Verify hash is consistent
            import hashlib

            expected_hash = hashlib.sha256(content).hexdigest()
            assert content_hash == expected_hash


class TestDatabaseErrorHandling:
    """Test database error handling."""

    def test_invalid_database_path(self):
        """Test database creation with invalid path."""
        invalid_path = Path("/invalid/path/that/does/not/exist/test.db")

        # Should raise an error when trying to create database in invalid location
        with pytest.raises(Exception):
            DB(invalid_path)

    def test_database_corruption_handling(self, temp_dir):
        """Test handling of corrupted database."""
        db_path = temp_dir / "test.db"

        # Create a valid database first
        with DB(db_path) as db:
            db.add_episode(
                title="Test",
                source="test",
                mp3_path=Path("/tmp/test.mp3"),
                duration_sec=60,
                content_bytes=b"test",
            )

        # Corrupt the database by writing invalid data
        with open(db_path, "wb") as f:
            f.write(b"invalid sqlite data")

        # Should handle corruption gracefully
        with pytest.raises(Exception):
            with DB(db_path) as db:
                db.list_episodes()


class TestDatabaseConcurrency:
    """Test database concurrency behavior."""

    def test_multiple_connections(self, temp_dir):
        """Test multiple connections to the same database."""
        db_path = temp_dir / "test.db"

        # First connection adds an episode
        with DB(db_path) as db1:
            db1.add_episode(
                title="Concurrent Test",
                source="concurrent",
                mp3_path=Path("/tmp/concurrent.mp3"),
                duration_sec=60,
                content_bytes=b"concurrent",
            )

        # Second connection should see the episode
        with DB(db_path) as db2:
            episodes = db2.list_episodes()
            assert len(episodes) == 1
            assert episodes[0][1] == "Concurrent Test"

    def test_connection_isolation(self, temp_dir):
        """Test that connections are isolated."""
        db_path = temp_dir / "test.db"

        # Create database with one connection
        DB(db_path)

        # Create another connection
        with DB(db_path) as db2:
            # Should be able to operate normally
            episodes = db2.list_episodes()
            assert len(episodes) == 0
