def to_invite_code(invite_code_or_url: str) -> str:
    """
    Extracts the Discord invite code from a URL or a direct code.

    :param invite_code_or_url: Invite code or URL.
    :return: Invite code.
    """
    return invite_code_or_url.split('/')[-1]
