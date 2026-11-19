"""Compatibility aliases for running the 2018 pywb source on Python 3.11."""

import collections
import collections.abc
import inspect
import yaml


for _name in (
    "AsyncIterable",
    "AsyncIterator",
    "Awaitable",
    "ByteString",
    "Callable",
    "Collection",
    "Container",
    "Coroutine",
    "Generator",
    "Hashable",
    "ItemsView",
    "Iterable",
    "Iterator",
    "KeysView",
    "Mapping",
    "MappingView",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "Reversible",
    "Sequence",
    "Set",
    "Sized",
    "ValuesView",
):
    if not hasattr(collections, _name):
        setattr(collections, _name, getattr(collections.abc, _name))

if not hasattr(inspect, "getargspec"):
    inspect.getargspec = inspect.getfullargspec


# pywb's historical loader predates PyYAML 6's required Loader argument.
_yaml_load = yaml.load


def _compat_yaml_load(stream, Loader=None):
    return _yaml_load(stream, Loader=Loader or yaml.SafeLoader)


yaml.load = _compat_yaml_load
