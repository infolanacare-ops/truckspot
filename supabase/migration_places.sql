-- Migracja: Places (lokale/biznesy) + ich wiadomości
-- Uruchom w Supabase → SQL Editor → Run

-- 1. Tabela miejsc
CREATE TABLE IF NOT EXISTS public.places (
  id BIGSERIAL PRIMARY KEY,
  owner_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL DEFAULT 'other',  -- cafe|pub|club|restaurant|gym|shop|beauty|fitness|other
  lat NUMERIC(10,6) NOT NULL,
  lng NUMERIC(10,6) NOT NULL,
  address TEXT,
  city TEXT,
  phone TEXT,
  website TEXT,
  description TEXT,
  photo_url TEXT,
  hours TEXT,
  plan TEXT NOT NULL DEFAULT 'free',  -- free|promoted|pro
  promoted_until DATE,
  visits_total INT DEFAULT 0,
  rating_avg NUMERIC(3,2),
  rating_count INT DEFAULT 0,
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_places_geo ON public.places (lat, lng);
CREATE INDEX IF NOT EXISTS idx_places_owner ON public.places (owner_user_id);
CREATE INDEX IF NOT EXISTS idx_places_plan ON public.places (plan, active);

-- 2. Wiadomości lokalu (auto-expiring)
CREATE TABLE IF NOT EXISTS public.place_messages (
  id BIGSERIAL PRIMARY KEY,
  place_id BIGINT NOT NULL REFERENCES public.places(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  emoji TEXT DEFAULT '📢',
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pm_active ON public.place_messages (place_id, expires_at) WHERE expires_at > NOW();

-- 3. RLS
ALTER TABLE public.places ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "places_read_all" ON public.places;
CREATE POLICY "places_read_all" ON public.places
  FOR SELECT USING (active = TRUE);

DROP POLICY IF EXISTS "places_owner_update" ON public.places;
CREATE POLICY "places_owner_update" ON public.places
  FOR UPDATE USING (auth.uid() = owner_user_id) WITH CHECK (auth.uid() = owner_user_id);

ALTER TABLE public.place_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "pm_read_active" ON public.place_messages;
CREATE POLICY "pm_read_active" ON public.place_messages
  FOR SELECT USING (expires_at > NOW());

DROP POLICY IF EXISTS "pm_owner_insert" ON public.place_messages;
CREATE POLICY "pm_owner_insert" ON public.place_messages
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM public.places WHERE id = place_messages.place_id AND owner_user_id = auth.uid())
  );

DROP POLICY IF EXISTS "pm_owner_delete" ON public.place_messages;
CREATE POLICY "pm_owner_delete" ON public.place_messages
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM public.places WHERE id = place_messages.place_id AND owner_user_id = auth.uid())
  );

-- 4. Realtime dla wiadomości (live banners)
DO $$ BEGIN
  ALTER PUBLICATION supabase_realtime ADD TABLE public.place_messages;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 5. Demo dane (3 przykładowe lokale w Warszawie — usuń po pierwszych prawdziwych)
INSERT INTO public.places (name, category, lat, lng, address, city, hours, description, plan)
VALUES
  ('Costa Coffee Marszałkowska', 'cafe', 52.230120, 21.013440, 'Marszałkowska 100', 'Warszawa', 'Pn-Pt 7-22, Sb-Nd 9-22', 'Najlepsza kawa w centrum', 'promoted'),
  ('Klub Hybrydy', 'club', 52.232851, 21.012231, 'Złota 7', 'Warszawa', 'Pt-Sb 22-6', 'Imprezy, dj, taniec', 'free'),
  ('Pub Pijalnia Wódki i Piwa', 'pub', 52.229891, 21.011552, 'Nowy Świat 23', 'Warszawa', 'Codziennie 16-3', 'Klasyk Krakowskiego Przedmieścia', 'free')
ON CONFLICT DO NOTHING;

SELECT 'OK' AS status, COUNT(*) AS places_count FROM public.places;
