import unittest
from unittest.mock import patch

from whosat.services import actions
from whosat.types import ProcessRecord


class KillActionTests(unittest.TestCase):
    def test_can_kill_only_for_pid(self):
        self.assertTrue(actions.can_kill(ProcessRecord(pid=10, name='x')))
        self.assertFalse(actions.can_kill(ProcessRecord(pid=None, name='x', source='docker')))

    @patch('whosat.services.actions.os.kill')
    def test_send_term_ok(self, mock_kill):
        res = actions.send_term(10)
        self.assertTrue(res.ok)
        self.assertEqual(res.signal_sent, actions.signal.SIGTERM)
        mock_kill.assert_called_once_with(10, actions.signal.SIGTERM)

    @patch('whosat.services.actions.pid_exists', side_effect=[True, False])
    @patch('whosat.services.actions.send_term')
    @patch('whosat.services.actions.time.sleep')
    def test_terminate_then_check_terminates(self, _sleep, mock_send_term, mock_exists):
        mock_send_term.return_value = actions.KillResult(True, 'SIGTERM sent', 20, actions.signal.SIGTERM)
        res = actions.terminate_then_check(20, grace_seconds=0.3)
        self.assertTrue(res.ok)
        self.assertFalse(res.still_running)

    @patch('whosat.services.actions.pid_exists', return_value=True)
    @patch('whosat.services.actions.send_term')
    @patch('whosat.services.actions.time.sleep')
    def test_terminate_then_check_still_running(self, _sleep, mock_send_term, _exists):
        mock_send_term.return_value = actions.KillResult(True, 'SIGTERM sent', 21, actions.signal.SIGTERM)
        res = actions.terminate_then_check(21, grace_seconds=0.01)
        self.assertTrue(res.still_running)
        self.assertIn('still running', res.message)


if __name__ == '__main__':
    unittest.main()
