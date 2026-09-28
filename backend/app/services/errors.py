class NotFoundError(LookupError):
    """Something the use case needs isn't stored yet (e.g. no profile or no active goal)."""
