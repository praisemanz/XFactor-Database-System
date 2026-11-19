from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every ORM model."""

    def __repr__(self) -> str:
        pk = ", ".join(f"{c.name}={getattr(self, c.key, None)!r}" for c in self.__table__.primary_key)
        return f"<{type(self).__name__} {pk}>"
