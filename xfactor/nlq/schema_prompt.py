"""Describe the database to the LLM. Generated from the ORM so it never drifts from the schema."""
from __future__ import annotations

from functools import lru_cache

from xfactor.models import Base

VIEW_DOCS = """\
VIEW v_series_summary(series_number, year, num_episodes, avg_viewers_millions, winner,
     winner_category, winning_mentor, runner_up, num_finalists)
VIEW v_performance_detail(performance_id, series_number, week_number, stage, theme, act, category,
     mentor, running_order, song, song_artist, duet_partner, is_showdown, result_text, final_position)
VIEW v_mentor_stats(mentor, series_mentored, finalists_mentored, winners, avg_final_position)"""

DOMAIN_NOTES = """\
Domain notes:
- The X Factor (UK) ran 15 series (2004-2018). series.series_number is 1..15; series_id is a surrogate key.
- series_act is one act's run in one series. final_position 1 = winner, 2 = runner-up, etc.
- Each act belongs to a category (e.g. Boys, Girls, Groups, Over 25s) mentored by one judge: series_act.mentorship_id -> mentorship(category_id, mentor_id -> person).
- person holds judges, presenters and judges'-houses assistants. Judges are linked by series_judge, presenters by series_presenter.
- live_show is one week of live shows (stage = 'Week 3', 'Quarter-Final', 'Semi-Final', 'Final').
- performance is one song sung by one act in one live show; is_showdown = 1 for sing-off songs.
- song.artist_id is the original/theme artist when known (often NULL). Use LIKE for name matching.
- episode holds every broadcast episode with official viewing figures (viewers_millions).
- music_release holds singles and albums released by former contestants; uk_peak is the UK chart peak.
- Prefer the views when they answer the question directly."""


@lru_cache(maxsize=1)
def schema_description() -> str:
    lines = []
    for table in Base.metadata.sorted_tables:
        cols = []
        for col in table.columns:
            note = " PK" if col.primary_key else ""
            fk = next(iter(col.foreign_keys), None)
            if fk:
                note += f" -> {fk.column.table.name}.{fk.column.name}"
            cols.append(f"{col.name} {col.type}{note}")
        lines.append(f"TABLE {table.name}(" + ", ".join(cols) + ")")
    return "\n".join(lines) + "\n" + VIEW_DOCS + "\n\n" + DOMAIN_NOTES
