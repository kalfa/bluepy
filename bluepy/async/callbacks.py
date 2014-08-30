"""Callback classes"""

import logging

from functools import partial
from concurrent import futures

log = logging.getLogger(__name__)

#import queue
#
#
#class CallbackChain(queue.Queue):
#    """Set up a callback and its parameters in a easy-to-pass way.
#
#    An object which represents a calback, including its positional and keyword
#    parameters.
#    This object is designed for asynchronous operations.
#
#    It is easy to pass more partial parameters to the function, at any stage of
#    the asynchronous process.
#    Multiple callbacks can be chained after this one, each one with different
#    parameters.
#
#    At the end of the process a result can be set. The result will be set on
#    each of the chained callbacks as well. The result set to the callbacks is
#    either the original result set to the root callback, or any result returned
#    by the parent callback.
#
#    The definition of the callback needs to have a "result_" keyword argument
#    which will receive the result of the asynchronous process, an exception
#    instance if the process resulted in an error, or None if no result has been
#    passed.
#
#    If the callback returns a result (i.e. a non-None value), this result will
#    be passed to all the chained callback.
#    The propagation of the result is only between the parent callback and the
#    chained ones. If any chained callback returns a result, it won't influence
#    any sibling chained callback.
#
#    For example:
#    For simplicity assume that baz, gna are defined callbacks which do some
#    work and do not return anything (i.e. None)
#
#    def foo(arg1, result_):
#        # do something
#        return 'new result!'
#
#    def bar(result_):
#        # do some more work
#        return 'further result!'
#
#    root_cb = CallbackChain(foo, 1)
#
#    root_child1 = CallbackChain(bar)
#    root.cb.put(root_child1)
#
#    child1_firstborn = CallbackChain(gna, somekw='wow')
#    child1_firstborn.append_partial_params('somepositional',
#                                           anotherkw='another!')
#    root_child1.put(child1_firstborn)
#
#    root_child2 = CallbackChain(baz)
#    root_cb.put(root_child2)
#
#
#
#    root_cb.set_result('result')
#
#    #  this code will create a call tree like:
#    #    root (foo(1, result_=<theresult>)
#    #         \-> root_child1 bar(result_=<theresult>)
#    #                \-> child2_child gna('somepositional', somekw='wow',
#    #                                     anotherkw='another!',
#    #                                     result_=<theresult>)
#    #         \-> root_child2 baz(result_<theresult>)
#    #
#    #  with root having a set result, produce by an async process.
#
#    root()  # run root callback: a call to foo(1, result_='result')
#
#    # at this point foo has been executed. since it returned something, the
#    # status for the chained calls is now its retuned value: 'new result!'
#
#    for child in root:
#        child()
#        for grandchild in child:
#            grandchild()
#
#    # the loop will call in this order:
#    # bar(result_='new result!') -> returns 'further result!'
#    # gna('somepositional', somekw='wow', anotherkw='another!',
#    #     result_='further result!')
#    # baz('new result!')
#    #
#    # note that baz has been called with the result returned by root. This is
#    # because the scope of the reuslt propagation is only to the callback
#    # subtree (chained callbacks, or children as called in this example).
#    # baz is called by root_child2, which is in fact a chained callback added
#    # to root, and for this reason it will inherit root's result.
#    """
#    result = None
#
#    def __init__(self, cb, *args, **kw):
#        # if cb is an instance of CallbackChain, it will trigger a double
#        # passing of result_ at __call__ time. Instead of work around it, it's
#        # cleaner if cb is required to not be an instance of CallbackChain.
#        assert not isinstance(cb, type(self)), \
#            "cb is not an instance of %s" % type(self)
#
#        self.partial_cb = partial(cb, *args, **kw)
#        super(CallbackChain, self).__init__()
#
#    def append_partial_params(self, *args, **kw):
#        self.partial_cb = partial(self.partial_cb, *args, **kw)
#
#    def set_result(self, value):
#        assert self.result is None, "result has not been set yet"
#        # Allowing Futures as result just adds complexity: it means that all
#        # the callbacks should be aware and manage this possibility.
#        # If a result is available via Future, the best thing to do is add a
#        # callbackchain.set_result call as 'done callback' to the future.
#        assert not isinstance(value, futures.Future)
#
#        self.result = value
#
#    def put(self, cb):
#        """Add a CB to be called after the current instance.
#
#        The current instance result will be passed to any chained CB
#
#        @param cb an instance of CallbackChain
#        """
#        assert isinstance(cb, self.__class__)
#        super().put(cb)
#
#    def put_future(self, future):
#        """add a Future to receive the result"""
#
#        assert isinstance(future, futures.Future)
#
#        def wrap_future(f, result_):
#            f.set_result(result_)
#            return result_
#
#        self.put(CallbackChain(wrap_future, future))
#
#    def __next__(self):
#        """Return the next chained CB instance, if any"""
#        try:
#            queued = self.get_nowait()
#            # at this point result should already be a real value and not a
#            # future (if it was when originally set).
#            assert not isinstance(self.result, futures.Future), \
#                'result is not a Future'
#            queued.set_result(self.result)
#            return queued
#        except queue.Empty:
#            raise StopIteration()
#
#    def __iter__(self):
#        return self
#
#    def __call__(self, *args, **kw):
#        self.result = self.partial_cb(result_=self.result, *args, **kw)
#        return self.result
#
#    def __str__(self):
#        return str(self.partial_cb)


class MultiverseFuture(futures.Future):
    def __init__(self):
        super(MultiverseFuture, self).__init__()
        self._done_chained_callbacks = []
        self._chained_result = futures.Future()
        print('chained result', self._chained_result, self)
        # set it running just to be sure that nothing will cancel it
        self._chained_result.set_running_or_notify_cancel()

    def chained_result(self, timeout=None):
        """Return the result of the chained call that the future represents.

        Args:
            timeout: The number of seconds to wait for the result if the future
                isn't done. If None, then there is no limit on the wait time.

        Returns:
            The result of the call that the future represents.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the given
                timeout.
            Exception: If the call raised then that exception will be raised.
        """
        with self._condition:
            if self._state in [futures._base.CANCELLED,
                               futures._base.CANCELLED_AND_NOTIFIED]:
                raise futures.CancelledError()
            elif self._chained_result._state in [futures._base.CANCELLED,
                                                 futures._base.CANCELLED_AND_NOTIFIED]:
                raise futures.CancelledError()
            elif self._state == futures._base.FINISHED and \
                    self._chained_result._state == futures._base.FINISHED:
                return self.__get_result()

            self._condition.wait(timeout)

            if self._state in [futures._base.CANCELLED,
                               futures._base.CANCELLED_AND_NOTIFIED]:
                raise futures.CancelledError()
            elif self._chained_result._state in [futures._base.CANCELLED,
                                                 futures._base.CANCELLED_AND_NOTIFIED]:
                raise futures.CancelledError()

            elif self._state == futures._base.FINISHED and \
                    self._chained_result._state == futures._base.FINISHED:
                return self.__get_result()
            else:
                raise futures.TimeoutError()

    def add_done_chained_callback(self, fn):
        """A different queue of callbacks.

        Each callback result is passed to the next one as the Future result.
        """
        assert callable(fn), 'chained callback is callable'

        print('state', self._state)
        with self._condition:
            if self._state not in [futures._base.CANCELLED,
                                   futures._base.CANCELLED_AND_NOTIFIED,
                                   futures._base.FINISHED]:
                self._done_chained_callbacks.append(fn)
                return
        result = fn(self._chained_result)
        self._chained_result.set_result(result)

    def add_done_chained_future(self, future):
        def propagate_result(to_future, from_future):
            if to_future.set_running_or_notify_cancel():
                to_future.set_result(from_future.result())
            return future.result()
        self.add_done_chained_callback(partial(propagate_result, future))

    def _invoke_callbacks(self):
        super()._invoke_callbacks()

        for callback in self._done_chained_callbacks:
            try:
                if not self._chained_result.done():
                    # first time to be called, inherit the result from the
                    # parent futurei. Changes status from RUNNING to FINISHED
                    self._chained_result.set_result(self.result())

                result = callback(self._chained_result)
                self._chained_result.set_result(result)
            except Exception:
                log.exception('exception calling callback for %r', self)
