"""Pruebas del agente web sin secretos, red ni bases de datos reales."""
import asyncio
import os
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
scratch = os.environ.get('TMPDIR')
with tempfile.TemporaryDirectory(prefix='web-chat-tests-', dir=scratch) as tmp:
    with patch.dict(os.environ, {'SQLITE_PATH': str(Path(tmp) / 'test.db')}, clear=True), patch('dotenv.load_dotenv', return_value=False), patch.object(socket.socket, 'connect', side_effect=AssertionError('Conexión de red bloqueada en tests')):
        if '--pytest' in sys.argv:
            import database
            asyncio.run(database.init_db())
            import pytest
            sys.exit(pytest.main([str(root), '-q', '-p', 'no:cacheprovider']))
        loader = unittest.defaultTestLoader
        suite = loader.loadTestsFromNames(sys.argv[1:]) if len(sys.argv) > 1 else loader.discover(str(root), pattern='test_*.py')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        print(f'RESUMEN tests={result.testsRun} fallos={len(result.failures)} errores={len(result.errors)}')
        sys.exit(0 if result.wasSuccessful() else 1)
