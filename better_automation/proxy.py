import re
from pathlib import Path
from typing import Iterable

from .utils import load_lines


# PROTOCOLS = ["http", "https", "SOP2", "SOP3", "socks4", "socks5"]
PROXY_FORMATS_REGEXP = [
    re.compile(r'^(?:(?P<type>.+)://)?(?P<login>[^:]+):(?P<password>[^@|:]+)[@|:](?P<ip>[^:]+):(?P<port>\d+)$'),
    re.compile(r'^(?:(?P<type>.+)://)?(?P<ip>[^:]+):(?P<port>\d+)[@|:](?P<login>[^:]+):(?P<password>[^:]+)$'),
    re.compile(r'^(?:(?P<type>.+)://)?(?P<ip>[^:]+):(?P<port>\d+)$'),
]


class Proxy:
    """
    A class to represent a proxy connection.

    Attributes
    ----------
    ip : str
        IP address of the proxy server
    port : int
        Port to use for the proxy server
    protocol : str, optional
        Protocol to use for the proxy connection, by default "http"
    login : str, optional
        Login for the proxy server, by default None
    password : str, optional
        Password for the proxy server, by default None
    """

    def __init__(
            self,
            ip: str,
            port: int,
            *,
            tags: Iterable[str] = None,
            protocol: str = None,
            login: str = None,
            password: str = None,
    ):
        self.protocol = protocol or "http"
        self.ip = ip
        self.port = port
        self.login = login
        self.password = password
        self.tags = set(tags) if tags else set()

    @classmethod
    def from_str(cls, proxy: str, *, tags: Iterable[str] = None) -> "Proxy":
        """
        Class method to create a Proxy object from a string.

        The string can be in one of the following formats:
        - '(type://)?ip:port[:@|]login:password'
        - '(type://)?login:password[:@|]ip:port'

        Parameters
        ----------
            proxy : str
                Proxy connection string in one of the above formats.

        Returns
        -------
            Proxy
                A Proxy object.

        Examples
        --------
        >>> proxy = Proxy.from_str('192.168.1.1:8080')
        >>> print(proxy)
        http://192.168.1.1:8080

        >>> proxy = Proxy.from_str('https://user:pass@192.168.1.1:8080')
        >>> print(proxy)
        https://192.168.1.1:8080@user:pass
        """
        for pattern in PROXY_FORMATS_REGEXP:
            match = pattern.match(proxy)
            if match:
                return cls(
                    ip=match.group('ip'),
                    port=int(match.group('port')),
                    protocol=match.group('type'),
                    login=match.group('login'),
                    password=match.group('password'),
                    tags=tags,
                )

        raise ValueError(f'Unsupported proxy format: {proxy}')

    @classmethod
    def from_file(cls, filepath: Path | str) -> set["Proxy"]:
        return {cls.from_str(proxy) for proxy in load_lines(filepath)}

    @property
    def as_url(self) -> str:
        return (f"{self.protocol}://"
                + (f"{self.login}:{self.password}@" if self.login and self.password else "")
                + f"{self.ip}:{self.port}")

    def __repr__(self):
        return f"Proxy(ip={self.ip}, port={self.port})"

    def __str__(self) -> str:
        info = f"[{self.ip:>15}:{str(self.port):<5}]"
        if self.tags: info += f" ({', '.join((str(tag) for tag in self.tags))})"
        return info

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
