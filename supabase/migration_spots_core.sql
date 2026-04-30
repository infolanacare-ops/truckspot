-- TribeSpot: SPOTS CORE — efemeryczne miejsca od userów
-- Data: 2026-04-30
-- Idea: user postuje "tu się dzieje" (foto + GPS + vibe + opis) → spot jest aktywny X godzin
-- Inne osoby JOINUJĄ spot (spot_joins) → people_count rośnie → mocniejszy glow na mapie
-- Auto-expire po 6h domyślnie (lub do active_until ustawionego przez postera)

-- ── 1. TABELA spots ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.spots (
  id           BIGSERIAL PRIMARY KEY,
  posted_by    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  lat          NUMERIC(10,6) NOT NULL,
  lng          NUMERIC(10,6) NOT NULL,
  -- Treść
  photo_url    TEXT,                              -- opcjonalne (Supabase Storage)
  description  TEXT,                              -- max 280 char (Twitter style)
  vibe         TEXT NOT NULL DEFAULT 'chill',     -- party|chill|food|sport|view|queue|event|other
  -- Czas życia
  active_until TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '6 hours'),
  expired      BOOLEAN GENERATED ALWAYS AS (NOW() > active_until) STORED,
  -- Statystyki (denormalizowane dla performance)
  joins_count  INT NOT NULL DEFAULT 1,            -- auto-aktualizowane triggerem
  views_count  INT NOT NULL DEFAULT 0,
  -- Powiązanie z biznesem (opcjonalne — gdy spot jest u biznesu z place_id)
  place_id     BIGINT REFERENCES public.places(id) ON DELETE SET NULL,
  -- Anti-spam
  flagged      BOOLEAN DEFAULT FALSE,
  hidden       BOOLEAN DEFAULT FALSE,
  -- Czas
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CHECK (LENGTH(COALESCE(description, '')) <= 280),
  CHECK (vibe IN ('party','chill','food','sport','view','queue','event','other'))
);

CREATE INDEX IF NOT EXISTS idx_spots_geo_active     ON public.spots (lat, lng) WHERE NOT hidden AND active_until > NOW();
CREATE INDEX IF NOT EXISTS idx_spots_active_until   ON public.spots (active_until DESC) WHERE NOT hidden;
CREATE INDEX IF NOT EXISTS idx_spots_posted_by      ON public.spots (posted_by, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_spots_vibe_active    ON public.spots (vibe, active_until DESC) WHERE NOT hidden AND active_until > NOW();
CREATE INDEX IF NOT EXISTS idx_spots_trending       ON public.spots (joins_count DESC, created_at DESC) WHERE NOT hidden AND active_until > NOW();

-- ── 2. TABELA spot_joins (kto dołączył) ─────────────────────────────────
CREATE TABLE IF NOT EXISTS public.spot_joins (
  id         BIGSERIAL PRIMARY KEY,
  spot_id    BIGINT NOT NULL REFERENCES public.spots(id) ON DELETE CASCADE,
  user_id    UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  left_at    TIMESTAMPTZ,                        -- NULL = nadal w spocie
  UNIQUE(spot_id, user_id)                       -- nie można dołączyć 2x
);

CREATE INDEX IF NOT EXISTS idx_spot_joins_spot     ON public.spot_joins(spot_id) WHERE left_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_spot_joins_user     ON public.spot_joins(user_id, joined_at DESC);

-- ── 3. TRIGGER: auto-update joins_count na spots ────────────────────────
CREATE OR REPLACE FUNCTION public.update_spot_joins_count()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE public.spots
      SET joins_count = (
        SELECT COUNT(*) FROM public.spot_joins
        WHERE spot_id = NEW.spot_id AND left_at IS NULL
      )
      WHERE id = NEW.spot_id;
    RETURN NEW;
  ELSIF TG_OP = 'UPDATE' THEN
    -- Jeśli ktoś opuścił (left_at zmieniony z NULL na timestamp)
    IF OLD.left_at IS NULL AND NEW.left_at IS NOT NULL THEN
      UPDATE public.spots
        SET joins_count = GREATEST(0, joins_count - 1)
        WHERE id = NEW.spot_id;
    END IF;
    RETURN NEW;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE public.spots
      SET joins_count = GREATEST(0, joins_count - 1)
      WHERE id = OLD.spot_id;
    RETURN OLD;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_spot_joins_count ON public.spot_joins;
CREATE TRIGGER trg_spot_joins_count
  AFTER INSERT OR UPDATE OR DELETE ON public.spot_joins
  FOR EACH ROW EXECUTE FUNCTION public.update_spot_joins_count();

-- ── 4. AUTO-JOIN postera (gdy ktoś tworzy spot, jest pierwszym uczestnikiem) ─
CREATE OR REPLACE FUNCTION public.auto_join_spot_creator()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.spot_joins (spot_id, user_id) VALUES (NEW.id, NEW.posted_by)
    ON CONFLICT DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_auto_join_creator ON public.spots;
CREATE TRIGGER trg_auto_join_creator
  AFTER INSERT ON public.spots
  FOR EACH ROW EXECUTE FUNCTION public.auto_join_spot_creator();

-- ── 5. RLS ──────────────────────────────────────────────────────────────
ALTER TABLE public.spots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.spot_joins ENABLE ROW LEVEL SECURITY;

-- Spots: każdy widzi aktywne, niezflagowane, nieukryte
DROP POLICY IF EXISTS "anyone_reads_active_spots" ON public.spots;
CREATE POLICY "anyone_reads_active_spots" ON public.spots
  FOR SELECT USING (NOT hidden);

-- Spots: zalogowany user pisze swoje
DROP POLICY IF EXISTS "user_creates_own_spots" ON public.spots;
CREATE POLICY "user_creates_own_spots" ON public.spots
  FOR INSERT WITH CHECK (auth.uid() = posted_by);

-- Spots: właściciel + admin może edytować
DROP POLICY IF EXISTS "owner_updates_own_spots" ON public.spots;
CREATE POLICY "owner_updates_own_spots" ON public.spots
  FOR UPDATE USING (
    auth.uid() = posted_by
    OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = TRUE)
  );

-- Spots: właściciel + admin może usuwać
DROP POLICY IF EXISTS "owner_deletes_own_spots" ON public.spots;
CREATE POLICY "owner_deletes_own_spots" ON public.spots
  FOR DELETE USING (
    auth.uid() = posted_by
    OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND is_admin = TRUE)
  );

-- Spot_joins: każdy zalogowany widzi (do wyświetlenia avatarów uczestników)
DROP POLICY IF EXISTS "anyone_reads_spot_joins" ON public.spot_joins;
CREATE POLICY "anyone_reads_spot_joins" ON public.spot_joins
  FOR SELECT USING (true);

-- Spot_joins: user dołącza tylko jako sam
DROP POLICY IF EXISTS "user_joins_self" ON public.spot_joins;
CREATE POLICY "user_joins_self" ON public.spot_joins
  FOR INSERT WITH CHECK (auth.uid() = user_id);

-- Spot_joins: user opuszcza tylko swoje
DROP POLICY IF EXISTS "user_leaves_self" ON public.spot_joins;
CREATE POLICY "user_leaves_self" ON public.spot_joins
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "user_deletes_own_join" ON public.spot_joins;
CREATE POLICY "user_deletes_own_join" ON public.spot_joins
  FOR DELETE USING (auth.uid() = user_id);

-- ── 6. WIDOK v_spots_active (dla mapy + trending) ──────────────────────
CREATE OR REPLACE VIEW public.v_spots_active AS
SELECT
  s.id,
  s.posted_by,
  s.lat,
  s.lng,
  s.photo_url,
  s.description,
  s.vibe,
  s.joins_count,
  s.views_count,
  s.active_until,
  s.created_at,
  s.place_id,
  EXTRACT(EPOCH FROM (s.active_until - NOW()))::INT AS seconds_left,
  pr.display_name AS posted_by_name,
  pr.avatar_2d_url AS posted_by_avatar,
  pl.name AS place_name
FROM public.spots s
LEFT JOIN public.profiles pr ON pr.id = s.posted_by
LEFT JOIN public.places pl ON pl.id = s.place_id
WHERE NOT s.hidden AND s.active_until > NOW();

-- ── 7. FUNKCJA spots_nearby (dla mapy: query po radiusie km) ──────────
-- Używa Haversine bez PostGIS (działa wszędzie)
CREATE OR REPLACE FUNCTION public.spots_nearby(
  p_lat NUMERIC,
  p_lng NUMERIC,
  p_radius_km NUMERIC DEFAULT 5,
  p_limit INT DEFAULT 100
)
RETURNS TABLE (
  id BIGINT,
  lat NUMERIC,
  lng NUMERIC,
  photo_url TEXT,
  description TEXT,
  vibe TEXT,
  joins_count INT,
  active_until TIMESTAMPTZ,
  posted_by_name TEXT,
  posted_by_avatar TEXT,
  place_name TEXT,
  distance_km NUMERIC,
  seconds_left INT
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    v.id, v.lat, v.lng, v.photo_url, v.description, v.vibe, v.joins_count,
    v.active_until, v.posted_by_name, v.posted_by_avatar, v.place_name,
    ROUND((6371 * acos(
      LEAST(1.0, GREATEST(-1.0,
        cos(radians(p_lat)) * cos(radians(v.lat)) *
        cos(radians(v.lng) - radians(p_lng)) +
        sin(radians(p_lat)) * sin(radians(v.lat))
      ))
    ))::NUMERIC, 2) AS distance_km,
    v.seconds_left
  FROM public.v_spots_active v
  WHERE (
    -- Bounding box pre-filter (szybki, używa indeksu)
    v.lat BETWEEN p_lat - (p_radius_km / 111.0)
              AND p_lat + (p_radius_km / 111.0)
    AND v.lng BETWEEN p_lng - (p_radius_km / (111.0 * COS(RADIANS(p_lat))))
                  AND p_lng + (p_radius_km / (111.0 * COS(RADIANS(p_lat))))
  )
  ORDER BY distance_km ASC, v.joins_count DESC
  LIMIT p_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.spots_nearby(NUMERIC, NUMERIC, NUMERIC, INT) TO authenticated, anon;

-- ── 8. FUNKCJA spots_trending (top spotów dziś w okolicy) ──────────────
CREATE OR REPLACE FUNCTION public.spots_trending(
  p_lat NUMERIC,
  p_lng NUMERIC,
  p_radius_km NUMERIC DEFAULT 10,
  p_limit INT DEFAULT 10
)
RETURNS TABLE (
  id BIGINT,
  lat NUMERIC,
  lng NUMERIC,
  photo_url TEXT,
  description TEXT,
  vibe TEXT,
  joins_count INT,
  posted_by_name TEXT,
  posted_by_avatar TEXT,
  place_name TEXT,
  distance_km NUMERIC,
  seconds_left INT,
  trending_score NUMERIC
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT
    n.id, n.lat, n.lng, n.photo_url, n.description, n.vibe, n.joins_count,
    n.posted_by_name, n.posted_by_avatar, n.place_name,
    n.distance_km, n.seconds_left,
    -- Trending score: joins_count * recency_boost / distance_penalty
    ROUND((
      n.joins_count::NUMERIC
      * (1.0 + GREATEST(0, n.seconds_left::NUMERIC / 21600))   -- max boost dla świeżych (6h = 21600s)
      / (1.0 + n.distance_km * 0.5)                              -- penalty za odległość
    ), 2) AS trending_score
  FROM public.spots_nearby(p_lat, p_lng, p_radius_km, 200) n
  ORDER BY trending_score DESC
  LIMIT p_limit;
END;
$$;

GRANT EXECUTE ON FUNCTION public.spots_trending(NUMERIC, NUMERIC, NUMERIC, INT) TO authenticated, anon;

-- ── 9. FUNKCJA join_spot / leave_spot (bezpieczne RPC) ─────────────────
CREATE OR REPLACE FUNCTION public.join_spot(p_spot_id BIGINT)
RETURNS public.spot_joins
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_uid UUID := auth.uid();
  v_row public.spot_joins;
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'Not authenticated'; END IF;
  IF NOT EXISTS (SELECT 1 FROM public.spots WHERE id = p_spot_id AND active_until > NOW() AND NOT hidden) THEN
    RAISE EXCEPTION 'Spot not active';
  END IF;
  INSERT INTO public.spot_joins (spot_id, user_id) VALUES (p_spot_id, v_uid)
    ON CONFLICT (spot_id, user_id) DO UPDATE SET left_at = NULL
    RETURNING * INTO v_row;
  RETURN v_row;
END;
$$;
GRANT EXECUTE ON FUNCTION public.join_spot(BIGINT) TO authenticated;

CREATE OR REPLACE FUNCTION public.leave_spot(p_spot_id BIGINT)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_uid UUID := auth.uid();
BEGIN
  IF v_uid IS NULL THEN RAISE EXCEPTION 'Not authenticated'; END IF;
  UPDATE public.spot_joins SET left_at = NOW()
    WHERE spot_id = p_spot_id AND user_id = v_uid AND left_at IS NULL;
  RETURN FOUND;
END;
$$;
GRANT EXECUTE ON FUNCTION public.leave_spot(BIGINT) TO authenticated;

-- ── 10. REALTIME ────────────────────────────────────────────────────────
-- Włącz Realtime dla obu tabel (Supabase Dashboard musi mieć Realtime ON)
ALTER PUBLICATION supabase_realtime ADD TABLE public.spots;
ALTER PUBLICATION supabase_realtime ADD TABLE public.spot_joins;

COMMENT ON TABLE public.spots IS 'TribeSpot: efemeryczne spoty od userów. Auto-expire po active_until (default 6h). Realtime ON.';
COMMENT ON FUNCTION public.spots_nearby IS 'Spoty w okolicy (radius km). Haversine bez PostGIS. Sortowanie: distance ASC, joins DESC.';
COMMENT ON FUNCTION public.spots_trending IS 'Top spoty dziś w okolicy. Score = joins * recency_boost / distance_penalty.';
