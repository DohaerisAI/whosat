import unittest

from whosat.services.filters import apply_filters, row_matches_search
from whosat.types import PortBinding, ProcessRecord


class FilterTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            ProcessRecord(pid=1, name='python3', cmdline=['uvicorn', 'main:app'], cpu_percent=2.0, memory_bytes=100, ports=[PortBinding(8000, 'tcp', 'ipv4', '0.0.0.0')]),
            ProcessRecord(pid=2, name='postgres', cpu_percent=1.0, memory_bytes=200, ports=[PortBinding(5432, 'tcp', 'ipv4', '127.0.0.1')]),
            ProcessRecord(pid=None, name='web', source='docker', docker_container_id='abc', docker_container_name='web', docker_image='nginx:latest', memory_bytes=50),
        ]

    def test_search_matches_port_and_ip(self):
        self.assertTrue(row_matches_search(self.rows[0], '8000'))
        self.assertTrue(row_matches_search(self.rows[0], '0.0.0.0'))
        self.assertFalse(row_matches_search(self.rows[0], '5432'))

    def test_scope_filter_docker(self):
        out = apply_filters(self.rows, search_query='', scope='docker', category_key='all', sort_by='name', sort_order='asc')
        self.assertEqual([r.name for r in out], ['web'])

    def test_category_filter(self):
        out = apply_filters(self.rows, search_query='', scope='all', category_key='postgres', sort_by='name', sort_order='asc')
        self.assertEqual([r.name for r in out], ['postgres'])

    def test_sort_by_port_asc(self):
        out = apply_filters(self.rows, search_query='', scope='all', category_key='all', sort_by='port', sort_order='asc')
        self.assertEqual([r.name for r in out][:2], ['postgres', 'python3'])


if __name__ == '__main__':
    unittest.main()
