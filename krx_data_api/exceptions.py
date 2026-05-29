class KRXError(Exception):
    pass


class KRXAuthError(KRXError):
    pass


class KRXFetchError(KRXError):
    pass


class KRXAuthRequiredError(KRXError):
    """KRX가 OTP 발급을 거부했고 (응답='LOGOUT'), 로그인된 세션이 필요함."""

    pass


class UnknownEndpointError(KRXError):
    pass
