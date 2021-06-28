from .deferred import Proxy, deferred
from .zombie import zombie, ZombieTypes as _ZombieTypes
from .imports import import_later

__all__ = ["Proxy", "deferred", "zombie", "touch", "import_later"]
__version__ = "0.1.0"


def touch(obj):
    """
    Return a non-proxy and non-zombiefied version of object. Regular objects are
    returned as-is.
    """
    if isinstance(obj, _ZombieTypes):
        obj._Zombie__awake()
        return obj
    elif isinstance(obj, Proxy):
        return obj._proxy_obj_
    return obj
