"""Callback classes"""

import queue
from functools import partial


class CallbackChain(queue.Queue):
    """Set up a callback and its parameters in a easy-to-pass way.

    An object which represents a calback, including its positional and keyword
    parameters.
    This object is designed for asynchronous operations.

    It is easy to pass more partial parameters to the function, at any stage of
    the asynchronous process.
    Multiple callbacks can be chained after this one, each one with different
    parameters.

    At the end of the process a result can be set. The result will be set on
    each of the chained callbacks as well. The result set to the callbacks is
    either the original result set to the root callback, or any result returned
    by the parent callback.

    The definition of the callback needs to have a "result_" keyword argument
    which will receive the result of the asynchronous process, an exception
    instance if the process resulted in an error, or None if no result has been
    passed.

    If the callback returns a result (i.e. a non-None value), this result will
    be passed to all the chained callback.
    The propagation of the result is only between the parent callback and the
    chained ones. If any chained callback returns a result, it won't influence
    any sibling chained callback.

    For example:
    For simplicity assume that baz, gna are defined callbacks which do some
    work and do not return anything (i.e. None)

    def foo(arg1, result_):
        # do something
        return 'new result!'

    def bar(result_):
        # do some more work
        return 'further result!'

    root_cb = CallbackChain(foo, 1)

    root_child1 = CallbackChain(bar)
    root.cb.put(root_child1)

    child1_firstborn = CallbackChain(gna, somekw='wow')
    child1_firstborn.append_partial_params('somepositional',
                                           anotherkw='another!')
    root_child1.put(child1_firstborn)

    root_child2 = CallbackChain(baz)
    root_cb.put(root_child2)



    root_cb.set_result('result')

    #  this code will create a call tree like:
    #    root (foo(1, result_=<theresult>)
    #         \-> root_child1 bar(result_=<theresult>)
    #                \-> child2_child gna('somepositional', somekw='wow',
    #                                     anotherkw='another!',
    #                                     result_=<theresult>)
    #         \-> root_child2 baz(result_<theresult>)
    #
    #  with root having a set result, produce by an async process.

    root()  # run root callback: a call to foo(1, result_='result')

    # at this point foo has been executed. since it returned something, the
    # status for the chained calls is now its retuned value: 'new result!'

    for child in root:
        child()
        for grandchild in child:
            grandchild()

    # the loop will call in this order:
    # bar(result_='new result!') -> returns 'further result!'
    # gna('somepositional', somekw='wow', anotherkw='another!',
    #     result_='further result!')
    # baz('new result!')
    #
    # note that baz has been called with the result returned by root. This is
    # because the scope of the reuslt propagation is only to the callback
    # subtree (chained callbacks, or children as called in this example).
    # baz is called by root_child2, which is in fact a chained callback added
    # to root, and for this reason it will inherit root's result.
    """
    result = None

    def __init__(self, cb, *args, **kw):
        self.partial_cb = partial(cb, *args, **kw)
        super(CallbackChain, self).__init__()

    def append_partial_params(self, *args, **kw):
        self.partial_cb = partial(self.partial_cb, *args, **kw)

    def set_result(self, value):
        self.result = value

    def put(self, cb):
        """Add a CB to be called after the current instance.

        The current instance result will be passed to any chained CB

        @param cb an instance of CallbackChain
        """
        assert isinstance(cb, self.__class__)
        super().put(cb)

    def __next__(self):
        """Return the next chained CB instance, if any"""
        try:
            queued = self.get_nowait()
            queued.set_result(self.result)
            return queued
        except queue.Empty:
            raise StopIteration

    def __iter__(self):
        return self

    def __call__(self, *args, **kw):
        self.result = self.partial_cb(result_=self.result, *args, **kw)
        return self.result
