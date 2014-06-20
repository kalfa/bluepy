from unittest import TestCase, mock

from functools import partial
import queue


class CallbackChain(object):
    chained_args = tuple()
    chained_kw = dict()

    def __init__(self, cb, *args, **kw):
        self.queue = queue.Queue()
        self.partial_cb = partial(cb, *args, **kw)

    def set_chained_params(self, *args, **kw):
        self.chained_args = args
        self.chained_kw = kw

    def __call__(self, *args, **kw):
        all_args = args + self.chained_args
        all_kw = kw.copy()
        all_kw.update(self.chained_kw)
        return self.partial_cb(*all_args, **all_kw)

    def concatenate(self, cb):
        assert isinstance(cb, self.__class__)
        self.queue.put(cb)

    def __next__(self):
        try:
            queued = self.queue.get_nowait()
            # propagate (i.e. chain!) the requested chained parameters
            queued.set_chained_params(*self.chained_args, **self.chained_kw)
            return queued
        except queue.Empty:
            return None


class TestCallbackChain(TestCase):
    def test_constructor_do_not_call(self):
        cb = mock.MagicMock()
        arg = mock.MagicMock()
        kw = mock.MagicMock()

        CallbackChain(cb, arg, foo=kw)
        self.assertFalse(cb.called)

    def test_call_no_further_args(self):
        cb = mock.MagicMock()
        arg = mock.MagicMock()

        unit = CallbackChain(cb, arg)
        unit()

        cb.assert_called_once_with(arg)

    def test_call_with_further_args(self):
        """Test that positional and kw args are called.

        It needs to be possible to add a positional arg at later stage, even
        though a KW arg has been already added.
        """
        cb = mock.MagicMock()
        arg1 = mock.MagicMock()
        arg2 = mock.MagicMock()
        kw1 = mock.MagicMock()
        kw2 = mock.MagicMock()

        unit = CallbackChain(cb, arg1, kw1=kw1)
        self.assertFalse(cb.called)
        unit(arg2, kw2=kw2)
        cb.assert_called_once_with(arg1, arg2, kw1=kw1, kw2=kw2)

    def test_call_with_only_later_kw(self):
        arg = mock.MagicMock()

        def cb(result):
            return result

        unit = CallbackChain(cb)

        self.assertEqual(arg, unit(result=arg))

    def test_call_with_later_kw(self):
        arg1 = mock.MagicMock()
        arg2 = mock.MagicMock()

        def cb(arg1, result=None):
            return result

        unit = CallbackChain(cb, arg1)

        self.assertEqual(arg2, unit(result=arg2))

    def test_concatenation(self):
        cb1 = mock.Mock()
        cb2 = CallbackChain(mock.Mock())

        unit = CallbackChain(cb1)
        unit.concatenate(cb2)

        self.assertEqual(next(unit), cb2)
        self.assertEqual(next(unit), None)

    def test_chain_parameters(self):
        cb1 = mock.Mock()
        arg1 = mock.Mock()
        kw1 = mock.Mock()
        arg2 = mock.Mock()
        kw2 = mock.Mock()
        arg3 = mock.Mock()
        kw3 = mock.Mock()

        unit = CallbackChain(cb1, arg1, kw1=kw1)

        unit()
        cb1.assert_called_once_with(arg1, kw1=kw1)
        cb1.reset_mock()

        unit(arg2, kw2=kw2)
        cb1.assert_called_once_with(arg1, arg2, kw1=kw1, kw2=kw2)
        cb1.reset_mock()

        unit.set_chained_params(arg3, kw3=kw3)
        unit(arg2, kw2=kw2)
        cb1.assert_called_once_with(arg1, arg2, arg3,
                                    kw1=kw1, kw2=kw2, kw3=kw3)

    def test_chain_parameters_on_concatenated_calls(self):
        cb1 = mock.Mock()
        arg1 = mock.Mock()
        kw1 = mock.Mock()
        cb2 = mock.Mock()
        arg2 = mock.Mock()
        kw2 = mock.Mock()
        arg3 = mock.Mock()
        kw3 = mock.Mock()

        unit = CallbackChain(cb1, arg1, kw1=kw1)
        concatenated = CallbackChain(cb2, arg2, kw2=kw2)
        unit.concatenate(concatenated)
        unit.set_chained_params(arg3, kw3=kw3)

        unit()
        cb1.assert_called_once_with(arg1, arg3, kw1=kw1, kw3=kw3)
        next(unit)()
        cb2.assert_called_once_with(arg2, arg3, kw2=kw2, kw3=kw3)

