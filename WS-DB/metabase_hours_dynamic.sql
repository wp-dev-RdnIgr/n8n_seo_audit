-- Metabase: Часы сотрудников (динамический диапазон дат)
-- Использует параметры Metabase: {{employee}}, {{date_range}}
-- Формат: pivot-таблица через UNION ALL с итогами

WITH src AS (
    SELECT
        u."name"                    AS emp,
        "ws_time_logs"."date_log"   AS dt,
        SUM("ws_time_logs"."hours") AS h
    FROM "public"."ws_time_logs"
    JOIN "public"."ws_users"       u ON "ws_time_logs"."user_id"      = u."id"
    JOIN "public"."ws_departments" d ON u."department_id"              = d."id"
    WHERE
        d."name" = 'PPC - Відділ контекстної та таргетованої реклами'
        AND {{employee}}
        AND {{date_range}}
    GROUP BY u."name", "ws_time_logs"."date_log"
),
ranked AS (
    SELECT DISTINCT dt,
           DENSE_RANK() OVER (ORDER BY dt ASC) AS rk
    FROM src
),
daily AS (
    SELECT
        s.emp,
        REPEAT(chr(1), r.rk::int)
          || TO_CHAR(s.dt, 'DD.MM')
          || ' ('
          || CASE EXTRACT(DOW FROM s.dt)
               WHEN 0 THEN 'Нд'
               WHEN 1 THEN 'Пн'
               WHEN 2 THEN 'Вт'
               WHEN 3 THEN 'Ср'
               WHEN 4 THEN 'Чт'
               WHEN 5 THEN 'Пт'
               WHEN 6 THEN 'Сб'
             END
          || ')' AS day_label,
        (ROUND(s.h * 60)::int / 60) || 'ч '
          || (ROUND(s.h * 60)::int % 60) || 'м' AS val
    FROM src s
    JOIN ranked r ON r.dt = s.dt
),
totals AS (
    SELECT
        emp,
        'Разом' AS day_label,
        (ROUND(SUM(h) * 60)::int / 60) || 'ч '
          || (ROUND(SUM(h) * 60)::int % 60) || 'м' AS val
    FROM src
    GROUP BY emp
)
SELECT
    emp        AS "Співробітник",
    day_label  AS "Дата",
    val        AS "Години"
FROM (
    SELECT * FROM daily
    UNION ALL
    SELECT * FROM totals
) t
ORDER BY emp, day_label
