from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request, closed when the response is sent."""
    with request.app.state.session_factory() as session:
        yield session


def get_today() -> date:
    """The only place the API reads the clock. Tests override this dependency."""
    return date.today()


SessionDep = Annotated[Session, Depends(get_session)]
TodayDep = Annotated[date, Depends(get_today)]
