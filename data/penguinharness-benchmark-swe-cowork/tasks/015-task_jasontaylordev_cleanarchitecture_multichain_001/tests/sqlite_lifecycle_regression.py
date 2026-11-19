"""Verify the actual schema observer releases WAL locks before the next host."""
import gc
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent/'private-runtime/task-environment'))
from sqlite_support import table_names


class SQLiteLifecycleRegression(unittest.TestCase):
    def test_observer_releases_wal_connection_without_garbage_collection(self):
        with tempfile.TemporaryDirectory(prefix='sqlite-schema-') as name:
            path=Path(name)/'app.db'
            seed=sqlite3.connect(path)
            try:
                seed.execute('PRAGMA journal_mode=WAL')
                seed.execute('CREATE TABLE TodoLists (id INTEGER)')
                seed.commit()
            finally:
                seed.close()
            enabled=gc.isenabled()
            gc.disable()
            try:
                self.assertEqual(table_names(path), {'TodoLists'})
                writer=sqlite3.connect(path, timeout=.1)
                try:
                    self.assertEqual(writer.execute('PRAGMA journal_mode=DELETE').fetchone()[0], 'delete')
                finally:
                    writer.close()
            finally:
                if enabled:
                    gc.enable()
                gc.collect()

    def test_missing_store_is_not_created_by_observation(self):
        with tempfile.TemporaryDirectory(prefix='sqlite-schema-') as name:
            path=Path(name)/'absent.db'
            with self.assertRaises(sqlite3.OperationalError):
                table_names(path)
            self.assertFalse(path.exists())


if __name__=='__main__':
    unittest.main()
