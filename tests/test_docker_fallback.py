import builtins
import unittest
from unittest.mock import Mock, patch

from whosat.collector.docker import collect_docker_snapshot


class DockerFallbackTests(unittest.TestCase):
    def test_disabled_returns_empty(self):
        res = collect_docker_snapshot(enabled=False)
        self.assertEqual(res.containers, [])
        self.assertEqual(res.errors, [])

    def test_missing_sdk_graceful(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'docker':
                raise ModuleNotFoundError('docker')
            return real_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=fake_import):
            res = collect_docker_snapshot(enabled=True)
        self.assertEqual(res.containers, [])
        self.assertTrue(res.errors)

    def test_missing_sdk_but_cli_daemon_reachable_gives_hint(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'docker':
                raise ModuleNotFoundError('docker')
            return real_import(name, *args, **kwargs)

        ok_running = Mock(returncode=0, stdout='id1\nid2\n', stderr='')
        ok_total = Mock(returncode=0, stdout='id1\nid2\nid3\n', stderr='')
        with patch('builtins.__import__', side_effect=fake_import), \
             patch('whosat.collector.docker.shutil.which', return_value='/usr/bin/docker'), \
             patch('whosat.collector.docker.subprocess.run', side_effect=[ok_running, ok_total]):
            res = collect_docker_snapshot(enabled=True)
        self.assertEqual(res.running_count, 2)
        self.assertEqual(res.stopped_count, 1)
        self.assertTrue(any('pip install whosat[docker]' in e for e in res.errors))

    def test_missing_sdk_and_daemon_not_running(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == 'docker':
                raise ModuleNotFoundError('docker')
            return real_import(name, *args, **kwargs)

        fail = Mock(returncode=1, stdout='', stderr='Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?')
        with patch('builtins.__import__', side_effect=fake_import), \
             patch('whosat.collector.docker.shutil.which', return_value='/usr/bin/docker'), \
             patch('whosat.collector.docker.subprocess.run', return_value=fail):
            res = collect_docker_snapshot(enabled=True)
        self.assertEqual(res.running_count, 0)
        self.assertTrue(any('Docker daemon not running' in e for e in res.errors))


if __name__ == '__main__':
    unittest.main()
