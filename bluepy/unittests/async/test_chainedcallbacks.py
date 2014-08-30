from unittest import TestCase, mock
from concurrent import futures

from bluepy.async.callbacks import MultiverseFuture


#def identity(result_):
#    return result_
#
#
#class TestCallbackChain(TestCase):
#    def test_constructor_do_not_call(self):
#        cb = mock.MagicMock()
#        arg = mock.MagicMock()
#        kw = mock.MagicMock()
#
#        CallbackChain(cb, arg, foo=kw)
#        self.assertFalse(cb.called)
#
#    def test_call_with_only_init_args(self):
#        cb = mock.MagicMock()
#        arg = mock.MagicMock()
#
#        unit = CallbackChain(cb, arg)
#        unit()
#
#        cb.assert_called_once_with(arg, result_=None)
#
#    def test_call_with_calltime_args(self):
#        """Test that positional and kw args are passed along with result_.
#        """
#        cb = mock.MagicMock()
#        arg1 = mock.MagicMock()
#        arg2 = mock.MagicMock()
#        kw1 = mock.MagicMock()
#        kw2 = mock.MagicMock()
#
#        unit = CallbackChain(cb, arg1, kw1=kw1)
#        self.assertFalse(cb.called)
#        unit(arg2, kw2=kw2)
#        cb.assert_called_once_with(arg1, arg2, kw1=kw1, kw2=kw2, result_=None)
#
#    def test_call_with_result(self):
#        expected_result = mock.MagicMock()
#
#        unit = CallbackChain(identity)
#        unit.set_result(expected_result)
#
#        self.assertEqual(expected_result, unit())
#
#    def test_call_with_returned_modified_result(self):
#        expected_result = mock.MagicMock()
#        cb = mock.MagicMock(return_value=expected_result)
#
#        unit = CallbackChain(cb)
#        unit.set_result('first result')
#
#        self.assertEqual(unit.result, 'first result')
#        self.assertEqual(expected_result, unit())
#        self.assertEqual(expected_result, unit.result)
#
#    def test_chained_cb_have_result(self):
#        """Test that all chained cb have result passed
#        """
#        cb1 = mock.MagicMock(return_value='foo')
#        cb2 = mock.MagicMock(return_value='bar')
#        cb3 = mock.MagicMock(return_value=cb1.return_value)
#
#        unit = CallbackChain(cb1)
#        unit.put(CallbackChain(cb2))
#        unit.put(CallbackChain(cb3))
#        # setting result of unit is irrelevant in this test
#        unit()
#
#        cb = next(unit)
#        self.assertEqual(cb.result, cb1.return_value)
#        cb()
#        # the new result is the returned one for this instance
#        self.assertEqual(cb.result, cb2.return_value)
#        cb2.assert_called_once_with(result_=cb1.return_value)
#
#        cb = next(unit)
#        self.assertEqual(cb.result, cb1.return_value)
#        cb()
#        self.assertEqual(cb.result, cb3.return_value)
#        cb3.assert_called_once_with(result_=cb1.return_value)
#
#    def test_chained_cb_returned_in_order(self):
#        """Test that all chained cb have result passed
#        """
#        expected_result = mock.MagicMock()
#
#        cb1 = mock.MagicMock(return_value=expected_result)
#        cb2 = mock.MagicMock(return_value=expected_result)
#        cb3 = mock.MagicMock(return_value=expected_result)
#
#        unit = CallbackChain(cb1)
#        unit.put(CallbackChain(cb2))
#        unit.put(CallbackChain(cb3))
#
#        unit()
#
#        cb = next(unit)
#        cb()
#        cb2.assert_called_once_with(result_=expected_result)
#
#        cb = next(unit)
#        cb()
#
#    def test_nested_instances_do_not_set_result_twice(self):
#        unit = CallbackChain(identity)
#
#        with self.assertRaises(AssertionError):
#            CallbackChain(unit)
#
#    def test_result_cannot_be_future(self):
#        unit = CallbackChain(identity)
#
#        with self.assertRaises(AssertionError):
#            unit.set_result(futures.Future)
#
#    def test_future_as_callback_works(self):
#        unit = CallbackChain(identity)
#        f = futures.Future()
#        final_result = mock.MagicMock()
#        expected_result = 'result'
#
#        unit.put(identity)
#        unit.put_future(f)
#        unit.put(final_result)
#
#        unit.set_result(expected_result)
#
#        self.assertTrue(f.done())
#        self.assertEqual(f.result(), expected_result)
#        final_result.assert_called_once_with(expected_result)


def inc(f):
    if not f.done():
        raise Exception('not done')
    return f.result() + 1


def inc2(f):
    if not f.done():
        raise Exception('not done')
    return f.result() + 2


class TestMultiverseFuture(TestCase):
    def test_set_result_can_be_called_multiple_times(self):
        expected_results = range(100)
        unit = MultiverseFuture()
        for i in expected_results:
            unit.set_result(i)
            self.assertEqual(unit.result(), i)

    def test_chained_callback_result_propagate_to_the_next_one(self):
        inc1 = mock.MagicMock()
        inc1.side_effect = inc

        unit = MultiverseFuture()
        unit.add_done_chained_callback(inc1)
        unit.add_done_chained_callback(inc1)
        unit.add_done_chained_callback(inc1)

        unit.set_result(1)
        self.assertEqual(unit._chained_result.result(), 4)
        inc1.assert_has_calls([mock.call(unit._chained_result),
                               mock.call(unit._chained_result),
                               mock.call(unit._chained_result)])

    def test_results_are_separated(self):
        unit = MultiverseFuture()
        unit.add_done_chained_callback(inc2)
        unit.add_done_callback(inc)

        unit.set_result(0)
        self.assertEqual(unit.chained_result(), 1)
        self.assertEqual(unit.result(), 2)
