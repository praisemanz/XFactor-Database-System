"""Generic CRUD pages for every table: list/search, create, edit, delete."""
from __future__ import annotations

import hmac
from typing import Any

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import String, inspect, select
from sqlalchemy.exc import IntegrityError, OperationalError

from xfactor.db import session_scope
from xfactor.repository.crud import MODELS, TableRepository
from xfactor.web import can_edit

bp = Blueprint("tables", __name__)
FK_DROPDOWN_LIMIT = 300


def _pk_from_path(repo: TableRepository, raw: str) -> tuple:
    parts = raw.split(",")
    if len(parts) != len(repo.pk_names()):
        abort(404)
    try:
        return tuple(int(p) if p.lstrip("-").isdigit() else p for p in parts)
    except ValueError:
        abort(404)


def _pk_of(repo: TableRepository, obj: Any) -> str:
    return ",".join(str(getattr(obj, name)) for name in repo.pk_names())


def _label_column(table: str):
    mapper = inspect(MODELS[table])
    return next((c for c in mapper.columns if isinstance(c.type, String)), None)


def _fk_options(db, repo: TableRepository) -> dict[str, list[tuple[Any, str]]]:
    """For small referenced tables, offer a dropdown of (id, label)."""
    options: dict[str, list[tuple[Any, str]]] = {}
    for col in repo.columns():
        if not col.foreign_table:
            continue
        model = MODELS[col.foreign_table]
        pk = inspect(model).primary_key[0]
        label = _label_column(col.foreign_table)
        stmt = select(pk, label if label is not None else pk).order_by(label if label is not None else pk)
        rows = db.execute(stmt.limit(FK_DROPDOWN_LIMIT + 1)).all()
        if len(rows) <= FK_DROPDOWN_LIMIT:
            options[col.name] = [(r[0], f"{r[1]} (#{r[0]})") for r in rows]
    return options


def _require_editor() -> None:
    if not can_edit():
        flash("Log in as editor to change data.", "error")
        abort(redirect(url_for("tables.login", next=request.path)))


@bp.route("/tables/<table>")
def list_rows(table: str):
    if table not in MODELS:
        abort(404)
    search = request.args.get("q", "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)
    with session_scope() as db:
        repo = TableRepository(db, table)
        rows, total = repo.list(search=search, page=page, per_page=50)
        columns = repo.columns()
        data = [(_pk_of(repo, r), [getattr(r, c.name) for c in columns]) for r in rows]
    return render_template("table_list.html", table=table, columns=columns, rows=data,
                           total=total, page=page, pages=max((total + 49) // 50, 1), search=search)


@bp.route("/tables/<table>/new", methods=["GET", "POST"])
def create_row(table: str):
    if table not in MODELS:
        abort(404)
    _require_editor()
    if request.method == "POST":
        try:
            with session_scope() as db:
                obj = TableRepository(db, table).create(request.form.to_dict())
                pk = _pk_of(TableRepository(db, table), obj)
            flash(f"Created {table} #{pk}.", "ok")
            return redirect(url_for("tables.list_rows", table=table))
        except (ValueError, IntegrityError, OperationalError) as exc:
            flash(_friendly(exc), "error")
    return _form(table, None, request.form.to_dict() if request.method == "POST" else {})


@bp.route("/tables/<table>/<pk>/edit", methods=["GET", "POST"])
def edit_row(table: str, pk: str):
    if table not in MODELS:
        abort(404)
    _require_editor()
    if request.method == "POST":
        try:
            with session_scope() as db:
                repo = TableRepository(db, table)
                if repo.update(_pk_from_path(repo, pk), request.form.to_dict()) is None:
                    abort(404)
            flash(f"Updated {table} #{pk}.", "ok")
            return redirect(url_for("tables.list_rows", table=table))
        except (ValueError, IntegrityError, OperationalError) as exc:
            flash(_friendly(exc), "error")
            return _form(table, pk, request.form.to_dict())
    with session_scope() as db:
        repo = TableRepository(db, table)
        obj = repo.get(_pk_from_path(repo, pk))
        if obj is None:
            abort(404)
        values = {c.name: getattr(obj, c.name) for c in repo.columns()}
    return _form(table, pk, values)


@bp.route("/tables/<table>/<pk>/delete", methods=["POST"])
def delete_row(table: str, pk: str):
    if table not in MODELS:
        abort(404)
    _require_editor()
    try:
        with session_scope() as db:
            repo = TableRepository(db, table)
            deleted = repo.delete(_pk_from_path(repo, pk))
        flash(f"Deleted {table} #{pk}." if deleted else "Row not found.", "ok" if deleted else "error")
    except (IntegrityError, OperationalError) as exc:
        flash(_friendly(exc), "error")
    return redirect(url_for("tables.list_rows", table=table))


@bp.route("/login", methods=["GET", "POST"])
def login():
    expected = current_app.config.get("EDIT_PASSWORD")
    if request.method == "POST":
        if expected and hmac.compare_digest(request.form.get("password", ""), expected):
            session["editor"] = True
            flash("Logged in as editor.", "ok")
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/") and not target.startswith("//") else "/")
        flash("Wrong password.", "error")
    return render_template("login.html")


def _form(table: str, pk: str | None, values: dict):
    with session_scope() as db:
        repo = TableRepository(db, table)
        columns = repo.columns()
        fk_options = _fk_options(db, repo)
    return render_template("table_form.html", table=table, pk=pk, columns=columns,
                           values=values, fk_options=fk_options)


def _friendly(exc: Exception) -> str:
    if isinstance(exc, ValueError):
        return f"Invalid input: {exc}"
    message = str(getattr(exc, "orig", exc))
    if "Duplicate entry" in message:
        return f"Rejected by a UNIQUE constraint: {message}"
    if "Check constraint" in message:
        return f"Rejected by a CHECK constraint: {message}"
    if "foreign key constraint" in message.lower():
        return f"Rejected by a FOREIGN KEY constraint: {message}"
    return f"Database error: {message}"
