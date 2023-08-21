import re
from pathlib import Path

from .utils import load_lines


# PROTOCOLS = ["http", "https", "SOP2", "SOP3", "socks4", "socks5"]
PROXY_FORMATS_REGEXP = [
    re.compile(r'^(?:(?P<type>.+)://)?(?P<login>[^:]+):(?P<password>[^@|:]+)[@|:](?P<ip>[^:]+):(?P<port>\d+)$'),
    re.compile(r'^(?:(?P<type>.+)://)?(?P<ip>[^:]+):(?P<port>\d+)[@|:](?P<login>[^:]+):(?P<password>[^:]+)$'),
    re.compile(r'^(?:(?P<type>.+)://)?(?P<ip>[^:]+):(?P<port>\d+)$'),
]


class Proxy:
    def __init__(
            self,
            ip: str,
            port: int,
            *,
            protocol: str = None,
            login: str = None,
            password: str = None,
    ):
        self.protocol = protocol or "http"
        self.ip = ip
        self.port = port
        self.login = login
        self.password = password

    @classmethod
    def from_str(cls, proxy: str) -> "Proxy":
        for pattern in PROXY_FORMATS_REGEXP:
            match = pattern.match(proxy)
            if match:
                return cls(
                    ip=match.group('ip'),
                    port=int(match.group('port')),
                    protocol=match.group('type'),
                    login=match.group('login'),
                    password=match.group('password'),
                )

        raise ValueError(f'Unsupported proxy format: {proxy}')

    @classmethod
    def from_file(cls, filepath: Path | str) -> list["Proxy"]:
        return [cls.from_str(proxy) for proxy in load_lines(filepath)]

    @property
    def as_url(self) -> str:
        return (f"{self.protocol}://"
                + (f"{self.login}:{self.password}@" if self.login and self.password else "")
                + f"{self.ip}:{self.port}")

    def __repr__(self):
        return f"Proxy(ip={self.ip}, port={self.port})"

    def __str__(self) -> str:
        return f"[{self.ip:>15}:{str(self.port):<5}]"

    def __hash__(self):
        return hash((self.ip, self.port, self.protocol, self.login, self.password))

    def __eq__(self, other):
        if isinstance(other, Proxy):
            return (
                self.ip == other.ip
                and self.port == other.port
                and self.protocol == other.protocol
                and self.login == other.login
                and self.password == other.password
            )
        return False
