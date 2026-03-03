-- Metabase: Часы сотрудников (динамический диапазон дат)
-- Использует параметры Metabase: {{employee}}, {{date_range}}
-- Формат: простая таблица (без пивота), итог через оконную функцию

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
)
SELECT
    emp AS "Співробітник",
    TO_CHAR(dt, 'DD.MM')
      || ' ('
      || CASE EXTRACT(DOW FROM dt)
           WHEN 0 THEN 'Нд'
           WHEN 1 THEN 'Пн'
           WHEN 2 THEN 'Вт'
           WHEN 3 THEN 'Ср'
           WHEN 4 THEN 'Чт'
           WHEN 5 THEN 'Пт'
           WHEN 6 THEN 'Сб'
         END
      || ')' AS "Дата",
    (ROUND(h * 60)::int / 60) || 'ч '
      || (ROUND(h * 60)::int % 60) || 'м' AS "Години",
    (ROUND(SUM(h) OVER (PARTITION BY emp) * 60)::int / 60) || 'ч '
      || (ROUND(SUM(h) OVER (PARTITION BY emp) * 60)::int % 60) || 'м' AS "Разом"
FROM src
ORDER BY emp, dt DESC
