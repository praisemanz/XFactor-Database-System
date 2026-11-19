-- Views for the X Factor UK database.
-- Statements are separated by lines containing only "-- @@" (see xfactor/sql/apply.py).

-- One row per series: winner, runner-up, the winning mentor and viewing figures.
CREATE OR REPLACE VIEW v_series_summary AS
SELECT
    s.series_number,
    YEAR(s.start_date)              AS year,
    s.num_episodes,
    s.avg_viewers_millions,
    win_act.name                    AS winner,
    win_cat.name                    AS winner_category,
    win_mentor.full_name            AS winning_mentor,
    ru_act.name                     AS runner_up,
    (SELECT COUNT(*) FROM series_act sa WHERE sa.series_id = s.series_id) AS num_finalists
FROM series s
LEFT JOIN series_act win      ON win.series_id = s.series_id AND win.final_position = 1
LEFT JOIN act win_act         ON win_act.act_id = win.act_id
LEFT JOIN mentorship win_m    ON win_m.mentorship_id = win.mentorship_id
LEFT JOIN category win_cat    ON win_cat.category_id = win_m.category_id
LEFT JOIN person win_mentor   ON win_mentor.person_id = win_m.mentor_id
LEFT JOIN series_act ru       ON ru.series_id = s.series_id AND ru.final_position = 2
LEFT JOIN act ru_act          ON ru_act.act_id = ru.act_id;
-- @@

-- Every live performance with its full context, flattened for reporting.
CREATE OR REPLACE VIEW v_performance_detail AS
SELECT
    p.performance_id,
    s.series_number,
    ls.week_number,
    ls.stage,
    ls.theme,
    a.name                AS act,
    c.name                AS category,
    mentor.full_name      AS mentor,
    p.running_order,
    so.title              AS song,
    orig.name             AS song_artist,
    partner.name          AS duet_partner,
    p.is_showdown,
    p.result_text,
    sa.final_position
FROM performance p
JOIN live_show ls        ON ls.show_id = p.show_id
JOIN series s            ON s.series_id = ls.series_id
JOIN series_act sa       ON sa.entry_id = p.entry_id
JOIN act a               ON a.act_id = sa.act_id
JOIN song so             ON so.song_id = p.song_id
LEFT JOIN artist orig    ON orig.artist_id = so.artist_id
LEFT JOIN artist partner ON partner.artist_id = p.duet_partner_id
LEFT JOIN mentorship m   ON m.mentorship_id = sa.mentorship_id
LEFT JOIN category c     ON c.category_id = m.category_id
LEFT JOIN person mentor  ON mentor.person_id = m.mentor_id;
-- @@

-- Mentor league table: how each judge's acts did overall.
CREATE OR REPLACE VIEW v_mentor_stats AS
SELECT
    p.full_name                                        AS mentor,
    COUNT(DISTINCT m.series_id)                        AS series_mentored,
    COUNT(sa.entry_id)                                 AS finalists_mentored,
    SUM(sa.final_position = 1)                         AS winners,
    ROUND(AVG(sa.final_position), 2)                   AS avg_final_position
FROM person p
JOIN mentorship m  ON m.mentor_id = p.person_id
JOIN series_act sa ON sa.mentorship_id = m.mentorship_id
GROUP BY p.person_id, p.full_name;
