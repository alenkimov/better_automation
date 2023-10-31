import asyncio
import email
import socket
import ssl
from collections import defaultdict
from email.message import Message
from typing import Iterable, Callable, Optional

from aioimaplib import IMAP4_SSL, get_running_loop, IMAP4ClientProtocol
from python_socks.async_.asyncio import Proxy


class ProxyIMAPClient(IMAP4_SSL):
    def __init__(self, *args, proxy: str = None, **kwargs):
        self.proxy = proxy
        super().__init__(*args, **kwargs)

    async def __aenter__(self):
        await self.wait_hello_from_server()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.logout()

    async def create_socket_through_proxy(
            self, host, port,
    ) -> socket.socket:
        proxy = Proxy.from_url(self.proxy)
        return await proxy.connect(dest_host=host, dest_port=port)

    def create_client(self, host: str, port: int, loop: asyncio.AbstractEventLoop,
                      conn_lost_cb: Callable[[Optional[Exception]], None] = None,
                      ssl_context: ssl.SSLContext = None):
        local_loop = loop if loop is not None else get_running_loop()

        if ssl_context is None:
            ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        async def create_connection():
            sock = await self.create_socket_through_proxy(host, port)
            await local_loop.create_connection(
                lambda: self.protocol, sock=sock, ssl=ssl_context, server_hostname=host)

        if self.proxy:
            self.protocol = IMAP4ClientProtocol(local_loop, conn_lost_cb)
            local_loop.create_task(create_connection())
        else:
            super().create_client(host, port, local_loop, conn_lost_cb, ssl_context)

    async def get_messages_from_folders(self, folders: Iterable[str]) -> dict[str: list[Message]]:
        messages = defaultdict(list)
        for folder in folders:
            result, data = await self.select(folder)
            if result != 'OK':
                # print(f"Failed to select folder {folder}: {data}")
                continue

            result, data = await self.search("ALL")
            if result == 'OK':
                for number_bytes in data[0].split():
                    number = number_bytes.decode('utf-8')
                    result, data = await self.fetch(number, '(RFC822)')
                    if result == 'OK':
                        messages[folder].append(email.message_from_bytes(data[1]))
            else:
                # print(f"SEARCH command failed in folder {folder}: {data}")
                pass

        return messages
