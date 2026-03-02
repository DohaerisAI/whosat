import unittest

from whosat.services.aggregator import build_categories, build_groups, merge_processes_with_containers
from whosat.types import ContainerRecord, PortBinding, ProcessRecord


class AggregatorTests(unittest.TestCase):
    def test_merge_container_onto_process_by_pid(self):
        rows = [ProcessRecord(pid=123, name='python3')]
        containers = [ContainerRecord(id='abc123', name='api', image='img', state='running', status='running', pid=123)]
        merged = merge_processes_with_containers(rows, containers)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].docker_container_name, 'api')

    def test_synthetic_docker_row_when_pid_missing(self):
        rows = []
        containers = [ContainerRecord(id='abc123', name='api', image='img', state='running', status='running', pid=None, ports=[PortBinding(8080, 'tcp', 'ipv4', '0.0.0.0')])]
        merged = merge_processes_with_containers(rows, containers)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].source, 'docker')
        self.assertEqual(merged[0].min_port, 8080)

    def test_build_categories_sections(self):
        rows = [
            ProcessRecord(pid=1, name='postgres', derived_status='ONLINE'),
            ProcessRecord(pid=2, name='python3', derived_status='WARN'),
            ProcessRecord(pid=None, name='web', source='docker', docker_container_id='x', derived_status='OFFLINE'),
        ]
        cats = build_categories(rows)
        sections = {c.key: c.section for c in cats}
        self.assertEqual(sections['all'], 'Categories')
        self.assertEqual(sections['postgres'], 'Database')
        self.assertEqual(sections['python3'], 'System')
        self.assertEqual(sections['containers'], 'Docker')
        groups = build_groups(rows)
        self.assertTrue(any(g.key == 'containers' for g in groups))


if __name__ == '__main__':
    unittest.main()
