class NotFoundError(LookupError):
    """Something the use case needs isn't stored yet (e.g. no profile or no active goal)."""


class ConflictError(RuntimeError):
    """The operation would overwrite data the user has entered."""
