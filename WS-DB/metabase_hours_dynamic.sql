-- Metabase: Часы сотрудников — пивот в SQL (без пивот-визуализации Metabase)
-- Параметры: {{employee}} (Field Filter → ws_users.name),
--            {{date_range}} (Field Filter → ws_time_logs.date_log)
-- Визуализация в Metabase: обычная таблица (Table), НЕ pivot.
-- ВАЖНО: Заголовки колонок статичны (на дату создания запроса 03.03.2026).
--         Данные всегда актуальны (используют CURRENT_DATE).
--         Для обновления заголовков — пересоздайте запрос.

WITH src AS (
    SELECT
        u."name"  AS emp,
        t."date_log" AS dt,
        SUM(t."hours") AS h
    FROM "public"."ws_time_logs" t
    JOIN "public"."ws_users" u ON t."user_id" = u."id"
    JOIN "public"."ws_departments" d ON u."department_id" = d."id"
    WHERE
        d."name" = 'PPC - Відділ контекстної та таргетованої реклами'
        AND {{employee}}
        AND {{date_range}}
    GROUP BY u."name", t."date_log"
),
pvt AS (
    SELECT
        emp,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE),      0) * 60)::int AS m0,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 1),  0) * 60)::int AS m1,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 2),  0) * 60)::int AS m2,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 3),  0) * 60)::int AS m3,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 4),  0) * 60)::int AS m4,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 5),  0) * 60)::int AS m5,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 6),  0) * 60)::int AS m6,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 7),  0) * 60)::int AS m7,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 8),  0) * 60)::int AS m8,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 9),  0) * 60)::int AS m9,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 10), 0) * 60)::int AS m10,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 11), 0) * 60)::int AS m11,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 12), 0) * 60)::int AS m12,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 13), 0) * 60)::int AS m13,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 14), 0) * 60)::int AS m14,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 15), 0) * 60)::int AS m15,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 16), 0) * 60)::int AS m16,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 17), 0) * 60)::int AS m17,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 18), 0) * 60)::int AS m18,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 19), 0) * 60)::int AS m19,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 20), 0) * 60)::int AS m20,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 21), 0) * 60)::int AS m21,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 22), 0) * 60)::int AS m22,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 23), 0) * 60)::int AS m23,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 24), 0) * 60)::int AS m24,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 25), 0) * 60)::int AS m25,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 26), 0) * 60)::int AS m26,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 27), 0) * 60)::int AS m27,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 28), 0) * 60)::int AS m28,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 29), 0) * 60)::int AS m29,
        ROUND(COALESCE(SUM(h) FILTER (WHERE dt = CURRENT_DATE - 30), 0) * 60)::int AS m30,
        ROUND(COALESCE(SUM(h), 0) * 60)::int AS mt
    FROM src
    GROUP BY emp
)
SELECT
    emp AS "Співробітник",
    (m0  / 60) || 'ч ' || (m0  % 60) || 'м' AS "03.03 (Вт)",
    (m1  / 60) || 'ч ' || (m1  % 60) || 'м' AS "02.03 (Пн)",
    (m2  / 60) || 'ч ' || (m2  % 60) || 'м' AS "01.03 (Нд)",
    (m3  / 60) || 'ч ' || (m3  % 60) || 'м' AS "28.02 (Сб)",
    (m4  / 60) || 'ч ' || (m4  % 60) || 'м' AS "27.02 (Пт)",
    (m5  / 60) || 'ч ' || (m5  % 60) || 'м' AS "26.02 (Чт)",
    (m6  / 60) || 'ч ' || (m6  % 60) || 'м' AS "25.02 (Ср)",
    (m7  / 60) || 'ч ' || (m7  % 60) || 'м' AS "24.02 (Вт)",
    (m8  / 60) || 'ч ' || (m8  % 60) || 'м' AS "23.02 (Пн)",
    (m9  / 60) || 'ч ' || (m9  % 60) || 'м' AS "22.02 (Нд)",
    (m10 / 60) || 'ч ' || (m10 % 60) || 'м' AS "21.02 (Сб)",
    (m11 / 60) || 'ч ' || (m11 % 60) || 'м' AS "20.02 (Пт)",
    (m12 / 60) || 'ч ' || (m12 % 60) || 'м' AS "19.02 (Чт)",
    (m13 / 60) || 'ч ' || (m13 % 60) || 'м' AS "18.02 (Ср)",
    (m14 / 60) || 'ч ' || (m14 % 60) || 'м' AS "17.02 (Вт)",
    (m15 / 60) || 'ч ' || (m15 % 60) || 'м' AS "16.02 (Пн)",
    (m16 / 60) || 'ч ' || (m16 % 60) || 'м' AS "15.02 (Нд)",
    (m17 / 60) || 'ч ' || (m17 % 60) || 'м' AS "14.02 (Сб)",
    (m18 / 60) || 'ч ' || (m18 % 60) || 'м' AS "13.02 (Пт)",
    (m19 / 60) || 'ч ' || (m19 % 60) || 'м' AS "12.02 (Чт)",
    (m20 / 60) || 'ч ' || (m20 % 60) || 'м' AS "11.02 (Ср)",
    (m21 / 60) || 'ч ' || (m21 % 60) || 'м' AS "10.02 (Вт)",
    (m22 / 60) || 'ч ' || (m22 % 60) || 'м' AS "09.02 (Пн)",
    (m23 / 60) || 'ч ' || (m23 % 60) || 'м' AS "08.02 (Нд)",
    (m24 / 60) || 'ч ' || (m24 % 60) || 'м' AS "07.02 (Сб)",
    (m25 / 60) || 'ч ' || (m25 % 60) || 'м' AS "06.02 (Пт)",
    (m26 / 60) || 'ч ' || (m26 % 60) || 'м' AS "05.02 (Чт)",
    (m27 / 60) || 'ч ' || (m27 % 60) || 'м' AS "04.02 (Ср)",
    (m28 / 60) || 'ч ' || (m28 % 60) || 'м' AS "03.02 (Вт)",
    (m29 / 60) || 'ч ' || (m29 % 60) || 'м' AS "02.02 (Пн)",
    (m30 / 60) || 'ч ' || (m30 % 60) || 'м' AS "01.02 (Нд)",
    (mt  / 60) || 'ч ' || (mt  % 60) || 'м' AS "Разом"
FROM pvt
ORDER BY emp
