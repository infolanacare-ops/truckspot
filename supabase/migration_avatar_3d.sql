-- TS PRO: Avatar 3D (Avaturn / RPM / VRM) ─ 2026-04-29
-- Dodaje pola dla GLB url + meta (provider, source: selfie/preset)
-- Bezpieczne: ALTER TABLE ... ADD COLUMN IF NOT EXISTS

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS avatar_2d_url   TEXT,           -- DiceBear PNG / snapshot 3D → PNG
  ADD COLUMN IF NOT EXISTS avatar_3d_url   TEXT,           -- pełny GLB / VRM
  ADD COLUMN IF NOT EXISTS avatar_provider TEXT,           -- 'dicebear' | 'avaturn' | 'rpm' | 'custom'
  ADD COLUMN IF NOT EXISTS avatar_meta     JSONB DEFAULT '{}'::jsonb;

-- Indeks żeby szybko filtrować userów którzy mają avatar 3D (ranking, reklama tej funkcji)
CREATE INDEX IF NOT EXISTS idx_profiles_has_3d
  ON public.profiles ((avatar_3d_url IS NOT NULL));

COMMENT ON COLUMN public.profiles.avatar_3d_url   IS 'URL do GLB/VRM (Avaturn, RPM, custom). Null = brak avatara 3D.';
COMMENT ON COLUMN public.profiles.avatar_provider IS 'avaturn | rpm | dicebear | custom';
COMMENT ON COLUMN public.profiles.avatar_meta     IS 'JSONB: { source: "selfie"|"preset", style, seed, generated_at, ... }';
