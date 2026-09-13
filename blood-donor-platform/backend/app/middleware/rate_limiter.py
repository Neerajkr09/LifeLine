"""
Rate limiting via slowapi (in-memory by default).

NOTE for production: the default in-memory backend only tracks limits within
a single process. If you deploy multiple API instances behind a load
balancer, point slowapi at a shared Redis backend instead
(storage_uri="redis://...") so limits are enforced consistently across
instances.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])
