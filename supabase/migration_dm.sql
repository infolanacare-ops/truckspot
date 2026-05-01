-- Migracja: Private Messages (DM między znajomymi)
-- Uruchom w Supabase → SQL Editor → Run

-- 1. Tabela wiadomości
CREATE TABLE IF NOT EXISTS public.private_messages (
  id BIGSERIAL PRIMARY KEY,
  from_user UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  to_user   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  body TEXT,
  msg_type TEXT NOT NULL DEFAULT 'text',  -- 'text' | 'pin' | 'meet_request'
  meta JSONB DEFAULT '{}'::jsonb,         -- {lat, lng, label, etc.}
  created_at TIMESTAMPTZ DEFAULT NOW(),
  read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pm_pair_time ON public.private_messages (LEAST(from_user,to_user), GREATEST(from_user,to_user), created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pm_to_unread ON public.private_messages (to_user, read_at) WHERE read_at IS NULL;

-- 2. RLS
ALTER TABLE public.private_messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "pm_read_own" ON public.private_messages;
CREATE POLICY "pm_read_own" ON public.private_messages
  FOR SELECT USING (auth.uid() = from_user OR auth.uid() = to_user);

DROP POLICY IF EXISTS "pm_send_to_friend" ON public.private_messages;
CREATE POLICY "pm_send_to_friend" ON public.private_messages
  FOR INSERT WITH CHECK (
    auth.uid() = from_user
    AND EXISTS (
      SELECT 1 FROM public.friendships f
      WHERE f.status = 'accepted'
        AND ((f.from_user = auth.uid() AND f.to_user = NEW.to_user)
          OR (f.to_user   = auth.uid() AND f.from_user = NEW.to_user))
    )
  );

DROP POLICY IF EXISTS "pm_mark_read" ON public.private_messages;
CREATE POLICY "pm_mark_read" ON public.private_messages
  FOR UPDATE USING (auth.uid() = to_user) WITH CHECK (auth.uid() = to_user);

-- 3. Realtime
ALTER PUBLICATION supabase_realtime ADD TABLE public.private_messages;

SELECT 'OK — private_messages gotowe' AS status;
