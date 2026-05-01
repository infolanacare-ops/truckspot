-- Migracja: Streaks 🔥 — zliczanie dni z rzędu z obustronną interakcją
-- Uruchom w Supabase → SQL Editor → Run

-- 1. Kolumny w friendships
ALTER TABLE public.friendships
  ADD COLUMN IF NOT EXISTS streak_days INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS streak_last_day DATE,
  ADD COLUMN IF NOT EXISTS last_msg_from_date DATE,
  ADD COLUMN IF NOT EXISTS last_msg_to_date DATE,
  ADD COLUMN IF NOT EXISTS msg_count_total INT DEFAULT 0;

-- 2. Trigger function — na każdy nowy DM aktualizuj streak
CREATE OR REPLACE FUNCTION public.update_friendship_streak()
RETURNS TRIGGER AS $$
DECLARE
  fr RECORD;
  today DATE := CURRENT_DATE;
  yesterday DATE := CURRENT_DATE - 1;
BEGIN
  SELECT id, from_user, to_user, streak_days, streak_last_day, last_msg_from_date, last_msg_to_date
  INTO fr
  FROM public.friendships
  WHERE status = 'accepted'
    AND ((from_user = NEW.from_user AND to_user = NEW.to_user)
      OR (from_user = NEW.to_user AND to_user = NEW.from_user))
  LIMIT 1;

  IF NOT FOUND THEN RETURN NEW; END IF;

  -- Zwiększ licznik wiadomości i zapisz datę ostatniego msg dla tej strony
  IF NEW.from_user = fr.from_user THEN
    UPDATE public.friendships
       SET last_msg_from_date = today, msg_count_total = COALESCE(msg_count_total,0) + 1
     WHERE id = fr.id;
    fr.last_msg_from_date := today;
  ELSE
    UPDATE public.friendships
       SET last_msg_to_date = today, msg_count_total = COALESCE(msg_count_total,0) + 1
     WHERE id = fr.id;
    fr.last_msg_to_date := today;
  END IF;

  -- Streak update tylko gdy OBOJE pisali dziś i streak jeszcze nie był dziś bumpnięty
  IF fr.last_msg_from_date = today
     AND fr.last_msg_to_date = today
     AND COALESCE(fr.streak_last_day, DATE '1900-01-01') < today THEN
    IF fr.streak_last_day = yesterday THEN
      UPDATE public.friendships
         SET streak_days = COALESCE(streak_days, 0) + 1, streak_last_day = today
       WHERE id = fr.id;
    ELSE
      UPDATE public.friendships
         SET streak_days = 1, streak_last_day = today
       WHERE id = fr.id;
    END IF;
  END IF;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS pm_update_streak ON public.private_messages;
CREATE TRIGGER pm_update_streak
  AFTER INSERT ON public.private_messages
  FOR EACH ROW
  EXECUTE FUNCTION public.update_friendship_streak();

-- 3. Daj read-only dostęp na te pola dla zalogowanych userów (RLS już jest na friendships)
SELECT 'OK — streaks gotowe' AS status;
