-- ═══════════════════════════════════════════════════════════════
-- TS PRO TASKS & GAMIFICATION — kompleksowa struktura
-- Daily / Weekly / Monthly + Location-locked + Sponsors (lokalni + online)
-- ═══════════════════════════════════════════════════════════════

-- ── 1. SPONSORS (lokalni + online jak Zalando, Empik) ─────────────
CREATE TABLE IF NOT EXISTS public.sponsors (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,                -- "Zalando", "Empik", "Costa Coffee"
  type TEXT NOT NULL DEFAULT 'local',-- 'local' | 'online' | 'national'
  logo_url TEXT,
  website TEXT,                      -- "https://zalando.pl"
  affiliate_url_template TEXT,       -- "https://zalando.pl/?promo={CODE}&aff=tspro"
  place_id BIGINT REFERENCES public.places(id) ON DELETE SET NULL, -- jeśli lokalny
  category TEXT,                     -- 'fashion' | 'food' | 'beauty' | 'fitness' | ...
  description TEXT,
  contact_email TEXT,
  contract_status TEXT DEFAULT 'active', -- 'active' | 'pending' | 'paused' | 'ended'
  commission_pct NUMERIC(5,2),       -- np. 5.00 = 5% prowizja od konwersji
  cpa_amount_pln NUMERIC(8,2),       -- jeśli stała kwota za acquisition
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sponsors_type ON public.sponsors (type, active);

-- ── 2. TASKS (zadania — 3 horyzonty + opcjonalnie geo) ────────────
CREATE TABLE IF NOT EXISTS public.tasks (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,               -- "Zrób 10000 kroków"
  description TEXT,
  emoji TEXT DEFAULT '🎯',
  -- Source kategoria (kto stworzył/po co): 'company' | 'community' | 'live' | 'system'
  source TEXT NOT NULL DEFAULT 'system',
  -- Mechanika zadania: 'steps' | 'visit' | 'photo' | 'video' | 'quiz' | 'social' | 'shop_online'
  type TEXT NOT NULL,
  -- Horyzont czasowy: 'daily' | 'weekly' | 'monthly' | 'campaign' | 'permanent'
  horizon TEXT NOT NULL,
  -- Kto stworzył (NULL = TS PRO admin / system)
  created_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,

  goal_value INT,                    -- 10000 (kroków), 3 (wizyt), 1 (zdjęcie)
  goal_unit TEXT,                    -- 'kroki' | 'wizyt' | 'zdjęć' | 'min'

  -- Location lock (opcjonalne — null = task globalny)
  lat NUMERIC(10,6),
  lng NUMERIC(10,6),
  trigger_radius_m INT,              -- 30m geofence
  min_dwell_seconds INT DEFAULT 60,  -- min czas obecności
  hidden_until_nearby BOOLEAN DEFAULT FALSE, -- fog of war (Pokemon Go style)
  city TEXT,                         -- ograniczenie do miasta

  -- Sponsor i nagroda
  sponsor_id BIGINT REFERENCES public.sponsors(id) ON DELETE SET NULL,
  xp_reward INT DEFAULT 50,
  coupon_template_id BIGINT,         -- referencja do coupon_templates (poniżej)

  -- Quiz fields (jeśli type='quiz')
  quiz_question TEXT,
  quiz_answer TEXT,                  -- ignore case + trim

  -- Czas
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  max_completions_per_user INT DEFAULT 1,  -- raz w życiu vs odświeżalne
  total_completions INT DEFAULT 0,

  -- Branding
  banner_color TEXT DEFAULT '#d4af37',
  banner_emoji TEXT,

  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tasks_active_horizon ON public.tasks (active, horizon, ends_at);
CREATE INDEX IF NOT EXISTS idx_tasks_source ON public.tasks (source, active);
CREATE INDEX IF NOT EXISTS idx_tasks_geo ON public.tasks (lat, lng) WHERE lat IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_city ON public.tasks (city, active);

-- ── 3. TASK PROGRESS (postęp usera per task) ──────────────────────
CREATE TABLE IF NOT EXISTS public.task_progress (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT REFERENCES public.tasks(id) ON DELETE CASCADE,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  current_value INT DEFAULT 0,
  completed BOOLEAN DEFAULT FALSE,
  completed_at TIMESTAMPTZ,
  xp_awarded INT DEFAULT 0,
  unlock_seen BOOLEAN DEFAULT FALSE, -- czy user widział unlock dla geo task
  unlocked_at TIMESTAMPTZ,
  -- proof — np. URL zdjęcia z photo task
  proof_url TEXT,
  proof_meta JSONB DEFAULT '{}'::jsonb,
  UNIQUE(task_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_tprogress_user ON public.task_progress (user_id, completed);

-- ── 4. USER STATS (level, XP, streaks) ────────────────────────────
CREATE TABLE IF NOT EXISTS public.user_stats (
  user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  total_xp INT DEFAULT 0,
  level INT DEFAULT 1,
  daily_streak INT DEFAULT 0,
  longest_streak INT DEFAULT 0,
  last_active_date DATE,
  tasks_completed INT DEFAULT 0,
  coupons_won INT DEFAULT 0,
  city TEXT,                         -- "główne miasto" usera (auto-detected lub set)
  display_rank TEXT,                 -- "Rookie" | "Explorer" | "Legend" | ...
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 5. COUPON TEMPLATES (definicja nagrody — wielokrotnego użytku) ─
CREATE TABLE IF NOT EXISTS public.coupon_templates (
  id BIGSERIAL PRIMARY KEY,
  sponsor_id BIGINT REFERENCES public.sponsors(id) ON DELETE CASCADE,
  title TEXT NOT NULL,               -- "Kebab -20%"
  description TEXT,
  emoji TEXT DEFAULT '🎁',
  discount_value TEXT,               -- "-20%" | "-30 zł" | "Gratis kawa"

  -- Online vs in-store
  delivery_type TEXT DEFAULT 'in_store', -- 'in_store' | 'online_code' | 'affiliate_link'
  static_code TEXT,                  -- np. ZALANDO20 (wszyscy ten sam)
  generates_unique_code BOOLEAN DEFAULT TRUE, -- czy generujemy unique per user

  validity_days INT DEFAULT 7,       -- ważność po wygenerowaniu
  max_per_user INT DEFAULT 1,        -- ile razy user może wygrać
  total_supply INT,                  -- limit całkowity (np. 100 kuponów Zalando)
  used_count INT DEFAULT 0,

  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ── 6. COUPONS (wygrane przez konkretnych userów) ──────────────────
CREATE TABLE IF NOT EXISTS public.coupons (
  id BIGSERIAL PRIMARY KEY,
  template_id BIGINT REFERENCES public.coupon_templates(id) ON DELETE SET NULL,
  task_id BIGINT REFERENCES public.tasks(id) ON DELETE SET NULL,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,

  code TEXT UNIQUE NOT NULL,         -- "TSPR-K3F8M2" lub static np "ZALANDO20"
  delivery_type TEXT NOT NULL,       -- 'in_store' | 'online_code' | 'affiliate_link'
  affiliate_url TEXT,                -- gotowy link "https://zalando.pl/?promo=TSPR-K3F8M2&aff=tspro_USER123"

  redeemed_at TIMESTAMPTZ,           -- gdy lokal zeskanował lub user kliknął online link
  redeemed_by_place_id BIGINT REFERENCES public.places(id),

  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_coupons_user ON public.coupons (user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_coupons_code ON public.coupons (code);

-- ── 7. ACHIEVEMENTS (odznaki) ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.achievements (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  badge_key TEXT NOT NULL,           -- 'first_10k_steps', 'streak_7', 'sieradz_master'
  badge_name TEXT NOT NULL,
  badge_emoji TEXT,
  description TEXT,
  earned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, badge_key)
);

-- ── 8. CAMPAIGNS (akcje typu "Aktywuj Sieradz 10k kroków") ────────
CREATE TABLE IF NOT EXISTS public.campaigns (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  city TEXT NOT NULL,
  banner_emoji TEXT DEFAULT '🔥',
  banner_color TEXT DEFAULT '#d4af37',
  starts_at TIMESTAMPTZ,
  ends_at TIMESTAMPTZ,
  max_winners INT,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Powiązanie: campaign → tasks (akcja może mieć wiele zadań)
ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS campaign_id BIGINT REFERENCES public.campaigns(id) ON DELETE SET NULL;

-- Powiązanie: campaign → sponsors (które firmy dorzucają nagrody)
CREATE TABLE IF NOT EXISTS public.campaign_sponsors (
  id BIGSERIAL PRIMARY KEY,
  campaign_id BIGINT REFERENCES public.campaigns(id) ON DELETE CASCADE,
  sponsor_id BIGINT REFERENCES public.sponsors(id) ON DELETE CASCADE,
  coupon_template_id BIGINT REFERENCES public.coupon_templates(id),
  payment_amount_pln NUMERIC(8,2),  -- ile firma płaci za udział
  payment_status TEXT DEFAULT 'pending', -- 'pending' | 'paid' | 'free'
  UNIQUE(campaign_id, sponsor_id)
);

-- ═══════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════

ALTER TABLE public.sponsors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "sponsors_read_all" ON public.sponsors;
CREATE POLICY "sponsors_read_all" ON public.sponsors FOR SELECT USING (active = TRUE);

ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "tasks_read_all" ON public.tasks;
CREATE POLICY "tasks_read_all" ON public.tasks FOR SELECT USING (active = TRUE);

ALTER TABLE public.task_progress ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "tprogress_own" ON public.task_progress;
CREATE POLICY "tprogress_own" ON public.task_progress FOR SELECT USING (auth.uid() = user_id);
DROP POLICY IF EXISTS "tprogress_insert_own" ON public.task_progress;
CREATE POLICY "tprogress_insert_own" ON public.task_progress FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "tprogress_update_own" ON public.task_progress;
CREATE POLICY "tprogress_update_own" ON public.task_progress FOR UPDATE USING (auth.uid() = user_id);

ALTER TABLE public.user_stats ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "stats_read_authenticated" ON public.user_stats;
CREATE POLICY "stats_read_authenticated" ON public.user_stats FOR SELECT USING (auth.role() = 'authenticated');
DROP POLICY IF EXISTS "stats_insert_own" ON public.user_stats;
CREATE POLICY "stats_insert_own" ON public.user_stats FOR INSERT WITH CHECK (auth.uid() = user_id);
DROP POLICY IF EXISTS "stats_update_own" ON public.user_stats;
CREATE POLICY "stats_update_own" ON public.user_stats FOR UPDATE USING (auth.uid() = user_id);

ALTER TABLE public.coupon_templates ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "ctmpl_read_all" ON public.coupon_templates;
CREATE POLICY "ctmpl_read_all" ON public.coupon_templates FOR SELECT USING (active = TRUE);

ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "coupons_own" ON public.coupons;
CREATE POLICY "coupons_own" ON public.coupons FOR SELECT USING (auth.uid() = user_id);

ALTER TABLE public.achievements ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "achievements_read_all" ON public.achievements;
CREATE POLICY "achievements_read_all" ON public.achievements FOR SELECT USING (auth.role() = 'authenticated');

ALTER TABLE public.campaigns ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "campaigns_read_all" ON public.campaigns;
CREATE POLICY "campaigns_read_all" ON public.campaigns FOR SELECT USING (active = TRUE);

ALTER TABLE public.campaign_sponsors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "csp_read_all" ON public.campaign_sponsors;
CREATE POLICY "csp_read_all" ON public.campaign_sponsors FOR SELECT USING (TRUE);

-- ═══════════════════════════════════════════════════════════════
-- TRIGGER: auto level-up po zdobyciu XP
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.recalc_user_level()
RETURNS TRIGGER AS $$
BEGIN
  -- Formula: level N requires N*(N-1)*50 XP cumulative
  -- level 2 = 100, level 3 = 300, level 4 = 600, level 5 = 1000, level 10 = 4500, level 20 = 19000
  NEW.level := GREATEST(1, FLOOR(0.5 + SQRT(0.25 + NEW.total_xp / 25.0))::INT);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS user_stats_level_recalc ON public.user_stats;
CREATE TRIGGER user_stats_level_recalc
  BEFORE INSERT OR UPDATE OF total_xp ON public.user_stats
  FOR EACH ROW EXECUTE FUNCTION public.recalc_user_level();

-- ═══════════════════════════════════════════════════════════════
-- TRIGGER: po complete task → +XP do user_stats + counter +1
-- ═══════════════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION public.award_task_xp()
RETURNS TRIGGER AS $$
DECLARE
  task_xp INT;
BEGIN
  IF NEW.completed = TRUE AND (OLD IS NULL OR OLD.completed = FALSE) THEN
    SELECT xp_reward INTO task_xp FROM public.tasks WHERE id = NEW.task_id;
    NEW.xp_awarded := COALESCE(task_xp, 0);
    NEW.completed_at := NOW();

    -- Upsert user_stats
    INSERT INTO public.user_stats (user_id, total_xp, tasks_completed, last_active_date)
    VALUES (NEW.user_id, COALESCE(task_xp, 0), 1, CURRENT_DATE)
    ON CONFLICT (user_id) DO UPDATE
      SET total_xp = user_stats.total_xp + COALESCE(task_xp, 0),
          tasks_completed = user_stats.tasks_completed + 1,
          last_active_date = CURRENT_DATE,
          updated_at = NOW();

    -- Bumpni licznik na zadaniu
    UPDATE public.tasks SET total_completions = COALESCE(total_completions, 0) + 1 WHERE id = NEW.task_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS task_progress_award_xp ON public.task_progress;
CREATE TRIGGER task_progress_award_xp
  BEFORE INSERT OR UPDATE OF completed ON public.task_progress
  FOR EACH ROW EXECUTE FUNCTION public.award_task_xp();

-- ═══════════════════════════════════════════════════════════════
-- DEMO DATA — pierwsza kampania Sieradz + przykłady online sponsors
-- ═══════════════════════════════════════════════════════════════

-- Sponsorzy demo (lokalni)
INSERT INTO public.sponsors (name, type, category, place_id, contract_status) VALUES
  ('Costa Coffee Marszałkowska', 'local', 'cafe', (SELECT id FROM places WHERE name='Costa Coffee Marszałkowska' LIMIT 1), 'active'),
  ('Pasza Kebab', 'local', 'food', NULL, 'active'),
  ('King Nails', 'local', 'beauty', NULL, 'active')
ON CONFLICT DO NOTHING;

-- Sponsorzy demo (online — przykład Zalando, Empik)
INSERT INTO public.sponsors (name, type, category, website, affiliate_url_template, contract_status, commission_pct) VALUES
  ('Zalando', 'online', 'fashion', 'https://zalando.pl', 'https://zalando.pl/?promo={CODE}&utm_source=tspro&utm_campaign={CAMPAIGN}', 'pending', 5.00),
  ('Empik', 'online', 'books', 'https://empik.com', 'https://empik.com/promo/{CODE}?aff=tspro', 'pending', 4.00),
  ('Allegro Smart', 'online', 'shopping', 'https://allegro.pl', 'https://allegro.pl/?promo={CODE}&aff=tspro', 'pending', 3.00)
ON CONFLICT DO NOTHING;

-- Pierwsza kampania
INSERT INTO public.campaigns (title, description, city, banner_emoji, starts_at, ends_at, max_winners, active) VALUES
  ('🔥 Aktywuj Sieradz · 10k kroków', 'Zrób 10000 kroków w jeden dzień, odbierz nagrody od 5 firm', 'Sieradz', '🚶', NOW(), NOW() + INTERVAL '7 days', 50, TRUE)
ON CONFLICT DO NOTHING;

-- Pierwsze przykładowe zadania (daily)
INSERT INTO public.tasks (title, description, emoji, type, horizon, goal_value, goal_unit, xp_reward, active, ends_at) VALUES
  ('Zrób 5000 kroków', 'Codzienny ruch', '🚶', 'steps', 'daily', 5000, 'kroki', 50, TRUE, NOW() + INTERVAL '1 day'),
  ('Wpadnij do nowej kawiarni', 'Odkryj coś nowego', '☕', 'visit', 'daily', 1, 'wizyt', 30, TRUE, NOW() + INTERVAL '1 day'),
  ('Napisz do ziomka', 'Społeczność = engagement', '💬', 'social', 'daily', 1, 'wiadomości', 10, TRUE, NOW() + INTERVAL '1 day')
ON CONFLICT DO NOTHING;

SELECT 'OK — TASKS & GAMIFICATION ready' AS status;
