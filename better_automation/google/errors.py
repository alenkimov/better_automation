class GoogleError(Exception):
    pass


class FailedToLogin(GoogleError):
    """Исключение, вызываемое если не получилось залогиниться по неизвестной причине."""
    pass


class CaptchaRequired(FailedToLogin):
    """Исключение, вызываемое если не получилось залогиниться из-за reCAPTCHA."""
    pass


class RecoveryRequired(FailedToLogin):
    """
    Исключение, вызываемое если не получилось залогиниться из-за того, что требуется восстановление аккаунта.

    Google: We noticed unusual activity in your Google Account.
        To keep your account safe, you were signed out.
        To continue, you’ll need to verify it’s you
    """
    pass


class RecoveryEmailRequired(FailedToLogin):
    """
    Исключение, вызываемое если не получилось залогиниться из-за того, что требуется recovery_email.
    """
    pass


class FailedToOAuth2(GoogleError):
    """Исключение, вызываемое если не получилось авторизоваться через OAuth2 по неизвестной причине."""
    pass


class PhoneVerificationRequired(FailedToLogin):
    """
    Исключение, вызываемое если не получилось залогиниться из-за того, что требуется SMS верификация.
    """
    pass
