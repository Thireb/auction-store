from .base import *  # noqa: F403

DEBUG = False

# PetHost ends HTTPS at its proxy and forwards plain HTTP to the container.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0)  # noqa: F405
SECURE_CONTENT_TYPE_NOSNIFF = True
