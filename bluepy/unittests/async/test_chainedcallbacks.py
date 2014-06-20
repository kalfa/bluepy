from unittest import TestCase, mock

from async.callbacks import CallbackChain

def identity(result_):
    return result_


class TestCallbackChain(TestCase):
    def test_constructor_do_not_call(self):
        cb = mock.MagicMock()
        arg = mock.MagicMock()
        kw = mock.MagicMock()

        CallbackChain(cb, arg, foo=kw)
        self.assertFalse(cb.called)

    def test_call_with_only_init_args(self):
        cb = mock.MagicMock()
        arg = mock.MagicMock()

        unit = CallbackChain(cb, arg)
        unit()

        cb.assert_called_once_with(arg, result_=None)

    def test_call_with_calltime_args(self):
        """Test that positional and kw args are passed along with result_.
        """
        cb = mock.MagicMock()
        arg1 = mock.MagicMock()
        arg2 = mock.MagicMock()
        kw1 = mock.MagicMock()
        kw2 = mock.MagicMock()

        unit = CallbackChain(cb, arg1, kw1=kw1)
        self.assertFalse(cb.called)
        unit(arg2, kw2=kw2)
        cb.assert_called_once_with(arg1, arg2, kw1=kw1, kw2=kw2, result_=None)

    def test_call_with_result(self):
        expected_result = mock.MagicMock()

        unit = CallbackChain(identity)
        unit.set_result(expected_result)

        self.assertEqual(expected_result, unit())

    def test_call_with_returned_modified_result(self):
        expected_result = mock.MagicMock()
        cb = mock.MagicMock(return_value=expected_result)

        unit = CallbackChain(cb)
        unit.set_result('first result')

        self.assertEqual(unit.result, 'first result')
        self.assertEqual(expected_result, unit())
        self.assertEqual(expected_result, unit.result)

    def test_chained_cb_have_result(self):
        """Test that all chained cb have result passed
        """
        cb1 = mock.MagicMock(return_value='foo')
        cb2 = mock.MagicMock(return_value='bar')
        cb3 = mock.MagicMock(return_value=cb1.return_value)

        unit = CallbackChain(cb1)
        unit.put(CallbackChain(cb2))
        unit.put(CallbackChain(cb3))
        # setting result of unit is irrelevant in this test
        unit()

        cb = next(unit)
        self.assertEqual(cb.result, cb1.return_value)
        cb()
        # the new result is the returned one for this instance
        self.assertEqual(cb.result, cb2.return_value)
        cb2.assert_called_once_with(result_=cb1.return_value)

        cb = next(unit)
        self.assertEqual(cb.result, cb1.return_value)
        cb()
        self.assertEqual(cb.result, cb3.return_value)
        cb3.assert_called_once_with(result_=cb1.return_value)

    def test_chained_cb_returned_in_order(self):
        """Test that all chained cb have result passed
        """
        expected_result = mock.MagicMock()

        cb1 = mock.MagicMock(return_value=expected_result)
        cb2 = mock.MagicMock(return_value=expected_result)
        cb3 = mock.MagicMock(return_value=expected_result)

        unit = CallbackChain(cb1)
        unit.put(CallbackChain(cb2))
        unit.put(CallbackChain(cb3))

        unit()

        cb = next(unit)
        cb()
        cb2.assert_called_once_with(result_=expected_result)

        cb = next(unit)
        cb()
        cb3.assert_called_once_with(result_=expected_result)
