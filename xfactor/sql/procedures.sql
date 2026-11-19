-- Stored procedures for the X Factor UK database.
-- Statements are separated by lines containing only "-- @@" (see xfactor/sql/apply.py).
-- No DELIMITER directives are needed because each statement is sent on its own.

DROP PROCEDURE IF EXISTS sp_act_journey;
-- @@
-- Every song an act performed, week by week, across all series it entered.
CREATE PROCEDURE sp_act_journey(IN p_act_name VARCHAR(120))
BEGIN
    SELECT s.series_number, ls.week_number, ls.stage, ls.theme,
           so.title AS song, ar.name AS song_artist,
           p.running_order, p.is_showdown, p.result_text
    FROM act a
    JOIN series_act sa  ON sa.act_id = a.act_id
    JOIN series s       ON s.series_id = sa.series_id
    JOIN performance p  ON p.entry_id = sa.entry_id
    JOIN live_show ls   ON ls.show_id = p.show_id
    JOIN song so        ON so.song_id = p.song_id
    LEFT JOIN artist ar ON ar.artist_id = so.artist_id
    WHERE a.name LIKE CONCAT('%', p_act_name, '%')
    ORDER BY s.series_number, ls.week_number, p.night, p.is_showdown, p.running_order;
END;
-- @@
DROP PROCEDURE IF EXISTS sp_series_leaderboard;
-- @@
-- Final standings for one series, with category, mentor and number of songs sung.
CREATE PROCEDURE sp_series_leaderboard(IN p_series_number INT)
BEGIN
    SELECT sa.final_position, a.name AS act, c.name AS category,
           pe.full_name AS mentor, h.name AS hometown, sa.result_text,
           COUNT(p.performance_id) AS songs_performed
    FROM series s
    JOIN series_act sa     ON sa.series_id = s.series_id
    JOIN act a             ON a.act_id = sa.act_id
    LEFT JOIN mentorship m ON m.mentorship_id = sa.mentorship_id
    LEFT JOIN category c   ON c.category_id = m.category_id
    LEFT JOIN person pe    ON pe.person_id = m.mentor_id
    LEFT JOIN hometown h   ON h.hometown_id = sa.hometown_id
    LEFT JOIN performance p ON p.entry_id = sa.entry_id
    WHERE s.series_number = p_series_number
    GROUP BY sa.entry_id, sa.final_position, a.name, c.name, pe.full_name, h.name, sa.result_text
    ORDER BY sa.final_position;
END;
-- @@
DROP PROCEDURE IF EXISTS sp_record_showdown_result;
-- @@
-- Write procedure: change the result of an act's performances in a given week.
-- Returns the number of rows updated through an OUT parameter.
CREATE PROCEDURE sp_record_showdown_result(
    IN  p_series_number INT,
    IN  p_week_number   INT,
    IN  p_act_name      VARCHAR(120),
    IN  p_result        VARCHAR(80),
    OUT p_rows_updated  INT)
BEGIN
    UPDATE performance p
    JOIN live_show ls  ON ls.show_id = p.show_id
    JOIN series s      ON s.series_id = ls.series_id
    JOIN series_act sa ON sa.entry_id = p.entry_id
    JOIN act a         ON a.act_id = sa.act_id
    SET p.result_text = p_result
    WHERE s.series_number = p_series_number
      AND ls.week_number = p_week_number
      AND a.name = p_act_name;
    SET p_rows_updated = ROW_COUNT();
END;
