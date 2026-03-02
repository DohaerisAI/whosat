import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from whosat.services.name_resolution import (
    extract_python_name,
    relative_time_from_epoch,
    resolve_identity,
    smart_truncate_path,
)
from whosat.types import PortBinding, ProcessRecord


class NameResolutionTests(unittest.TestCase):
    def test_python_module_uvicorn_resolves_app_target(self):
        cmd = ['python3', '-m', 'uvicorn', 'main:app', '--port', '8000']
        self.assertEqual(extract_python_name(cmd), 'main')

    def test_python_script_resolves_parent_and_script(self):
        cmd = ['python3', '/home/u/myapp/server.py']
        self.assertEqual(extract_python_name(cmd), 'myapp/server')

    def test_smart_truncate_keeps_filename(self):
        path = '/home/adwitiya24/corporate-app/src/server.py'
        out = smart_truncate_path(path, max_len=24)
        self.assertTrue(out.endswith('server.py'))
        self.assertIn('...', out)

    def test_relative_time(self):
        now = time.time()
        self.assertEqual(relative_time_from_epoch(now - 2, now), 'just now')
        self.assertEqual(relative_time_from_epoch(now - 65, now), '1m ago')

    def test_resolve_identity_docker_synthetic(self):
        row = ProcessRecord(pid=None, name='api', source='docker', docker_container_name='grafana', docker_image='grafana:10', docker_container_id='abcdef123456')
        ident = resolve_identity(row, now=time.time())
        self.assertEqual(ident.display_name, 'grafana')
        self.assertIn('container id', ident.origin_label)

    def test_resolve_identity_node_package_name(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / 'package.json').write_text('{"name": "yoda-frontend"}', encoding='utf-8')
            script = root / 'src' / 'server.js'
            script.parent.mkdir(parents=True)
            script.write_text('console.log(1)', encoding='utf-8')
            row = ProcessRecord(pid=1, name='node', cmdline=['node', str(script)], cwd=str(script.parent))
            ident = resolve_identity(row)
            self.assertEqual(ident.display_name, 'yoda-frontend')


if __name__ == '__main__':
    unittest.main()
