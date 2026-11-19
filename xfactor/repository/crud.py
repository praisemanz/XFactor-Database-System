"""CRUD operations through the ORM.

`ActRepository` is the hand-written example used in the terminal demo.
`TableRepository` is a generic version, driven by model metadata, used by the web GUI
so every table gets create/read/update/delete without per-table code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, Integer, Numeric, SmallInteger, String, func, inspect, or_, select
from sqlalchemy.orm import Session

from xfactor import models as m

MODELS: dict[str, type[m.Base]] = {
    model.__tablename__: model for model in (
        m.Series, m.Person, m.SeriesJudge, m.SeriesPresenter, m.Category, m.Mentorship,
        m.MentorshipAssistant, m.Hometown, m.Act, m.SeriesAct, m.Artist, m.Song, m.LiveShow,
        m.Performance, m.Episode, m.Release,
    )
}


class ActRepository:
    """Create / read / update / delete for the `act` table."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, name: str, is_group: bool = False) -> m.Act:
        act = m.Act(name=name, is_group=is_group)
        self.session.add(act)
        self.session.flush()  # assigns act_id; raises IntegrityError on duplicate name
        return act

    def get(self, act_id: int) -> m.Act | None:
        return self.session.get(m.Act, act_id)

    def search(self, text: str, limit: int = 25) -> list[m.Act]:
        stmt = select(m.Act).where(m.Act.name.like(f"%{text}%")).order_by(m.Act.name).limit(limit)
        return list(self.session.scalars(stmt))

    def rename(self, act_id: int, new_name: str) -> m.Act | None:
        act = self.get(act_id)
        if act is not None:
            act.name = new_name  # the ORM issues: UPDATE act SET name=... WHERE act_id=...
            self.session.flush()
        return act

    def delete(self, act_id: int) -> bool:
        act = self.get(act_id)
        if act is None:
            return False
        self.session.delete(act)  # cascades to series_act -> performance, and to releases
        self.session.flush()
        return True


@dataclass(frozen=True)
class ColumnInfo:
    name: str
    kind: str            # "int" | "float" | "bool" | "date" | "text" | "choice"
    primary_key: bool
    autoincrement: bool
    nullable: bool
    foreign_table: str | None
    choices: tuple[str, ...] = ()


class TableRepository:
    """Generic CRUD for any table in MODELS, keyed by its (possibly composite) primary key."""

    def __init__(self, session: Session, table: str) -> None:
        if table not in MODELS:
            raise KeyError(f"unknown table {table!r}")
        self.session = session
        self.model = MODELS[table]
        self.mapper = inspect(self.model)

    def columns(self) -> list[ColumnInfo]:
        out = []
        for col in self.mapper.columns:
            fk = next(iter(col.foreign_keys), None)
            choices = tuple(getattr(col.type, "enums", ()) or ())
            out.append(ColumnInfo(
                name=col.key, kind="choice" if choices else _kind(col.type),
                primary_key=col.primary_key,
                autoincrement=col.primary_key and col.autoincrement is True and len(self.mapper.primary_key) == 1,
                nullable=col.nullable, foreign_table=fk.column.table.name if fk else None, choices=choices,
            ))
        return out

    def pk_names(self) -> list[str]:
        return [c.key for c in self.mapper.primary_key]

    def list(self, search: str = "", page: int = 1, per_page: int = 50) -> tuple[list[Any], int]:
        stmt = select(self.model)
        text_cols = [c for c in self.mapper.columns if isinstance(c.type, String)]
        if search and text_cols:
            stmt = stmt.where(or_(*(c.like(f"%{search}%") for c in text_cols)))
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        stmt = stmt.order_by(*self.mapper.primary_key).offset((page - 1) * per_page).limit(per_page)
        return list(self.session.scalars(stmt)), total

    def get(self, pk: tuple) -> Any | None:
        return self.session.get(self.model, pk if len(pk) > 1 else pk[0])

    def create(self, values: dict[str, str]) -> Any:
        obj = self.model(**self._coerce(values, creating=True))
        self.session.add(obj)
        self.session.flush()
        return obj

    def update(self, pk: tuple, values: dict[str, str]) -> Any | None:
        obj = self.get(pk)
        if obj is None:
            return None
        for key, value in self._coerce(values, creating=False).items():
            setattr(obj, key, value)
        self.session.flush()
        return obj

    def delete(self, pk: tuple) -> bool:
        obj = self.get(pk)
        if obj is None:
            return False
        self.session.delete(obj)
        self.session.flush()
        return True

    def _coerce(self, values: dict[str, str], creating: bool) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for info in self.columns():
            if info.autoincrement or (info.primary_key and not creating):
                continue
            if info.kind == "bool":
                out[info.name] = values.get(info.name) in ("on", "true", "1", "True")
                continue
            if info.name not in values:
                continue
            out[info.name] = _convert(values[info.name], info)
        return out


def _kind(col_type: Any) -> str:
    if isinstance(col_type, Boolean):
        return "bool"
    if isinstance(col_type, (Integer, SmallInteger)):
        return "int"
    if isinstance(col_type, Numeric):
        return "float"
    if isinstance(col_type, Date):
        return "date"
    return "text"


def _convert(raw: str | None, info: ColumnInfo) -> Any:
    text = (raw or "").strip()
    if text == "":
        if info.nullable:
            return None
        raise ValueError(f"{info.name} is required")
    try:
        if info.kind == "int":
            return int(text)
        if info.kind == "float":
            return Decimal(text)
        if info.kind == "date":
            return date.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{info.name}: {exc}") from exc
    if info.choices and text not in info.choices:
        raise ValueError(f"{info.name} must be one of {', '.join(info.choices)}")
    return text
