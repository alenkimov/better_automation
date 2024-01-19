class GoogleError(Exception):
    pass


class CaptchaRequired(GoogleError):
    """ Исключение, вызываемое при обнаружении reCAPTCHA. """
    pass
