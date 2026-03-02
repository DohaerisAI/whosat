import unittest

from whosat.services.status import derive_row_status
from whosat.types import PortBinding, ProcessRecord


class StatusTests(unittest.TestCase):
    def test_online_with_listener(self):
        row = ProcessRecord(pid=1, name='python', ports=[PortBinding(8000, 'tcp', 'ipv4', '0.0.0.0')])
        self.assertEqual(derive_row_status(row), 'ONLINE')

    def test_warn_on_high_cpu(self):
        row = ProcessRecord(pid=1, name='python', cpu_percent=95.0)
        self.assertEqual(derive_row_status(row), 'WARN')

    def test_warn_on_high_memory(self):
        row = ProcessRecord(pid=1, name='python', memory_percent=90.0)
        self.assertEqual(derive_row_status(row), 'WARN')

    def test_offline_docker_synthetic(self):
        row = ProcessRecord(pid=None, name='svc', source='docker')
        self.assertEqual(derive_row_status(row), 'OFFLINE')


if __name__ == '__main__':
    unittest.main()
