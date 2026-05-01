-- Migracja: dodaj email do profiles + auto-sync z auth.users
-- Uruchom w Supabase → SQL Editor → Run

-- 1. Kolumna email
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS email TEXT;
CREATE INDEX IF NOT EXISTS idx_profiles_email ON public.profiles (LOWER(email));
CREATE INDEX IF NOT EXISTS idx_profiles_display_name ON public.profiles (LOWER(display_name));

-- 2. Backfill istniejących userów z auth.users
UPDATE public.profiles p
SET email = u.email
FROM auth.users u
WHERE p.id = u.id AND (p.email IS NULL OR p.email = '');

-- 3. Trigger: gdy ktoś nowy zakłada profil, skopiuj email z auth.users
CREATE OR REPLACE FUNCTION public.set_profile_email_from_auth()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.email IS NULL OR NEW.email = '' THEN
    NEW.email := (SELECT email FROM auth.users WHERE id = NEW.id);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS profiles_set_email_trigger ON public.profiles;
CREATE TRIGGER profiles_set_email_trigger
  BEFORE INSERT OR UPDATE ON public.profiles
  FOR EACH ROW
  EXECUTE FUNCTION public.set_profile_email_from_auth();

-- 4. Trigger: gdy ktoś rejestruje się (auth.users INSERT), utwórz profile z emailem
CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, display_name)
  VALUES (NEW.id, NEW.email, COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(NEW.email, '@', 1)))
  ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_auth_user();

-- 5. Sprawdź wynik
SELECT id, display_name, email FROM public.profiles ORDER BY created_at DESC LIMIT 10;
