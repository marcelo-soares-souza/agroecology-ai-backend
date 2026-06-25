from typing import Any, cast

from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.adapters.rest.server import app as fastapi_app
from src.shared.config import TRUSTED_PROXY_HOSTS
from src.shared.logging_utils import configure_logging

configure_logging()
app = ProxyHeadersMiddleware(cast(Any, fastapi_app), trusted_hosts=TRUSTED_PROXY_HOSTS)
