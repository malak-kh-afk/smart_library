"""Custom exceptions: every rejected operation raises one of these with a clear message."""


class LibraryError(Exception):
    """Base class for all errors raised by the application."""


class ValidationError(LibraryError):
    """The data supplied by the user is invalid (empty, wrong format, ...)."""


class NotFoundError(LibraryError):
    """A book / member / loan / reservation / penalty does not exist."""


class BusinessRuleError(LibraryError):
    """The operation is well-formed but violates a library rule."""
