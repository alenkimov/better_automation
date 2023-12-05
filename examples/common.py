import sys, asyncio

PROXY = None  # "http://login:password@host:port"


# Подробнее об этом: https://curl-cffi.readthedocs.io/en/latest/faq/#not-working-on-windows-notimplementederror
def set_windows_event_loop_policy():
    if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
