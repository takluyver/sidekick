import time
import types
from collections.abc import Iterable, Mapping
from functools import singledispatch
from typing import Callable, TypeVar

from sidekick.functions.combinators import always
from .. import _toolz as toolz
from .._fn import fn, quick_fn, extract_function

NOT_GIVEN = object()
T = TypeVar("T")
S = TypeVar("S")

__all__ = [
    *["call", "call_over", "do"],  # Function calling
    *["splice"],  # Call filtering
    *["error", "ignore_error", "retry"],  # Error control
    *["flip", "select_args", "skip_args", "keep_args"],  # Arg control
    *["force_function"],  # Misc
]


#
# Function calling
#
def call(*args, **kwargs) -> fn:
    """
    Creates a function that receives another function and apply the given
    arguments.

    Examples:
        >>> caller = call(1, 2)
        >>> caller(op.add), caller(op.mul)
        (3, 2)

        This function can be used as a decorator to declare self calling
        functions:

        >>> @call()
        ... def patch_module():
        ...     import builtins
        ...
        ...     builtins.evil = lambda: print('Evil patch')
        ...     return True

        The variable ``patch_module`` will be assigned to the return value of the
        function and the function object itself will be garbage collected.
    """
    return quick_fn(lambda f: f(*args, **kwargs))


def call_over(*args, **kwargs) -> fn:
    """
    Transforms the arguments passed to the result by the functions provided as
    arguments.

    Return a factory function that binds the transformations to its argument

    Examples:
        >>> transformer = call_over(op.add(1), op.mul(2))
        >>> func = transformer(op.add)
        >>> func(1, 2) # (1 + 1) + (2 * 2)
        6
    """
    f_args = tuple(map(extract_function, args))
    f_kwargs = {k: extract_function(v) for k, v in kwargs.items()}
    identity = lambda x: x

    @quick_fn
    def transformed(func):
        @quick_fn
        def wrapped(*args, **kwargs):
            try:
                extra = args[len(f_args) :]
            except IndexError:
                raise TypeError("not enough arguments")
            args = (f(x) for f, x in zip(f_args, args))
            for k, v in kwargs.items():
                kwargs[k] = f_kwargs.get(k, identity)(v)
            return func(*args, *extra, **kwargs)

        return wrapped

    return transformed


@fn.curry(2)
def do(func, x, *args, **kwargs):
    """
    Runs ``func`` on ``x``, returns ``x``.

    Because the results of ``func`` are not returned, only the side
    effects of ``func`` are relevant.

    Logging functions can be made by composing ``do`` with a storage function
    like ``list.append`` or ``file.write``

    Examples:
        >>> log = []
        >>> inc = do(log.append) >> (X + 1)
        >>> [inc(1), inc(11)]
        [2, 12]
        >>> log
        [1, 11]
    """
    func(x, *args, **kwargs)
    return x


#
# Call filtering
#
@fn
def splice(func):
    """
    Return a function that receives variadic arguments and pass them as a tuple
    to func.

    Args:
        func:
            Function that receives a single tuple positional argument.

    Example:
        >>> vsum = splice(sum)
        >>> vsum(1, 2, 3, 4)
        10
    """
    return fn(lambda *args, **kwargs: func(args, **kwargs))


# Can we implement this in a robust way? It seems to be impossible with Python
# unless we accept fragile solutions based on killing threads, multiprocessing
# and signals
#
# @fn.curry(2)
# def timeout(*args, **kwargs):
#     """
#     Limit the function execution time to the given timeout (in seconds).
#
#     Example:
#         >>> fib = lambda n: 1 if n <= 1 else fib(n - 1) + fib(n - 2)
#         >>> timeout(0.25, fib, 10)  # wait at most 0.25 seconds
#         89
#         >>> timeout(0.25, fib, 50)  # stops before the thermal death of the universe
#         Traceback (most recent call last)
#         ...
#         TimeoutError:
#
#     Args:
#         timeout (float, seconds):
#             The maximum duration of function execution
#         func:
#             Function to be executed
#     """
#     from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
#
#     executor = ProcessPoolExecutor
#     timeout, func, *args = args
#     if func in ('thread', 'process'):
#         executor = ThreadPoolExecutor if func == 'thread' else ProcessPoolExecutor
#         func, *args = args
#
#     with executor() as e:
#         future = e.submit(func, *args, **kwargs)
#         return future.result(timeout=timeout)


#
# Argument order
#
@fn
def flip(func):
    """
    Flip the order of arguments in a binary operator.

    The resulting function is always curried.

    Examples:
        >>> rdiv = flip(lambda x, y: x / y)
        >>> rdiv(2, 10)
        5.0
    """
    func = extract_function(func)
    return fn.curry(2, lambda x, y: func(y, x))


@fn
def reversed(func):
    """
    Creates a function that invokes func with the positional arguments order
    reversed.

    Examples:
        >>> mul = reversed(lambda x, y, z: x * y % z)
        >>> mul(10, 2, 8)
        6
    """
    return fn(lambda *args, **kwargs: func(*args[::-1], **kwargs))


@fn.curry(2)
def select_args(idx, func):
    """
    Creates a function that calls func with the arguments reordered.

    Examples:
        >>> double = select_args([0, 0], (X + Y))
        >>> double(21)
        42
    """
    return fn(lambda *args, **kwargs: func(*(args[i] for i in idx), **kwargs))


@fn.curry(2)
def skip_args(n, func):
    """
    Skips the first n positional arguments before calling func.

    Examples:
        >>> incr = skip_args(1, (X + 1))
        >>> incr('whatever', 41)
        42
    """
    return fn(lambda *args, **kwargs: func(*args[n:], **kwargs))


@fn.curry(2)
def keep_args(n, func):
    """
    Uses only the first n positional arguments to call func.

    Examples:
        >>> incr = keep_args(1, (X + 1))
        >>> incr(41, 'whatever')
        42
    """
    func = extract_function(func)
    # if n == 1:
    #     return fn(lambda x, *args, **kwargs: func(x, **kwargs))
    return fn(lambda *args, **kwargs: func(*args[:n], **kwargs))


#
# Error control
#
@fn
def error(exc):
    """
    Raises the given exception.

    If argument is not an exception, raises ValueError(exc).

    Examples:
        >>> error('some error')
        Traceback (most recent call last):
        ...
        ValueError: some error
    """
    if isinstance(exc, Exception):
        raise exc
    elif isinstance(exc, type) and issubclass(exc, Exception):
        raise exc()
    else:
        raise ValueError(exc)


@fn.curry(2)
def ignore_error(exception, func, *, handler=None, raises=None):
    """
    Ignore exception in function. If the exception occurs, it executes the given
    handler.

    Examples:
        >>> nan = always(float('nan'))
        >>> div = ignore_error(ZeroDivisionError, (X / Y), on_error=nan)
        >>> div(1, 0)
        nan

        The function can be used to re-write exceptions by passing the optional
        raises parameter.

        >>> @ignore_error(KeyError, raises=ValueError("invalid name"))
        ... def get_value(name):
        ...     return data[name]
    """

    if isinstance(raises, Exception):
        handler = error.partial(raises)
    elif raises is not None:
        handler = lambda e: error(raises(e))
    return quick_fn(toolz.excepts(exception, func, handler))


@fn.curry(2)
def retry(n: int, func, *, error=Exception, sleep=None):
    """
    Retry to execute function at least n times before raising an error.

    This is useful for functions that may fail due to interaction with external
    resources (e.g., fetch data from the network).

    Args:
        n:
            Maximum number of times to execute function
        func:
            Function that may raise errors.
        error:
            Exception or tuple with suppressed exceptions.
        sleep:
            Interval in which it sleeps between attempts.

    Example:
        >>> queue = [111, 7, None, None]
        >>> process = retry(5, lambda x: queue.pop() * x)
        >>> process(6)
        42
    """

    @fn.wraps(func)
    def safe_func(*args, **kwargs):
        for _ in range(n - 1):
            try:
                return func(*args, **kwargs)
            except error as ex:
                if sleep:
                    time.sleep(sleep)
        return func(*args, **kwargs)

    return safe_func


#
# Misc
#
def force_function(func, name=None) -> Callable:
    """
    Force callable or placeholder expression to be converted into a function
    object.

    If function is anonymous, provide a default function name.
    """

    func = extract_function(func)
    if isinstance(func, types.FunctionType):
        if name is not None and func.__name__ == "<lambda>":
            func.__name__ = name
        return func
    else:

        def f(*args, **kwargs):
            return func(*args, **kwargs)

        if name is not None:
            f.__name__ = name
        else:
            name = getattr(func.__class__, "__name__", "function")
            f.__name__ = getattr(func, "__name__", name)
        return f


@singledispatch
def _fmap(f, x):
    try:
        fmap = x.map
    except AttributeError:
        tname = type(x).__name__
        raise NotImplementedError(f"no map function implemented for {tname}")
    else:
        return fmap(f)


#
# Functor map implementations
#
@fn
def fmap(f, x):
    """
    Register actions to how interpret``f @ x`` if f is a sidekick function.

    Example:
        >>> fmap((X * 2), [1, 2, 3])
        [2, 4, 6]
    """
    return _functor_dispatch(type(x))(f, x)


_functor_dispatch = _fmap.dispatch
fmap.register = lambda cls: _fmap.register(cls)
fmap.dispatch = _fmap.dispatch


@fmap.register(str)
def _(f, st):
    return "".join(map(f, st))


@fmap.register(list)
def _(f, obj):
    return [f(x) for x in obj]


@fmap.register(tuple)
def _(f, obj):
    return tuple(f(x) for x in obj)


@fmap.register(set)
def _(f, obj):
    return {f(x) for x in obj}


@fmap.register(dict)
def _(f, obj):
    return {k: f(v) for k, v in obj.items()}


@fmap.register(Mapping)
def _(f, obj):
    return ((k, f(v)) for k, v in obj.items())


@fmap.register(Iterable)
def _(f, obj):
    return ((k, f(v)) for k, v in obj.items())


#
# Removed functions
#
# toolz.memoize ==> use sk.lru_cache
