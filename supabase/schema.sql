-- TruckSpot — schemat bazy danych
-- Uruchom w Supabase → SQL Editor → New query

-- ── TABELE ───────────────────────────────────────────────────────────────────

CREATE TABLE public.profiles (
    id UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
    display_name TEXT,
    truck_type TEXT DEFAULT 'standard',
    truck_height_m NUMERIC(4,2),
    truck_weight_t NUMERIC(5,1),
    truck_width_m NUMERIC(4,2),
    country TEXT DEFAULT 'PL',
    language TEXT DEFAULT 'pl',
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.parkings (
    id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    lat NUMERIC(10,6) NOT NULL,
    lng NUMERIC(10,6) NOT NULL,
    type TEXT[] DEFAULT '{}',
    country TEXT,
    city TEXT,
    address TEXT,
    spots_tir INTEGER DEFAULT 0,
    spots_camper INTEGER DEFAULT 0,
    amenities TEXT[] DEFAULT '{}',
    price_eur NUMERIC(8,2) DEFAULT 0,
    rating NUMERIC(3,1),
    status TEXT DEFAULT 'open',
    poi JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.markets (
    id BIGINT PRIMARY KEY,
    name TEXT,
    city TEXT,
    state TEXT,
    region TEXT,
    address TEXT,
    lat NUMERIC(10,6),
    lng NUMERIC(10,6),
    type TEXT,
    schedule TEXT,
    recurring BOOLEAN DEFAULT FALSE,
    recurring_day TEXT,
    dates JSONB,
    time_from TEXT,
    time_to TEXT,
    website TEXT,
    description TEXT,
    indoor BOOLEAN DEFAULT FALSE,
    free_entry BOOLEAN DEFAULT TRUE,
    parking BOOLEAN DEFAULT FALSE,
    country TEXT
);

CREATE TABLE public.scenic_spots (
    id BIGINT PRIMARY KEY,
    name TEXT,
    country TEXT,
    region TEXT,
    lat NUMERIC(10,6),
    lng NUMERIC(10,6),
    type TEXT,
    description TEXT,
    elevation INTEGER,
    best_season TEXT,
    parking BOOLEAN DEFAULT FALSE,
    free_entry BOOLEAN DEFAULT TRUE,
    website TEXT
);

CREATE TABLE public.user_favorites (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    spot_type TEXT NOT NULL,  -- 'parking' | 'market' | 'scenic'
    spot_id BIGINT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, spot_type, spot_id)
);

CREATE TABLE public.ai_conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE public.parking_reviews (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    parking_id BIGINT REFERENCES public.parkings(id) ON DELETE CASCADE,
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, parking_id)
);

-- ── INDEKSY ───────────────────────────────────────────────────────────────────

CREATE INDEX idx_parkings_country ON public.parkings(country);
CREATE INDEX idx_parkings_lat_lng ON public.parkings(lat, lng);
CREATE INDEX idx_parkings_type ON public.parkings USING GIN(type);
CREATE INDEX idx_parkings_amenities ON public.parkings USING GIN(amenities);
CREATE INDEX idx_ai_conversations_user ON public.ai_conversations(user_id, created_at DESC);
CREATE INDEX idx_user_favorites_user ON public.user_favorites(user_id);

-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parkings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.markets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scenic_spots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_favorites ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.parking_reviews ENABLE ROW LEVEL SECURITY;

-- Profiles: tylko swój profil
CREATE POLICY "profile_select_own" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profile_insert_own" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profile_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);

-- Parkings / markets / scenic: publiczny odczyt
CREATE POLICY "parkings_public_read" ON public.parkings FOR SELECT USING (true);
CREATE POLICY "markets_public_read" ON public.markets FOR SELECT USING (true);
CREATE POLICY "scenic_public_read" ON public.scenic_spots FOR SELECT USING (true);

-- Favorites: właściciel zarządza
CREATE POLICY "favorites_own" ON public.user_favorites FOR ALL USING (auth.uid() = user_id);

-- AI conversations: prywatne
CREATE POLICY "ai_conv_own" ON public.ai_conversations FOR ALL USING (auth.uid() = user_id);

-- Reviews: publiczny odczyt, własne modyfikacje
CREATE POLICY "reviews_public_read" ON public.parking_reviews FOR SELECT USING (true);
CREATE POLICY "reviews_own_write" ON public.parking_reviews FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "reviews_own_update" ON public.parking_reviews FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "reviews_own_delete" ON public.parking_reviews FOR DELETE USING (auth.uid() = user_id);

-- ── AUTO-PROFIL PRZY REJESTRACJI ──────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, display_name, country)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email, '@', 1)),
        COALESCE(NEW.raw_user_meta_data->>'country', 'PL')
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();


-- ══════════════════════════════════════════════════════════════════
-- FRIENDSHIPS — system znajomych (TS PRO Metaverse)
-- ══════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS public.friendships (
  id          BIGSERIAL PRIMARY KEY,
  from_user   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  to_user     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  status      TEXT NOT NULL DEFAULT 'pending', -- pending / accepted / rejected / blocked
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  UNIQUE(from_user, to_user)
);
CREATE INDEX IF NOT EXISTS idx_friendships_from ON public.friendships(from_user, status);
CREATE INDEX IF NOT EXISTS idx_friendships_to   ON public.friendships(to_user, status);

ALTER TABLE public.friendships ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users see own friendships"   ON public.friendships FOR SELECT
  USING (auth.uid() = from_user OR auth.uid() = to_user);
CREATE POLICY "users send friend requests"  ON public.friendships FOR INSERT
  WITH CHECK (auth.uid() = from_user);
CREATE POLICY "users update own friendships" ON public.friendships FOR UPDATE
  USING (auth.uid() = from_user OR auth.uid() = to_user);
CREATE POLICY "users delete own friendships" ON public.friendships FOR DELETE
  USING (auth.uid() = from_user OR auth.uid() = to_user);
