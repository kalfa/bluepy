import io
from unittest import TestCase, mock

from bluepy.async import transport


class HelperTest(TestCase):
    @mock.patch('subprocess.Popen')
    def test_helper_instance_start_executes_helper(self, popen):
        helper = transport.BLEHelperProcess('path', stdin='stdin',
                                            stdout='stdout', stderr='stderr')
        helper.start()
        popen.assert_called_once_with(['path'], stdin='stdin', stdout='stdout',
                                      stderr='stderr', universal_newlines=True)


    @mock.patch('subprocess.Popen')
    def test_helper_instance_start_does_nothing_when_already_started(self,
                                                                     popen):
        unit = transport.BLEHelperProcess('path')
        unit.started = True
        unit.start()

        # Popen process has not been touch
        self.assertEqual(popen.mock_calls, [])

    @mock.patch('logging.debug')
    def test_helper_instance_stop_quits_and_waits_for_process_to_stop(self,
                                                                      logging):
        unit = transport.BLEHelperProcess('path')

        unit.started = True
        # unit.process is going to be assigned to None, keep an handler to the
        # mock obj
        unit.process = process = mock.MagicMock()
        unit.process.communicate.return_value = '', ''

        unit.stop()
        process.stdin.write.assert_called_once_with('quit\n')
        process.communicate.assert_called_once_with()

    def test_helper_instance_stop_does_nothing_when_already_stopped(self):
        unit = transport.BLEHelperProcess('path')
        unit.started = False
        unit.stop()

        # Popen process has not been touch
        unit.process = process = mock.MagicMock()
        self.assertEqual(process.stdin.write.mock_calls, [])


    def test_helper_instance_is_alive_when_process_is_alive(self):
        unit = transport.BLEHelperProcess('path')
        # process is still running: no exit code
        unit.process = mock.MagicMock(**{'poll.return_value':None})

        self.assertTrue(unit.is_alive())

    def test_helper_instance_is_not_alive_when_process_is_dead(self):
        unit = transport.BLEHelperProcess('path')
        # exit code of the process
        unit.process = mock.MagicMock(**{'poll.return_value': 0})

        self.assertFalse(unit.is_alive())


@mock.patch('bluepy.async.transport.BLEHelperProcess')
class TransportTest(TestCase):
    def test_foo(self, helper):
        unit = transport.Transport()
        unit.process.assert_called_once()

    @mock.patch('logging.debug')
    def test_writeline_does_not_accept_newline(self, helper, logging):
        unit = transport.Transport()
        with self.assertRaises(AssertionError):
            unit.writeline('foo\n')

    @mock.patch('logging.debug')
    @mock.patch('bluepy.async.transport.PipedFuture')
    def test_writeline_sends_command_to_helper_and_creates_future(self, piped,
                                                                  logging,
                                                                  helper):
        unit = transport.Transport()
        stdin = mock.MagicMock(spec=io.TextIOBase)

        unit.writeline('data', file_=stdin)

        stdin.write.assert_called_once_with('data\n')
        piped.assert_called_once_with(description='command "data" sent')

    def test_readline
    def test_setconnectedstate
    def test_connect
    def test_disconnect
