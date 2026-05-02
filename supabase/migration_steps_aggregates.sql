-- ── KROKI: agregacje tydzień / miesiąc + auto-zaliczanie zadań ─────────────
-- Krzysiek 02.05.2026: "kroki maja zaliczać te zadania automatycznie"
-- ────────────────────────────────────────────────────────────────────────────

-- 1. RPC: agregacje user steps (dziś/tydzień/miesiąc/rok) jednym wywołaniem
CREATE OR REPLACE FUNCTION public.steps_summary(p_user UUID DEFAULT NULL)
RETURNS TABLE (
  today_steps   INT,
  today_goal    INT,
  week_steps    BIGINT,
  week_avg      INT,
  month_steps   BIGINT,
  month_avg     INT,
  year_steps    BIGINT,
  total_steps   BIGINT,
  best_day      DATE,
  best_steps    INT,
  current_streak INT,
  days_with_data INT
)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  uid UUID := COALESCE(p_user, auth.uid());
  pl_today DATE := (now() AT TIME ZONE 'Europe/Warsaw')::DATE;
  streak INT := 0;
  d DATE := pl_today;
BEGIN
  -- Streak: ile kolejnych dni z >= 5000 kroków od dziś wstecz
  WHILE EXISTS (SELECT 1 FROM daily_steps WHERE user_id = uid AND date = d AND steps >= 5000) LOOP
    streak := streak + 1;
    d := d - INTERVAL '1 day';
  END LOOP;

  RETURN QUERY
  SELECT
    COALESCE((SELECT steps FROM daily_steps WHERE user_id = uid AND date = pl_today), 0)::INT,
    COALESCE((SELECT goal  FROM daily_steps WHERE user_id = uid AND date = pl_today), 10000)::INT,
    COALESCE((SELECT SUM(steps) FROM daily_steps WHERE user_id = uid AND date >= pl_today - INTERVAL '6 days' AND date <= pl_today), 0)::BIGINT,
    COALESCE((SELECT ROUND(AVG(steps))::INT FROM daily_steps WHERE user_id = uid AND date >= pl_today - INTERVAL '6 days' AND date <= pl_today AND steps > 0), 0),
    COALESCE((SELECT SUM(steps) FROM daily_steps WHERE user_id = uid AND date >= pl_today - INTERVAL '29 days' AND date <= pl_today), 0)::BIGINT,
    COALESCE((SELECT ROUND(AVG(steps))::INT FROM daily_steps WHERE user_id = uid AND date >= pl_today - INTERVAL '29 days' AND date <= pl_today AND steps > 0), 0),
    COALESCE((SELECT SUM(steps) FROM daily_steps WHERE user_id = uid AND date >= pl_today - INTERVAL '364 days' AND date <= pl_today), 0)::BIGINT,
    COALESCE((SELECT SUM(steps) FROM daily_steps WHERE user_id = uid), 0)::BIGINT,
    (SELECT date FROM daily_steps WHERE user_id = uid ORDER BY steps DESC NULLS LAST LIMIT 1),
    COALESCE((SELECT MAX(steps) FROM daily_steps WHERE user_id = uid), 0)::INT,
    streak,
    (SELECT COUNT(*)::INT FROM daily_steps WHERE user_id = uid AND steps > 0);
END;
$$;

GRANT EXECUTE ON FUNCTION public.steps_summary TO authenticated, anon;

-- 2. RPC: ostatnie 30 dni jako tablica (dla bar chart heatmap)
CREATE OR REPLACE FUNCTION public.steps_last_n_days(p_days INT DEFAULT 30)
RETURNS TABLE (date DATE, steps INT, goal INT, met BOOLEAN)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  uid UUID := auth.uid();
  pl_today DATE := (now() AT TIME ZONE 'Europe/Warsaw')::DATE;
BEGIN
  RETURN QUERY
  SELECT
    d::DATE,
    COALESCE(ds.steps, 0)::INT,
    COALESCE(ds.goal, 10000)::INT,
    (COALESCE(ds.steps, 0) >= COALESCE(ds.goal, 10000))::BOOLEAN
  FROM generate_series(pl_today - (p_days - 1) * INTERVAL '1 day', pl_today, INTERVAL '1 day') AS d
  LEFT JOIN daily_steps ds ON ds.user_id = uid AND ds.date = d::DATE
  ORDER BY d ASC;
END;
$$;

GRANT EXECUTE ON FUNCTION public.steps_last_n_days TO authenticated;

-- 3. RPC: auto-zaliczanie zadań krokowych (Krzysiek life-saver)
-- Wołane z _addSteps po każdym update kroków
-- Znajduje wszystkie aktywne taski typu 'steps' / 'walk' z odpowiednim horyzontem,
-- aktualizuje task_progress.current_value, jeśli osiąga goal — completed=true + XP
CREATE OR REPLACE FUNCTION public.auto_claim_step_tasks(p_today_steps INT)
RETURNS TABLE (task_id BIGINT, title TEXT, xp_granted INT, just_completed BOOLEAN)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
DECLARE
  uid UUID := auth.uid();
  pl_today DATE := (now() AT TIME ZONE 'Europe/Warsaw')::DATE;
  pl_week_start DATE := pl_today - ((EXTRACT(DOW FROM pl_today)::INT + 6) % 7) * INTERVAL '1 day';
  pl_month_start DATE := DATE_TRUNC('month', pl_today)::DATE;
  v_task RECORD;
  v_prog RECORD;
  v_value INT;
  v_was_completed BOOLEAN;
BEGIN
  IF uid IS NULL THEN RETURN; END IF;

  FOR v_task IN
    SELECT * FROM tasks
    WHERE active = true
      AND task_type IN ('steps','walk','daily_steps','weekly_steps','monthly_steps')
      AND (ends_at IS NULL OR ends_at > now())
  LOOP
    -- Wartość bieżąca zależnie od horyzontu zadania
    IF v_task.horizon = 'daily' THEN
      v_value := p_today_steps;
    ELSIF v_task.horizon = 'weekly' THEN
      SELECT COALESCE(SUM(steps),0)::INT INTO v_value
        FROM daily_steps WHERE user_id = uid AND date >= pl_week_start AND date <= pl_today;
    ELSIF v_task.horizon = 'monthly' THEN
      SELECT COALESCE(SUM(steps),0)::INT INTO v_value
        FROM daily_steps WHERE user_id = uid AND date >= pl_month_start AND date <= pl_today;
    ELSE
      v_value := p_today_steps; -- fallback
    END IF;

    -- Pobierz/utworz progress
    SELECT * INTO v_prog FROM task_progress
      WHERE task_id = v_task.id AND user_id = uid;

    v_was_completed := COALESCE(v_prog.completed, false);

    IF v_prog IS NULL THEN
      INSERT INTO task_progress (task_id, user_id, current_value, completed)
      VALUES (v_task.id, uid, v_value, v_value >= COALESCE(v_task.goal_value, 1));
    ELSE
      UPDATE task_progress SET
        current_value = GREATEST(v_prog.current_value, v_value),
        completed = (GREATEST(v_prog.current_value, v_value) >= COALESCE(v_task.goal_value, 1)),
        completed_at = CASE
          WHEN v_was_completed THEN v_prog.completed_at
          WHEN GREATEST(v_prog.current_value, v_value) >= COALESCE(v_task.goal_value, 1) THEN now()
          ELSE NULL
        END
      WHERE task_id = v_task.id AND user_id = uid;
    END IF;

    -- Jeśli zadanie właśnie się zakończyło — XP grant
    IF NOT v_was_completed AND v_value >= COALESCE(v_task.goal_value, 1) THEN
      INSERT INTO user_stats (user_id, total_xp, tasks_completed, level)
      VALUES (uid, COALESCE(v_task.xp_reward, 0), 1, 1)
      ON CONFLICT (user_id) DO UPDATE SET
        total_xp = user_stats.total_xp + COALESCE(v_task.xp_reward, 0),
        tasks_completed = user_stats.tasks_completed + 1,
        level = GREATEST(1, FLOOR(SQRT(GREATEST(0, user_stats.total_xp + COALESCE(v_task.xp_reward, 0))/25.0))::INT + 1);
      task_id := v_task.id;
      title := v_task.title;
      xp_granted := COALESCE(v_task.xp_reward, 0);
      just_completed := true;
      RETURN NEXT;
    END IF;
  END LOOP;
END;
$$;

GRANT EXECUTE ON FUNCTION public.auto_claim_step_tasks TO authenticated;
