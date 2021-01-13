import itertools
import operator as op
from collections import deque
from itertools import filterfalse, dropwhile, takewhile, islice

from .iter import Iter, generator
from .lib_basic import uncons
from .. import _toolz
from .._empty import EMPTY as NOT_GIVEN
from ..functions import fn, to_callable
from ..typing import Func, Pred, Seq, Union, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .. import api as sk, Union  # noqa: F401
    from ..api import X, Y  # noqa: F401

_filter = filter
_snd = op.itemgetter(1)


@fn.curry(2)
def filter(pred: Pred, seq: Seq):
    """
    Return an iterator yielding those items of iterable for which function(item)
    is true.

    Behaves similarly to Python's builtin filter, but accepts anything
    convertible to callable using :func:`sidekick.functions.to_callable` as predicate
    and return sidekick iterators instead of regular ones.


    filter(pred, seq) ==> seq[a], seq[b], seq[c], ...

    in which a, b, c, ... are the indexes in which pred(seq[i]) == True.

    Examples:
        >>> sk.filter((X % 2), range(10))
        sk.iter([1, 3, 5, 7, 9])

    See Also:
        :func:`remove`
        :func:`separate`
    """
    pred = to_callable(pred)
    return Iter(_filter(pred, seq))


@fn.curry(2)
def remove(pred: Pred, seq: Seq) -> Iter:
    """
    Opposite of filter. Return those items of sequence for which pred(item)
    is False

    Examples:
        >>> sk.remove((X < 5), range(10))
        sk.iter([5, 6, 7, 8, 9])

    See Also:
        :func:`filter`.
        :func:`separate`
    """
    return Iter(filterfalse(to_callable(pred), seq))


@fn.curry(2)
def separate(pred: Func, seq: Seq, consume: bool = False) -> (Seq, Seq):
    """
    Split sequence it two. The first consists of items that pass the
    predicate and the second of those items that don't.

    Similar to (filter(pred, seq), filter(!pred, seq)), but only evaluate
    the predicate once per item.

    Args:
        pred:
            Predicate function
        seq:
            Iterable of items that should be separated.
        consume:
            If given, fully consume the iterator and return two lists. This is
            faster than separating and then converting each element to a list.

    Examples:
        >>> sk.separate((X % 2), [1, 2, 3, 4, 5])
        (sk.iter([1, 3, 5]), sk.iter([2, 4]))

    See Also:
        :func:`filter`
        :func:`remove`
    """
    pred = to_callable(pred)
    if consume:
        a, b = [], []
        add_a = a.append
        add_b = b.append
        for x in seq:
            if pred(x):
                add_a(x)
            else:
                add_b(x)
        return a, b
    else:
        a, b = itertools.tee((x, pred(x)) for x in seq)
        return (
            Iter(x for x, keep in a if keep),
            Iter(x for x, exclude in b if not exclude),
        )


@fn.curry(2)
def drop(key: Union[Pred, int], seq: Seq) -> Iter:
    """
    Drop items from the start of iterable.

    If key is a number, drop at most this number of items for iterator. If it
    is a predicate, drop items while key(item) is true.

        drop(key, seq) ==> seq[n], seq[n + 1], ...

    n is either equal to key, if its a number or is the index for the first
    item in which key(item) is false.

    Examples:
        >>> sk.drop((X < 5), range(10))
        sk.iter([5, 6, 7, 8, 9])

        >>> sk.drop(3, range(10))
        sk.iter([3, 4, 5, 6, 7, 8, ...])

    See Also:
        :func:`take`
        :func:`rdrop`
        :func:`strip`
    """
    if isinstance(key, int):
        return Iter(islice(seq, key, None))
    else:
        return Iter(dropwhile(to_callable(key), seq))


@fn.curry(2)
@generator
def rdrop(key: Union[Pred, int], seq: Seq) -> Iter:
    """
    Drop items from the end of iterable.

    Examples:
        >>> sk.rdrop(2, [1, 2, 3, 4])
        sk.iter([1, 2])

        >>> sk.rdrop((X >= 2), [1, 2, 4, 1, 2, 4])
        sk.iter([1, 2, 4, 1])

    See Also:
        :func:`drop`
        :func:`rtake`
    """
    seq = iter(seq)

    if isinstance(key, int):
        n: int = key
        out = deque(take(n, seq), n)
        for x in seq:
            yield out[0]
            out.append(x)

    else:
        pending = []
        wait = pending.append
        clear = pending.clear

        for x in seq:
            if key(x):
                wait(x)
            else:
                yield from pending
                yield x
                clear()


@fn.curry(2)
def drop_at(indices: Seq, seq: Seq) -> Seq:
    """
    Drop all elements in the given positions.

    Indices can be a set or a (possibly infinite) **sorted** iterable.

    Examples:
        >>> "".join(drop_at({1, 2, 4, 10}, "foobar"))
        'fbr'

    See Also:
        :func:`drop`
        :func:`take_at`
    """
    if isinstance(indices, set):
        return Iter(x for i, x in enumerate(seq) if i not in indices)
    return Iter(_drop_at_lazy(iter(indices), iter(seq)))


def _drop_at_lazy(indices, seq):
    idx = next(indices, None)
    if idx is None:
        return
    for i, x in enumerate(seq):
        if i == idx:
            try:
                idx = next(indices)
            except StopIteration:
                break
        elif i > idx:
            raise ValueError("non-decreasing sequence of indices")
        else:
            yield x
    yield from seq


@fn.curry(2)
def take(key: Union[Pred, int], seq: Seq) -> Iter:
    """
    Return the first entries iterable.

    If key is a number, return at most this number of items for iterator. If it
    is a predicate, return items while key(item) is true.

        take(key, seq) ==> seq[0], seq[1], ..., seq[n - 1]

    n is either equal to key, if its a number or is the index for the first
    item in which key(item) is false.

    This function is a complement of :func:`drop`. Given two identical iterators
    ``seq1`` and ``seq2``, ``take(key, seq1) + drop(key, seq2)`` yields the
    original sequence of items.

    Examples:
        >>> sk.take((X < 5), range(10))
        sk.iter([0, 1, 2, 3, 4])

    See Also:
        :func:`drop`
    """
    if isinstance(key, int):
        return Iter(islice(seq, key))
    else:
        return Iter(takewhile(to_callable(key), seq))


@fn.curry(2)
@generator
def rtake(key: Union[Pred, int], seq: Seq) -> Iter:
    """
    Return the last entries iterable.

    Examples:
        >>> sk.rtake(2, [1, 2, 3, 4])
        sk.iter([3, 4])

        >>> sk.rtake((X >= 2), [1, 2, 4, 1, 2, 4])
        sk.iter([2, 4])

    See Also:
        :func:`take`
        :func:`rdrop`
    """
    seq = iter(seq)

    if isinstance(key, int):
        yield from deque(seq, key)
    else:
        tail = []
        wait = tail.append
        clear = tail.clear

        for x in seq:
            if key(x):
                wait(x)
            else:
                clear()
        yield from tail


@fn.curry(2)
def take_at(indices: Seq, seq: Seq) -> Seq:
    """
    Return a sequence with values in the positions specified by indices.

    Indices must be any non-decreasing (and possibly infinite) sequence.

    If you want to pass a list of non-ordered indices, use the builtin sorted()
    function before sending to this function. It raises a ValueError if a
    non-decreasing sequence is detected.

    Examples:
        >>> "".join(take_at([0, 1, 1, 1, 4, 5, 10], "foo bar baz"))
        'fooobaz'

    See Also:
        :func:`get`
        :func:`drop_at`
    """
    return Iter(iter(indices), seq)


def _take_at(indices, seq):
    idx = next(indices, None)
    if idx is None:
        return
    for i, x in enumerate(seq):
        if i == idx:
            yield x
            for idx in indices:
                if i == idx:
                    yield x
                else:
                    break
        elif i > idx:
            raise ValueError("non-decreasing sequence of indices")


@fn.curry(2)
def strip(prefix: Seq, seq: Seq, partial=False, cmp=NOT_GIVEN) -> Iter:
    """
    If seq starts with the same elements as in prefix, remove them from
    result.

    Args:
        prefix:
            Prefix sequence to possibly removed from seq.
        seq:
            Sequence of input elements.
        partial:
            If True, remove partial matches with prefix.
        cmp:
            If given, uses as a comparation function between elements of prefix
            and sequence. It removes elements that cmp(x, y) returns True.

    Examples:
        >>> ''.join(strip("ab", "abcd"))
        'cd'
        >>> strip(sk.repeat(3), range(6), partial=True, cmp=(X < Y)))
        sk.iter([3, 4, 5])
    """
    if partial:
        cmp = NOT_GIVEN.resolve(cmp, op.eq)
        return Iter(_strip_partial(iter(prefix), iter(seq), cmp=cmp))
    elif cmp is NOT_GIVEN:
        return Iter(_strip_full(tuple(prefix), iter(seq)))
    else:
        return Iter(_strip_full_cmp(tuple(prefix), iter(seq), cmp))


def _strip_partial(prefix, seq, cmp):
    for x, y in zip(prefix, seq):
        if not cmp(x, y):
            yield y
    yield from seq


def _strip_full(prefix, seq):
    elems = tuple(islice(seq, len(prefix)))
    if elems == prefix:
        yield from seq
    else:
        yield from elems
        yield from seq


def _strip_full_cmp(prefix, seq, cmp):
    elems = tuple(islice(seq, len(prefix)))
    if all(cmp(x, y) for x, y in zip(elems, seq)):
        yield from seq
    else:
        yield from elems
        yield from seq


@fn.curry(1)
@generator
def unique(seq: Seq, *, key: Func = None, exclude: Seq = (), slow=False) -> Iter:
    """
    Returns the given sequence with duplicates removed.

    Preserves order. If key is supplied map distinguishes values by comparing
    their keys.

    Args:
        seq:
            Iterable of objects.
        key:
            Optional key function. It will return only the first value that
            evaluate to a unique key by the key function.
        exclude:
            Optional sequence of keys to exclude from seq
        slow:
            If True, allows the slow path (i.e., store seen elements in a list,
            instead of a hash).

    Examples:
        >>> sk.unique(range(10), key=(X % 5))
        sk.iter([0, 1, 2, 3, 4])

    Note:
        Elements of a sequence or their keys should be hashable, otherwise it
        must use a slow path.

    See Also:
        :func:`dedupe`
    """
    pred = to_callable(key)
    if slow:
        seen = [*exclude] if key is None else [*map(pred, exclude)]
        add = seen.append
    else:
        seen = {*exclude} if key is None else {*map(key, exclude)}
        add = seen.add

    if key is None:
        for x in seq:
            if x not in seen:
                add(x)
                yield x
    else:
        for x in seq:
            test = key(x)
            if test not in seen:
                add(test)
                yield x


@fn.curry(1)
@generator
def dedupe(seq: Seq, *, key: Func = None) -> Iter:
    """
    Remove duplicates of successive elements.

    Args:
        seq:
            Iterable of objects.
        key:
            Optional key function. It will yield successive values if their
            keys are different.

    See Also:
        :func:`unique`
    """
    try:
        x, rest = uncons(seq)
        yield x
    except ValueError:
        return

    if key is None:
        for y in rest:
            if x != y:
                yield y
            x = y
    else:
        key = to_callable(key)
        key_x = key(x)
        for y in rest:
            key_y = key(y)
            if key_x != key_y:
                yield y
            key_x = key_y


@fn.curry(2)
@generator
def converge(pred: Pred, seq: Seq) -> Iter:
    """
    Test convergence with the predicate function by passing the last two items
    of sequence. If pred(penultimate, last) returns True, stop iteration.

    Examples:
        We start with a converging (possibly infinite) sequence and an explicit
        criteria.

        >>> seq = sk.iterate((X / 2), 1.0)
        >>> conv = lambda x, y: abs(x - y) < 0.01

        Run it until convergence

        >>> it = sk.converge(conv, seq); it
        sk.iter([1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125, ...])
        >>> sum(it)
        1.9921875
    """
    seq = iter(seq)
    try:
        x = next(seq)
    except StopIteration:
        return

    yield x
    for y in seq:
        yield y
        if pred(x, y):
            break
        x = y


@fn.curry(2)
def random_sample(prob: float, seq: Seq, *, random_state=None) -> Seq:
    """
    Choose with probability ``prob`` each element of seq to include in the
    output sequence.
    """
    return _toolz.random_sample(prob, seq, random_state=random_state)


@fn.curry(3)
def indexed(transform, func: Callable, seq: Seq, *, start=0) -> Seq:
    """
    Take a function that receives a sequence and a function and transform it
    to operate in a indexed sequence.

    This is mostly useful for functions like filter, take, drop, etc that loose
    indexing information after the transform.

    Examples:
        >>> seq = [5, 10, 2, 3, 25, 42]
        >>> indexed(filter, (X >= 10), seq)
        sk.iter([(1, 10), (4, 25), (5, 42)])
    """
    func = to_callable(func)
    func_ = lambda x: func(_snd(x))
    return transform(func_, enumerate(seq, start))
