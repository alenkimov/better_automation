from functools import cache
from typing import Literal
import base64
import json


@cache
def _encode_x_properties(properties: str) -> str:
    return base64.b64encode(properties.encode('utf-8')).decode('utf-8')


def encode_x_properties(properties: dict) -> str:
    return _encode_x_properties(json.dumps(properties, separators=(',', ':')))


@cache
def decode_x_properties(encoded_properties: str) -> dict:
    decoded_bytes = base64.b64decode(encoded_properties.encode('utf-8'))
    return json.loads(decoded_bytes.decode('utf-8'))


def create_guild_x_context_properties(
        location_guild_id: int | str,
        location_channel_id: int | str,
        location_channel_type: int = 0,
        location: Literal["Accept Invite Page", "Join Guild"] = "Accept Invite Page",
) -> str:
    x_context_properties = {
        "location_guild_id": str(location_guild_id),
        "location_channel_id": str(location_channel_id),
        "location_channel_type": location_channel_type,
        "location": location,
    }
    return encode_x_properties(x_context_properties)


def create_x_super_properties(
        user_agent: str,
        client_build_number: int,
        *,
        browser: str = "Chrome",
        browser_version: str = "110.0.0.0",
        os: str = "Windows",
        os_version: str = "10",
        system_locale: str = "en-US",
        # system_locale: str = "ru-RU",
) -> str:
    x_super_properties = {
        'browser': browser,
        'browser_user_agent': user_agent,
        'browser_version': browser_version,
        'client_build_number': client_build_number,
        'client_event_source': None,
        'device': '',
        'os': os,
        'os_version': os_version,
        # 'referrer': 'https://discord.com/',
        # 'referring_domain': 'discord.com',
        'referrer': '',
        'referring_domain': '',
        'referrer_current': '',
        'referring_domain_current': '',
        'release_channel': 'stable',
        'system_locale': system_locale}
    return encode_x_properties(x_super_properties)