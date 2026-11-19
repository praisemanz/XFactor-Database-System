"""Terminal front end — demonstrates every required database feature.

Usage:  python -m xfactor.cli
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from xfactor.db import session_scope
from xfactor.models import LiveShow
from xfactor.repository import reports
from xfactor.repository.crud import ActRepository
from xfactor.repository.reports import ResultTable


def show(table: ResultTable, max_width: int = 32) -> None:
    if not table.rows:
        print("  (no rows)")
        return
    cells = [[("" if v is None else str(v))[:max_width] for v in row] for row in table.rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(table.columns)]
    line = "  ".join(h.ljust(w) for h, w in zip(table.columns, widths))
    print(line)
    print("-" * len(line))
    for row in cells:
        print("  ".join(v.ljust(w) for v, w in zip(row, widths)))
    print(f"({len(cells)} rows)")


def ask(prompt: str, default: str = "") -> str:
    value = input(f"{prompt}{f' [{default}]' if default else ''}: ").strip()
    return value or default


# ----------------------------------------------------------------- CRUD

def crud_create() -> None:
    name = ask("New act name")
    is_group = ask("Is it a group? (y/n)", "n").lower().startswith("y")
    try:
        with session_scope() as s:
            act = ActRepository(s).create(name, is_group)
            print(f"INSERTED act_id={act.act_id} name={act.name!r}")
    except IntegrityError as exc:
        print(f"Rejected by UNIQUE constraint on act.name: {exc.orig}")


def crud_read() -> None:
    term = ask("Search acts by name", "Mix")
    with session_scope() as s:
        acts = ActRepository(s).search(term)
        show(ResultTable(("act_id", "name", "is_group"), tuple((a.act_id, a.name, a.is_group) for a in acts)))


def crud_update() -> None:
    act_id = int(ask("act_id to rename"))
    new_name = ask("New name")
    with session_scope() as s:
        act = ActRepository(s).rename(act_id, new_name)
        print(f"UPDATED -> {act.name!r}" if act else "No act with that id.")


def crud_delete() -> None:
    act_id = int(ask("act_id to delete"))
    if ask(f"Really delete act {act_id} and its performances? (yes/no)", "no") != "yes":
        print("Cancelled.")
        return
    with session_scope() as s:
        print("DELETED." if ActRepository(s).delete(act_id) else "No act with that id.")


# ----------------------------------------------------------------- demos

def demo_constraint() -> None:
    print("Trying: INSERT INTO series (series_number) VALUES (150)  -- violates ck_series_number_range")
    try:
        with session_scope() as s:
            s.execute(text("INSERT INTO series (series_number) VALUES (150)"))
    except (IntegrityError, OperationalError) as exc:
        print(f"Rejected by CHECK constraint: {exc.orig}")
    print("\nTrying: INSERT INTO act (name) VALUES ('Little Mix')  -- duplicate of a UNIQUE column")
    try:
        with session_scope() as s:
            s.execute(text("INSERT INTO act (name, is_group) VALUES ('Little Mix', 1)"))
    except IntegrityError as exc:
        print(f"Rejected by UNIQUE constraint: {exc.orig}")


def demo_index() -> None:
    title = ask("Song title to look up", "Hallelujah")
    with session_scope() as s:
        print("\nIndexes on `song` and `performance`:")
        for table in ("song", "performance"):
            rows = s.execute(text(f"SHOW INDEX FROM {table}")).mappings().all()
            for r in rows:
                print(f"  {table}.{r['Key_name']} ({r['Column_name']})")
        print("\nEXPLAIN SELECT * FROM song WHERE title = :title")
        plan = s.execute(text("EXPLAIN SELECT * FROM song WHERE title = :t"), {"t": title})
        show(reports._table(plan))


def demo_join() -> None:
    mentor = ask("Mentor name", "Cowell")
    with session_scope() as s:
        show(reports.songs_by_mentor(s, mentor))


def demo_view() -> None:
    name = ask(f"View {reports.VIEW_NAMES}", "v_series_summary")
    with session_scope() as s:
        show(reports.read_view(s, name))


def demo_procedure() -> None:
    choice = ask("1) sp_series_leaderboard  2) sp_act_journey  3) sp_record_showdown_result", "1")
    with session_scope() as s:
        if choice == "2":
            show(reports.act_journey(s, ask("Act name", "One Direction")))
        elif choice == "3":
            rows = reports.record_showdown_result(
                s, int(ask("Series", "6")), int(ask("Week", "1")),
                ask("Act (exact name)", "Kandy Rain"), ask("New result", "Eliminated"))
            print(f"Procedure updated {rows} row(s) (OUT parameter p_rows_updated).")
        else:
            show(reports.series_leaderboard(s, int(ask("Series number", "7"))))


def demo_update() -> None:
    print("UPDATE through the ORM: change a live show's theme.")
    series, week = int(ask("Series", "6")), int(ask("Week", "1"))
    theme = ask("New theme", "Musical heroes")
    with session_scope() as s:
        before = s.execute(text(
            "SELECT ls.show_id, ls.theme FROM live_show ls JOIN series s USING (series_id) "
            "WHERE s.series_number=:s AND ls.week_number=:w"), {"s": series, "w": week}).first()
        if before is None:
            print("No such show.")
            return
        show_obj = s.get(LiveShow, before.show_id)
        show_obj.theme = theme
        s.flush()
        print(f"show_id={before.show_id}: theme {before.theme!r} -> {show_obj.theme!r}")


MENU: dict[str, tuple[str, Callable[[], None]]] = {
    "1": ("CRUD  - Create an act", crud_create),
    "2": ("CRUD  - Read / search acts", crud_read),
    "3": ("CRUD  - Update (rename) an act", crud_update),
    "4": ("CRUD  - Delete an act", crud_delete),
    "5": ("CONSTRAINT demo (CHECK + UNIQUE)", demo_constraint),
    "6": ("INDEX demo (SHOW INDEX + EXPLAIN)", demo_index),
    "7": ("JOIN query - songs sung by a mentor's acts", demo_join),
    "8": ("VIEW - read a view", demo_view),
    "9": ("STORED PROCEDURE - call a procedure", demo_procedure),
    "10": ("UPDATE query - change a show's theme", demo_update),
    "11": ("Top 15 most-performed songs", lambda: _with(reports.most_performed_songs)),
}


def _with(fn: Callable) -> None:
    with session_scope() as s:
        show(fn(s))


def main() -> None:
    print("=== The X Factor (UK) database ===")
    while True:
        print()
        for key, (label, _) in MENU.items():
            print(f"{key:>3}) {label}")
        print("  q) Quit")
        choice = input("> ").strip().lower()
        if choice in ("q", "quit", "exit"):
            break
        if choice not in MENU:
            continue
        try:
            MENU[choice][1]()
        except (ValueError, KeyboardInterrupt) as exc:
            print(f"Cancelled: {exc}")


if __name__ == "__main__":
    main()
