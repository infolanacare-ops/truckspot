-- TS PRO: Rozszerzenie typów zadań + 12 nowych wzorcowych
-- Data: 2026-04-30
-- Nowe typy: workout, mood_checkin, donation, eco, art, learn, safe_drive, route, event_attend, team, mystery
-- + Photo: najlepszy widok / foto-quest
-- + Quiz: trivia weekend
-- + Social: zaproś / pierwsze DM / wspólny spacer

-- ── 1. ROZSZERZENIE SCHEMY ─────────────────────────────────────────────────
-- Dodaj task_meta JSONB dla danych specyficznych typu (foto-quest items, quiz pytania, route GeoJSON, team członkowie...)
ALTER TABLE public.tasks
  ADD COLUMN IF NOT EXISTS task_meta JSONB DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS verify_method TEXT DEFAULT 'auto',  -- 'auto' | 'photo' | 'manual_admin' | 'quiz' | 'community_vote'
  ADD COLUMN IF NOT EXISTS difficulty TEXT DEFAULT 'normal',   -- 'easy' | 'normal' | 'hard' | 'epic'
  ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'public';   -- 'public' | 'friends_only' | 'premium'

-- Komentarz aktualizujący spis typów
COMMENT ON COLUMN public.tasks.type IS 'steps | visit | photo | video | quiz | social | shop_online | workout | mood_checkin | donation | eco | art | learn | safe_drive | route | event_attend | team | mystery';
COMMENT ON COLUMN public.tasks.verify_method IS 'auto = system; photo = upload + AI/manual; manual_admin = admin akceptuje; quiz = answer match; community_vote = top X głosów';
COMMENT ON COLUMN public.tasks.task_meta IS 'JSONB specyficzne dla typu, np. quiz {questions:[]}, foto-quest {items:[]}, route {geojson:...}, team {members_required:N, member_ids:[]}';

-- ── 2. WZORCOWE ZADANIA ──────────────────────────────────────────────────

-- 📸 PHOTO — Najlepszy widok (community vote)
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '📸 Najlepszy widok tygodnia',
    'Wrzuć zdjęcie z punktu widokowego w swoim mieście. Top 10 najczęściej lajkowanych zdobywa nagrody!',
    '📸',
    'system',
    'photo',
    'weekly',
    1, 'zdjęć', 300, 'community_vote', 'normal',
    '📷', '#ec4899',
    '{"voting_ends_at_iso":"weekly_sunday_22","min_likes_for_xp":5,"top_n_winners":10,"prize_xp_top1":500}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- 📸 PHOTO — Foto-quest (5 obiektów do sfocowania)
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '🔍 Foto-quest: Sieradz odkryty',
    'Sfocuj 5 ikonicznych obiektów Sieradza: Zamek, Rynek, Park Praszka, Most na Warcie, Mural Stara Synagoga.',
    '🗺️',
    'system',
    'photo',
    'weekly',
    5, 'zdjęć', 400, 'auto', 'normal',
    '🎯', '#f59e0b',
    '{"items":[{"name":"Zamek","lat":51.5985,"lng":18.7301,"radius_m":50},{"name":"Rynek","lat":51.5963,"lng":18.7320,"radius_m":40},{"name":"Park Praszka","lat":51.5955,"lng":18.7268,"radius_m":80},{"name":"Most Warta","lat":51.5990,"lng":18.7350,"radius_m":60},{"name":"Synagoga","lat":51.5970,"lng":18.7295,"radius_m":40}]}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- ❓ QUIZ — Trivia Weekend (niedzielny live)
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '🧠 Trivia Weekend — Niedziela 20:00',
    '10 pytań o Polsce, popkulturze, twoim mieście. Top 3 zdobywa nagrody, każdy >70% bonus XP!',
    '🧠',
    'live',
    'quiz',
    10, 'pytań', 500, 'quiz', 'normal',
    '🏆', '#a855f7',
    '{"start_iso":"sunday_20:00","duration_min":15,"questions":[{"q":"W którym roku powstał Sieradz?","a":"1233","options":["1153","1233","1353","1410"]},{"q":"Jaka rzeka przepływa przez Sieradz?","a":"Warta","options":["Warta","Wisła","Odra","Bug"]}],"top3_xp":[1000,700,500]}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- 👥 SOCIAL — Zaproś 3 ziomków
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '👥 Przyprowadź 3 ziomków',
    'Zaproś znajomych do TS PRO. Za każdego nowego usera dostajesz +200 XP. 3 = bonus +500 XP!',
    '👥',
    'system',
    'social',
    3, 'osób', 600, 'auto', 'easy',
    '🚀', '#3b82f6',
    '{"action":"referral","reward_per_invite_xp":200,"bonus_at_3_xp":500}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 👥 SOCIAL — Pierwsze DM
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '💬 Pierwszy lód',
    'Wyślij wiadomość komuś nowemu (nie był w twoich znajomych). Złam pierwsze lody!',
    '💬',
    'system',
    'social',
    1, 'wiadomości', 100, 'auto', 'easy',
    '🧊', '#06b6d4',
    '{"action":"first_dm_to_stranger"}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 👥 SOCIAL — Wspólny spacer
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '🚶 Wspólny spacer',
    'Bądź razem ze znajomym min. 30 minut w odległości <50m. Bonus jeśli >5km kroków razem!',
    '🚶',
    'system',
    'social',
    30, 'min', 300, 'auto', 'normal',
    '👯', '#10b981',
    '{"action":"co_walk","min_distance_to_friend_m":50,"min_minutes":30,"bonus_steps_5km_xp":200}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 💪 WORKOUT — Yoga 30 min
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '🧘 Yoga 30 minut',
    'Codzienny stretching/yoga 30 min — wyzwoli endorfiny i uspokoi umysł. Wymaga zdjęcia maty + selfie.',
    '🧘',
    'system',
    'workout',
    30, 'min', 200, 'photo', 'easy',
    '🌸', '#ec4899',
    '{"workout_type":"yoga","proof":"selfie_with_mat"}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 😊 MOOD CHECKIN — emoji nastroju
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '😊 Mood check-in',
    'Wybierz emoji nastroju dziś. Streak 7 dni dobrego nastroju = badge "Good Vibes".',
    '😊',
    'system',
    'mood_checkin',
    1, 'check-in', 30, 'auto', 'easy',
    '✨', '#fbbf24',
    '{"emojis":["😄","😊","😐","😢","😡","🤩","🥰","😴","🤔"],"streak_7_badge":"good_vibes"}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 💝 DONATION — Tydzień pomocy
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '💝 Tydzień pomocy: 5 zł na schronisko',
    'Wpłać minimum 5 zł na schronisko dla zwierząt w Sieradzu. Badge "Anioł" + 500 XP.',
    '💝',
    'live',
    'donation',
    5, 'zł', 500, 'manual_admin', 'easy',
    '🐕', '#ef4444',
    '{"charity":"Schronisko Sieradz","payment_url":"https://schronisko-sieradz.pl/wplac","min_amount_zl":5,"badge":"angel"}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- ♻️ ECO — Recykling
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '♻️ Eko-bohater: 5 butelek do PET-a',
    'Sfocuj 5 plastikowych butelek wrzucanych do recyklomatu. XP + szansa na voucher.',
    '♻️',
    'system',
    'eco',
    5, 'butelek', 250, 'photo', 'easy',
    '🌱', '#10b981',
    '{"recycling_machines_only":true,"bonus_for_glass":true}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 🎨 ART — Mural tygodnia
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '🎨 Mural Tygodnia — Sieradz Street Art',
    'Sfocuj nowy mural i napisz krótki opis (kto, gdzie, kiedy). Najlepszy opis = +500 XP.',
    '🎨',
    'live',
    'art',
    1, 'zdjęcie+opis', 300, 'community_vote', 'normal',
    '🖼️', '#8b5cf6',
    '{"category":"street_art","description_min_chars":50,"top_post_bonus_xp":500}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- 📚 LEARN — Podcast 3 odcinki
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '🎧 Podcast Master: 3 odcinki tygodniowo',
    'Wysłuchaj 3 odcinków podcastu (dowolny temat — nauka, biznes, podróże). Self-report + screenshot.',
    '🎧',
    'system',
    'learn',
    3, 'odcinków', 200, 'photo', 'easy',
    '📚', '#0ea5e9',
    '{"proof":"screenshot_app_progress","topics":["nauka","biznes","podróże","historia","tech"]}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 🛡️ SAFE DRIVE — Tydzień bez wykroczeń (integruje się z istniejącym sd.points)
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '🛡️ Bezpieczny kierowca tygodnia',
    'Tydzień bez przekroczenia +50 km/h. Punkty z modułu nawigacji liczą się automatycznie.',
    '🛡️',
    'system',
    'safe_drive',
    7, 'dni bez wykr.', 700, 'auto', 'normal',
    '🚦', '#d4af37',
    '{"max_speeding_events":0,"min_km_driven":50}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 🥾 ROUTE — Pieszy szlak Warty
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active)
VALUES
  (
    '🥾 Pieszy szlak Warty — 10 km',
    'Pokonaj cały szlak nadwarciańskiego deptaka pieszo. GPS śledzi trasę, na końcu badge "Wędrowiec".',
    '🥾',
    'system',
    'route',
    10000, 'metrów', 800, 'auto', 'hard',
    '🗺️', '#059669',
    '{"route_geojson_url":"/static/routes/szlak_warty.geojson","tolerance_m":50,"min_speed_kmh":2,"max_speed_kmh":8,"badge":"wedrowiec"}'::jsonb,
    TRUE
  )
ON CONFLICT DO NOTHING;

-- 🎤 EVENT ATTEND — Koncert / mecz / festiwal
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '🎤 Bądź na evencie tego tygodnia',
    'Pojaw się na liście wydarzeń (koncerty, mecze, festiwale). Geofence + 30 min obecności = XP.',
    '🎤',
    'live',
    'event_attend',
    30, 'min', 400, 'auto', 'normal',
    '🎉', '#f97316',
    '{"events_source":"places_with_event_flag","min_dwell_min":30}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- 👯 TEAM — Wspólny cel grupy
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, ends_at)
VALUES
  (
    '👯 Drużyna 100k kroków',
    'Razem z 2 znajomymi nazbierajcie 100 000 kroków w tygodniu. Każdy dostaje 1000 XP gdy osiągniecie cel.',
    '👯',
    'system',
    'team',
    100000, 'kroków zespołu', 1000, 'auto', 'hard',
    '🏆', '#fbbf24',
    '{"team_size_required":3,"team_steps_total":100000,"each_member_xp_on_complete":1000}'::jsonb,
    TRUE, NOW() + INTERVAL '7 days'
  )
ON CONFLICT DO NOTHING;

-- 🕵️ MYSTERY — Hidden task (Pokemon Go fog of war)
INSERT INTO public.tasks
  (title, description, emoji, source, type, horizon, goal_value, goal_unit, xp_reward, verify_method, difficulty, banner_emoji, banner_color, task_meta, active, lat, lng, trigger_radius_m, hidden_until_nearby)
VALUES
  (
    '🕵️ ???',
    'Coś tu jest ukryte... Zbliż się do tajemniczej lokalizacji w centrum, by odkryć zadanie.',
    '🕵️',
    'system',
    'mystery',
    1, 'odkrycie', 1000, 'auto', 'epic',
    '👁️', '#7c3aed',
    '{"reveal_text":"Tajemnica Sieradza: Znajdź skarb pod zegarem ratuszowym. Sfocuj go z dokładną godziną wskazaną na tarczy.","hint_radius_m":300,"unlock_action":"photo","real_task_emoji":"⏰"}'::jsonb,
    TRUE,
    51.5963, 18.7320, 30,  -- Rynek Sieradz
    TRUE
  )
ON CONFLICT DO NOTHING;

-- ── 3. INDEKS na nowe pola ────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_tasks_difficulty ON public.tasks(difficulty, active);
CREATE INDEX IF NOT EXISTS idx_tasks_visibility ON public.tasks(visibility, active);
CREATE INDEX IF NOT EXISTS idx_tasks_verify ON public.tasks(verify_method);

-- Komentarz końcowy
COMMENT ON COLUMN public.tasks.difficulty IS 'easy/normal/hard/epic — wpływa na mnożnik XP w przyszłości';
COMMENT ON COLUMN public.tasks.visibility IS 'public/friends_only/premium — kontrola dostępu';
