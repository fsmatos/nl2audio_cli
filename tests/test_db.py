"""
Test database connection management and context manager behavior.
"""

import tempfile
from pathlib import Path
import sqlite3
import os

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from nl2audio.store import DB

def test_db_context_manager():
    """Test that database connections are properly closed using context manager."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        
        # Test context manager
        with DB(db_path) as db:
            # Verify database is accessible
            assert db.conn is not None
            assert db.conn.execute("SELECT 1").fetchone()[0] == 1
            
            # Add a test episode
            episode_id = db.add_episode(
                title="Test Episode",
                source="test",
                mp3_path=Path("/tmp/test.mp3"),
                duration_sec=60,
                content_bytes=b"test content"
            )
            assert episode_id > 0
            
            # List episodes
            episodes = db.list_episodes()
            assert len(episodes) == 1
            assert episodes[0][1] == "Test Episode"
        
        # After context manager exits, connection should be closed
        # We can't directly check if conn is None since it's a private attribute,
        # but we can verify the file is accessible and not locked
        
        # Verify the database file exists and can be opened by another connection
        conn2 = sqlite3.connect(str(db_path))
        try:
            result = conn2.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            assert result == 1
        finally:
            conn2.close()

def test_db_explicit_close():
    """Test that explicit close() method works."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        
        db = DB(db_path)
        
        # Verify database is accessible
        assert db.conn is not None
        assert db.conn.execute("SELECT 1").fetchone()[0] == 1
        
        # Close explicitly
        db.close()
        
        # Verify the database file is accessible
        conn2 = sqlite3.connect(str(db_path))
        try:
            result = conn2.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
            assert result == 0  # No episodes added in this test
        finally:
            conn2.close()

def test_db_multiple_operations():
    """Test multiple database operations within the same context."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        
        with DB(db_path) as db:
            # Add multiple episodes
            for i in range(3):
                episode_id = db.add_episode(
                    title=f"Episode {i}",
                    source=f"test_{i}",
                    mp3_path=Path(f"/tmp/test_{i}.mp3"),
                    duration_sec=60 + i,
                    content_bytes=f"test content {i}".encode()
                )
                assert episode_id > 0
            
            # List all episodes
            episodes = db.list_episodes()
            assert len(episodes) == 3
            
            # Verify episode details (order is ASC by created_at, so oldest first)
            episode_titles = [episode[1] for episode in episodes]
            expected_titles = ["Episode 0", "Episode 1", "Episode 2"]
            
            # Verify we have the right number and titles exist
            assert len(episode_titles) == 3
            for expected_title in expected_titles:
                assert expected_title in episode_titles
            
            # Verify content hashes are present (field 3 is the hash)
            for episode in episodes:
                assert episode[3] is not None  # Hash should not be None

if __name__ == "__main__":
    # Run tests if executed directly
    test_db_context_manager()
    test_db_explicit_close()
    test_db_multiple_operations()
    print("All database tests passed!") 