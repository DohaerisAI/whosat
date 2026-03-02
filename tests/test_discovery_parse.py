import unittest

from whosat.collector.system import _apply_well_known_and_noise_filter, parse_ss_output


class ParseSsOutputTests(unittest.TestCase):
    def test_parse_ipv4_line(self):
        out = 'LISTEN 0 128 0.0.0.0:5433 0.0.0.0:* users:(("postgres",pid=712,fd=5))\n'
        rows = parse_ss_output(out, proto='TCP')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['ip'], '0.0.0.0')
        self.assertEqual(rows[0]['port'], 5433)
        self.assertEqual(rows[0]['proto'], 'TCP')
        self.assertEqual(rows[0]['pid'], 712)
        self.assertEqual(rows[0]['proc_name'], 'postgres')

    def test_parse_ipv6_line(self):
        out = 'LISTEN 0 128 [::1]:5433 [::]:* users:(("postgres",pid=712,fd=6))\n'
        rows = parse_ss_output(out, proto='TCP')
        self.assertEqual(rows[0]['ip'], '::1')
        self.assertEqual(rows[0]['family'], 'IPv6')

    def test_parse_without_users(self):
        out = 'UNCONN 0 0 127.0.0.53:53 0.0.0.0:*\n'
        rows = parse_ss_output(out, proto='UDP')
        self.assertEqual(rows[0]['pid'], None)
        self.assertEqual(rows[0]['proc_name'], None)
        self.assertEqual(rows[0]['proto'], 'UDP')

    def test_well_known_fallback_for_missing_pid(self):
        rows, filtered = _apply_well_known_and_noise_filter(
            [{"port": 5433, "ip": "127.0.0.1", "proto": "TCP", "family": "IPv4", "pid": None, "proc_name": None, "state": "LISTEN"}]
        )
        self.assertEqual(filtered, 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["proc_name"], "postgres")

    def test_noise_filtered_for_unknown_missing_pid(self):
        rows, filtered = _apply_well_known_and_noise_filter(
            [{"port": 9999, "ip": "127.0.0.1", "proto": "TCP", "family": "IPv4", "pid": None, "proc_name": None, "state": "LISTEN"}]
        )
        self.assertEqual(rows, [])
        self.assertEqual(filtered, 1)


if __name__ == '__main__':
    unittest.main()
