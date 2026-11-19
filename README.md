# The X Factor (UK) Database

CMSC 4323 Database Systems final project. A normalised MySQL database of **The X Factor (UK)**
(15 series, 2004–2018), scraped from Wikipedia and accessed through the **SQLAlchemy ORM**.
It has a terminal app, a Flask web GUI with full CRUD, and a natural-language "Ask" page powered by Claude.

- **Source wiki:** [The X Factor (British TV series)](https://en.wikipedia.org/wiki/The_X_Factor_(British_TV_series)),
  its 15 series articles and the discography article.
- **Size:** 16 tables, **5,075 rows** (1,494 performances, 1,028 songs, 810 releases, 446 episodes, ...).

## Requirement checklist

| Requirement | Where |
|---|---|
| 12+ table normalised model (ERD) | 16 tables. [docs/erd.drawio](docs/erd.drawio) (draw.io) and [docs/erd.md](docs/erd.md) (Mermaid) |
| ORM-created tables | [xfactor/models/](xfactor/models/). `Base.metadata.create_all()` in [xfactor/sql/apply.py](xfactor/sql/apply.py) |
| CHECK constraint | `ck_series_number_range`, `ck_final_position_positive`, `ck_viewers_non_negative`, `ck_uk_peak_range`, `ck_week_number_range`, ... |
| UNIQUE constraint | `act.name`, `uq_series_act (series_id, act_id)`, `uq_mentorship_series_category`, `uq_live_show_week`, ... |
| INDEX | `ix_song_title`, `ix_performance_song`, `ix_performance_entry`, `ix_episode_air_date`, `ix_series_act_position` |
| Populated, 3+ rows per table | [xfactor/loader.py](xfactor/loader.py). Smallest table (`category`) has 9 rows |
| CRUD | [xfactor/repository/crud.py](xfactor/repository/crud.py): `ActRepository` (CLI) and `TableRepository` (GUI, all 16 tables) |
| Multi-join query | `songs_by_mentor()` in [xfactor/repository/reports.py](xfactor/repository/reports.py) (8-table ORM join) |
| VIEW access | `v_series_summary`, `v_performance_detail`, `v_mentor_stats` ([views.sql](xfactor/sql/views.sql)), reflected via the ORM |
| STORED PROCEDURE access | `sp_series_leaderboard`, `sp_act_journey`, `sp_record_showdown_result` (with OUT param) ([procedures.sql](xfactor/sql/procedures.sql)) |
| Terminal interface (group of 1) | `python -m xfactor.cli` |
| EC 7a: GUI with CRUD | `python -m xfactor.web` |
| EC 7b: LLM natural-language queries | `/ask` page: [xfactor/nlq/](xfactor/nlq/) |
| EC 7c: Published online | Render + Aiven: see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| EC 7d: 2,000+ rows of real data | 5,075 rows scraped from Wikipedia: [xfactor/scraper/](xfactor/scraper/) |

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then edit DB_* to point at your MySQL server
python -m xfactor.loader          # creates DB, tables, views, procedures, loads data
python -m xfactor.cli             # terminal app
python -m xfactor.web             # GUI at http://127.0.0.1:5050
pytest                            # 96 tests (integration tests need MySQL)
```

The database user in `.env` needs `CREATE` rights on the `xfactor` and `xfactor_test` databases
(see [docs/MYSQL_SETUP.md](docs/MYSQL_SETUP.md)). Use `python -m xfactor.loader --reset` to rebuild from scratch.

### Rebuilding the dataset from Wikipedia

```bash
python -m xfactor.scraper.pipeline --fetch   # re-download pages into data/raw/, re-parse
python -m xfactor.loader --reset
```

`data/parsed/xfactor.json` is committed, so loading needs no network access.

## Architecture

```
Wikipedia HTML ──► scraper/ (parse → frozen dataclass records) ──► data/parsed/xfactor.json
                                                                        │
                                       loader.py (ORM, get-or-create) ◄─┘
                                                │
                                        MySQL 8 (16 tables + 3 views + 3 procedures)
                                                │
                   repository/ (CRUD, joins, views, procedures) ◄── cli.py / web/ / nlq/
```

| Package | Responsibility |
|---|---|
| `xfactor/scraper/` | Fetch and parse Wikipedia tables (rowspans, footnotes, renamed acts, multi-song weeks) |
| `xfactor/models/` | SQLAlchemy models: competition (series, people, mentors), acts, shows (performances, songs, episodes, releases) |
| `xfactor/sql/` | Views and stored procedures, and the script that applies them |
| `xfactor/repository/` | All database access used by the interfaces |
| `xfactor/nlq/` | Question → SQL (Claude) → SQL guard → read-only execution → answer from rows |
| `xfactor/web/` | Flask GUI: generic CRUD for every table, views, procedures, join report, Ask page |

### How the "Ask" page stays grounded and safe

1. Claude (`claude-opus-5-5`) receives the schema (generated from the ORM) and returns a single `SELECT` as structured JSON.
2. [sql_guard.py](xfactor/nlq/sql_guard.py) rejects anything but one read-only SELECT (no DML/DDL, `INTO OUTFILE`, `SLEEP`, system schemas, comments, stacked statements) and adds `LIMIT 200` plus a 5-second execution cap.
3. The query runs as a **SELECT-only MySQL user** inside `START TRANSACTION READ ONLY`, then rolls back.
4. Claude writes the answer **only from the returned rows**. The generated SQL and raw results are shown so the answer can be checked.

Server-side refusal fallback (`fallbacks: "default"`) is enabled on both Claude calls.

## Data notes and limitations

- Covers the **live-show finalists** of each series. Audition and bootcamp contestants are not included.
- `song.artist_id` is filled only where Wikipedia names the artist (theme columns such as "Musical Hero" and duet partners), so many songs have no artist.
- Mentors written as surnames in the source ("Cole", "Fernandez-Versini") are resolved to one canonical person ("Cheryl"). Rhythmix is merged into Little Mix.
- Data is © Wikipedia contributors, CC BY-SA 4.0.
