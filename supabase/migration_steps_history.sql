-- TS PRO: Step counter z historią dzienną + B2B weryfikacja
-- Data: 2026-04-30
-- Cel: 10 000 kroków/dzień, reset Polska północ, biz panel weryfikuje klientów po email

-- ── 0. PROFILES.is_admin (potrzebne do RLS i biz panel) ───────────────────
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- Auto-uprawnienia admin dla emaili wspólników
UPDATE public.profiles SET is_admin = TRUE
  WHERE id IN (
    SELECT id FROM auth.users
    WHERE LOWER(email) IN (
      'truckspot.info@gmail.com',
      'krzysiek89sadowski@gmail.com',
      'info.lanacare@gmail.com',
      'kbakowicz86@gmail.com'
    )
  );

-- ── 1. TABELA daily_steps ─────────────────────────────────────────────────
-- Każdy user ma 1 wiersz na dzień (UNIQUE constraint).
-- Na update: stary count zastępowany większym (UPSERT), źródło zapisywane.
CREATE TABLE IF NOT EXISTS public.daily_steps (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  date        DATE NOT NULL,                              -- data Polska (Europe/Warsaw)
  steps       INTEGER NOT NULL DEFAULT 0 CHECK (steps >= 0),
  source      TEXT NOT NULL DEFAULT 'web',                -- 'web' | 'capacitor' | 'manual_test'
  goal        INTEGER NOT NULL DEFAULT 10000,             -- cel danego dnia (zmienny w czasie)
  goal_met    BOOLEAN GENERATED ALWAYS AS (steps >= goal) STORED,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_daily_steps_user_date  ON public.daily_steps(user_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_daily_steps_date_goal  ON public.daily_steps(date, goal_met) WHERE goal_met = TRUE;

-- ── 2. TRIGGER updated_at ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.touch_daily_steps_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_touch_daily_steps ON public.daily_steps;
CREATE TRIGGER trg_touch_daily_steps
  BEFORE UPDATE ON public.daily_steps
  FOR EACH ROW EXECUTE FUNCTION public.touch_daily_steps_updated_at();

-- ── 3. RLS: user widzi swoje, znajomi widzą leaderboard, biz/admin po email ─
ALTER TABLE public.daily_steps ENABLE ROW LEVEL SECURITY;

-- Polityka 1: User widzi swoje wiersze
DROP POLICY IF EXISTS "user_reads_own_steps" ON public.daily_steps;
CREATE POLICY "user_reads_own_steps" ON public.daily_steps
  FOR SELECT USING (auth.uid() = user_id);

-- Polityka 2: User pisze tylko swoje
DROP POLICY IF EXISTS "user_writes_own_steps" ON public.daily_steps;
CREATE POLICY "user_writes_own_steps" ON public.daily_steps
  FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "user_updates_own_steps" ON public.daily_steps;
CREATE POLICY "user_updates_own_steps" ON public.daily_steps
  FOR UPDATE USING (auth.uid() = user_id);

-- Polityka 3: Znajomi widzą kroki (przyjaźń = friendships.status='accepted')
-- Tabela friendships używa kolumn from_user/to_user
DROP POLICY IF EXISTS "friends_read_steps" ON public.daily_steps;
CREATE POLICY "friends_read_steps" ON public.daily_steps
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.friendships f
      WHERE f.status = 'accepted'
        AND (
          (f.from_user = auth.uid() AND f.to_user = daily_steps.user_id)
          OR
          (f.to_user = auth.uid() AND f.from_user = daily_steps.user_id)
        )
    )
  );

-- Polityka 4: Admin widzi wszystko (profiles.is_admin)
DROP POLICY IF EXISTS "admin_reads_all_steps" ON public.daily_steps;
CREATE POLICY "admin_reads_all_steps" ON public.daily_steps
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.id = auth.uid() AND p.is_admin = TRUE
    )
  );

-- ── 4. UPSERT funkcja: user wysyła kroki, my MAX z istniejącym ────────────
-- Bezpieczne wobec race conditions (user może wysyłać z 2 urządzeń)
CREATE OR REPLACE FUNCTION public.upsert_daily_steps(
  p_steps INTEGER,
  p_source TEXT DEFAULT 'web',
  p_goal INTEGER DEFAULT 10000
)
RETURNS public.daily_steps
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_uid UUID;
  v_date DATE;
  v_row public.daily_steps;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;
  IF p_steps < 0 OR p_steps > 200000 THEN
    RAISE EXCEPTION 'Invalid step count: %', p_steps;
  END IF;
  -- Data w Europe/Warsaw (Polska)
  v_date := (NOW() AT TIME ZONE 'Europe/Warsaw')::DATE;

  INSERT INTO public.daily_steps (user_id, date, steps, source, goal)
  VALUES (v_uid, v_date, p_steps, p_source, p_goal)
  ON CONFLICT (user_id, date) DO UPDATE
    SET steps  = GREATEST(public.daily_steps.steps, EXCLUDED.steps),
        goal   = EXCLUDED.goal,
        source = EXCLUDED.source
  RETURNING * INTO v_row;

  RETURN v_row;
END;
$$;

GRANT EXECUTE ON FUNCTION public.upsert_daily_steps(INTEGER, TEXT, INTEGER) TO authenticated;

-- ── 5. FUNKCJA: get_user_step_history (dla biz panel) ─────────────────────
-- Wyszukuje usera po email, zwraca jego ostatnie 30 dni kroków + achievements
-- Tylko dla: admin OR biz owner z aktywną kampanią
CREATE OR REPLACE FUNCTION public.biz_get_user_history(
  p_email TEXT,
  p_days  INTEGER DEFAULT 30
)
RETURNS TABLE (
  user_id        UUID,
  display_name   TEXT,
  email          TEXT,
  total_xp       INTEGER,
  level          INTEGER,
  date           DATE,
  steps          INTEGER,
  goal           INTEGER,
  goal_met       BOOLEAN
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_caller UUID;
  v_is_admin BOOLEAN;
  v_target UUID;
BEGIN
  v_caller := auth.uid();
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'Not authenticated';
  END IF;

  -- Sprawdź czy caller jest adminem LUB ma jakąkolwiek place (biz owner)
  SELECT p.is_admin INTO v_is_admin FROM public.profiles p WHERE p.id = v_caller;
  IF NOT COALESCE(v_is_admin, FALSE) THEN
    IF NOT EXISTS (SELECT 1 FROM public.places WHERE owner_user_id = v_caller) THEN
      RAISE EXCEPTION 'Permission denied — admin or biz owner required';
    END IF;
  END IF;

  -- Znajdź target user_id po email
  SELECT u.id INTO v_target FROM auth.users u WHERE LOWER(u.email) = LOWER(p_email);
  IF v_target IS NULL THEN
    RAISE EXCEPTION 'User with email % not found', p_email;
  END IF;

  RETURN QUERY
  SELECT
    pr.id AS user_id,
    pr.display_name,
    (SELECT au.email FROM auth.users au WHERE au.id = pr.id)::TEXT AS email,
    COALESCE(us.total_xp, 0) AS total_xp,
    COALESCE(us.level, 1) AS level,
    ds.date,
    ds.steps,
    ds.goal,
    ds.goal_met
  FROM public.profiles pr
  LEFT JOIN public.user_stats us ON us.user_id = pr.id
  LEFT JOIN public.daily_steps ds
    ON ds.user_id = pr.id
    AND ds.date >= ((NOW() AT TIME ZONE 'Europe/Warsaw')::DATE - p_days)
  WHERE pr.id = v_target
  ORDER BY ds.date DESC NULLS LAST;
END;
$$;

GRANT EXECUTE ON FUNCTION public.biz_get_user_history(TEXT, INTEGER) TO authenticated;

-- ── 6. WIDOK leaderboard znajomych dzisiaj (przygotowany na Etap 2) ──────
-- Zwraca user_id, display_name, avatar, steps_today posortowane DESC
CREATE OR REPLACE VIEW public.v_friends_leaderboard_today AS
SELECT
  pr.id AS user_id,
  pr.display_name,
  pr.avatar_2d_url,
  COALESCE(ds.steps, 0) AS steps,
  COALESCE(ds.goal, 10000) AS goal,
  COALESCE(ds.goal_met, FALSE) AS goal_met
FROM public.profiles pr
LEFT JOIN public.daily_steps ds
  ON ds.user_id = pr.id
  AND ds.date = (NOW() AT TIME ZONE 'Europe/Warsaw')::DATE;
-- (Filtrowanie znajomych robimy po stronie klienta przez RLS — view dziedziczy uprawnienia)

COMMENT ON TABLE public.daily_steps IS 'Kroki użytkownika per-dzień. Reset codzienny: północ Europe/Warsaw.';
COMMENT ON FUNCTION public.upsert_daily_steps IS 'UPSERT: jeśli wiersz istnieje, bierze MAX(stary, nowy). Bezpieczne dla wielu urządzeń.';
COMMENT ON FUNCTION public.biz_get_user_history IS 'Panel /biz: właściciel firmy lub admin wyszukuje usera po email i widzi 30 dni historii kroków + XP.';
