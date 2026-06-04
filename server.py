from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from src.adapters.rest.server import app as fastapi_app

app = ProxyHeadersMiddleware(fastapi_app, trusted_hosts="*")

__all__ = ["app"]
