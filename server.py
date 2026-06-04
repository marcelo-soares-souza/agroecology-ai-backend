from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.adapters.rest.server import app as fastapi_app
from src.shared.logging_utils import configure_logging

configure_logging()
app = ProxyHeadersMiddleware(fastapi_app, trusted_hosts="*")

__all__ = ["app"]
