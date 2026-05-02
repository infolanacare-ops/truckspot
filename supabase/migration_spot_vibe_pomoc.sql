-- ── Faza E1 misji Areny: kategoria spotów "🤝 Pomoc" ─────────────────────────
-- Dodaje nową kategorię vibe='pomoc' do tabeli spots
-- Score 8.0 w matrycy priorytetów strategy_systemic_roadmap
-- 02.05.2026
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Update CHECK constraint na kolumnie vibe
ALTER TABLE public.spots DROP CONSTRAINT IF EXISTS spots_vibe_check;

ALTER TABLE public.spots ADD CONSTRAINT spots_vibe_check
  CHECK (vibe IN ('party','chill','food','sport','view','queue','event','other','pomoc'));

-- 2. Index dla szybkiego filtrowania spotów Pomoc (Arena dashboard)
CREATE INDEX IF NOT EXISTS idx_spots_pomoc_active
  ON public.spots (active_until DESC)
  WHERE NOT hidden AND active_until > NOW() AND vibe = 'pomoc';

-- 3. Komentarz do dokumentacji w bazie
COMMENT ON COLUMN public.spots.vibe IS
  'Kategoria spota: party|chill|food|sport|view|queue|event|other|pomoc (od 02.05.2026: pomoc = misja Areny Bohaterów)';
