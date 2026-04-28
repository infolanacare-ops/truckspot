# TruckSpot PRO — Plan publikacji Google Play

## Stan aktualny
- APK release: `android/app/release/app-release.apk` — NIE podpisany (brak keystore)
- App ID: `com.truckspot.app`
- versionCode: 1, versionName: "1.0"

---

## KROK 1 — Keystore (podpis cyfrowy)

Wykonać RAZ na komputerze deweloperskim, zachować plik `.jks` w bezpiecznym miejscu!

```bash
keytool -genkey -v \
  -keystore truckspot-release.jks \
  -alias truckspot \
  -keyalg RSA -keysize 2048 \
  -validity 10000
```

Wypełnić:
- First/Last name: Krzysztof [nazwisko]
- Organization: TruckSpot
- Country: PL

**WAŻNE: Backup .jks + hasła — bez tego nie można aktualizować apki nigdy!**

---

## KROK 2 — Konfiguracja podpisu w build.gradle

Dodać do `android/app/build.gradle` w sekcji `android {}`:

```gradle
signingConfigs {
    release {
        storeFile file("../../truckspot-release.jks")
        storePassword "TWOJE_HASLO"
        keyAlias "truckspot"
        keyPassword "TWOJE_HASLO"
    }
}
buildTypes {
    release {
        signingConfig signingConfigs.release
        minifyEnabled false
        proguardFiles getDefaultProguardFile('proguard-android.txt'), 'proguard-rules.pro'
    }
}
```

---

## KROK 3 — Build AAB (Google Play wymaga AAB, nie APK)

```bash
cd android
./gradlew bundleRelease
```

Wynik: `android/app/build/outputs/bundle/release/app-release.aab`

---

## KROK 4 — Konto Google Play Developer

1. Wejdź: https://play.google.com/console
2. Zapłać $25 (jednorazowo)
3. Wypełnij dane firmy/osoby

---

## KROK 5 — Przygotowanie materiałów

### Screenshoty (wymagane)
- Minimum 2 screenshoty telefonu (1080x1920 lub 1920x1080)
- Opcjonalnie: tablet, Android Auto

### Ikona hi-res
- 512x512 PNG, bez zaokrąglonych rogów (Play sam zaokrągla)

### Grafika feature
- 1024x500 PNG — baner na górze strony w Play

### Krótki opis (max 80 znaków — appears under app icon w Play)
```
Nawigacja TIR która chroni Twoje prawo jazdy. +10 pkt dziennie za bezpieczną jazdę
```

### Opis PL (max 4000 znaków)
```
🛡️ TRUCKSPOT PRO — JEDYNA NAWIGACJA KTÓRA CHRONI TWOJE PRAWO JAZDY 🛡️

W Polsce przekroczenie prędkości o 50 km/h = automatyczne zatrzymanie prawa jazdy
na 3 miesiące + mandat 2000 zł + 15 punktów karnych. Dla młodych kierowców
(prawko <2 lata) = cofnięcie do egzaminu.

TruckSpot pilnuje Twojego prawka 24/7. Każdy dzień bez przekroczenia +50 km/h
to +10 punktów. Streak rośnie codziennie. Wymieniaj punkty na nagrody.

═══════════════════════════════════════════
🎯 SAFE DRIVE SHIELD — TWOJA TARCZA PRAWKA
═══════════════════════════════════════════
✅ Inteligentny alarm "ZWOLNIJ" gdy przekraczasz +50 km/h
✅ Eskalacja: pierwsze ostrzeżenie głosowe, potem komunikat o utracie prawka
✅ Codzienne punkty za bezpieczną jazdę (+10 pkt)
✅ Streak licznik dni z rzędu — buduj nawyk
✅ Statystyki po każdej trasie (km, przekroczenia, punkty)
✅ Wykres 14 dni — widzisz swój postęp

═══════════════════════════════════════════
🚛 NAWIGACJA DEDYKOWANA TIR (BUS, TURYSTA)
═══════════════════════════════════════════
✅ Routing HGV — trasy z uwzględnieniem wysokości, wagi, długości, szerokości
✅ Ograniczenia TIR na trasie — automatyczne ostrzeżenia (mosty, tunele, zakazy)
✅ HGV=NO i zakazy warunkowe (godzinowe) — pełne wsparcie OSM
✅ Parkingi TIR — 10 000+ z oceną bezpieczeństwa, 113 rynków hurtowych
✅ Stacje paliw z kartami flotowymi (DKV, UTA, AS24, E100, Shell, AdBlue)
✅ Fotoradary z potwierdzeniem przez kierowców (społecznościowa weryfikacja)
✅ Wybór 3 alternatywnych tras (najszybsza / najkrótsza / bez autostrad)

═══════════════════════════════════════════
🌐 SPOŁECZNOŚĆ KIEROWCÓW (METAVERSE)
═══════════════════════════════════════════
✅ CB Radio — czat z kierowcami w pobliżu w real-time
✅ Avatary innych kierowców na mapie z ich pozycją na żywo
✅ Strefy aktywności — gdzie jest najwięcej kierowców
✅ Zgłaszanie korków, kontroli, wypadków, robót

═══════════════════════════════════════════
🗺️ ZAAWANSOWANE FUNKCJE NAWIGACJI
═══════════════════════════════════════════
✅ Tryb 3.5D z budynkami i terenem
✅ Tryby mapy: 2D / 2.5D / 3.5D / Satelita / Ciemna / Z góry
✅ Polski głos lektora (Google Wavenet HD)
✅ Ostrzeżenia o korkach + automatyczne objazdy
✅ Lane Assist — pokazuje na który pas się ustawić
✅ Działa OFFLINE (cache trasy i parkingów)

═══════════════════════════════════════════
💎 DLA KOGO?
═══════════════════════════════════════════
🚛 Kierowcy TIR i busów — pełne wsparcie ograniczeń
🏎️ Młodzi kierowcy — chroni prawko (najwyższe ryzyko +50 km/h)
🚐 Kurierzy i logistyka — szybkie planowanie wielu przystanków
🏕️ Turyści i camperowcy — POI dla campingów, scenicznych miejsc

DOŁĄCZ DO TRUCKSPOT — JEDYNEJ NAWIGACJI KTÓRA WALCZY O TWOJE PRAWKO 🛡️
```

### Opis EN (max 4000 znaków)
```
🛡️ TRUCKSPOT PRO — THE ONLY NAVIGATION THAT SAVES YOUR DRIVING LICENSE 🛡️

In many EU countries, speeding +50 km/h = automatic license suspension + heavy fines.
TruckSpot monitors your speed 24/7 and rewards safe driving with daily points.

✅ Safe Drive Shield — voice alarm at +50 km/h with escalating warnings
✅ +10 points daily for staying safe — build a streak
✅ HGV routing — height, weight, length, width restrictions
✅ 10 000+ truck parking spots
✅ Speed cameras (community-verified)
✅ Fuel stations with fleet cards (DKV, UTA, AS24)
✅ CB Radio — real-time chat with nearby drivers
✅ 3.5D buildings, lane assist, traffic alerts
✅ Works OFFLINE
```

### Kategoria
- **Mapy i nawigacja** (główna)
- **Tag dodatkowy:** Bezpieczeństwo

### Ocena treści
- Wszyscy (PEGI 3 / IARC Everyone)

### Słowa kluczowe (Google Play SEO)
```
nawigacja, TIR, ciężarówka, prawo jazdy, fotoradar, GPS,
bezpieczna jazda, przekroczenie prędkości, mandat, parking TIR,
DKV, UTA, AS24, AdBlue, busiarz, transport, logistyka,
ograniczenia HGV, autostrady, korki, CB radio
```

### Tagline na grafice feature (1024x500)
- **PL:** *"TruckSpot — chroni Twoje prawko"*
- **EN:** *"TruckSpot — saves your license"*

### Sugestie screenshotów (priorytety)
1. **🛡️ Panel Bezpieczna jazda** — pokazuje punkty + streak (KILLER FEATURE)
2. **Modal podsumowania trasy** — "✓ Bezpieczna jazda — bez przekroczeń"
3. **Speedometer z alarmem +50** — pulsujący czerwony + komunikat
4. **Mapa TIR z ograniczeniami** — wyświetlone "Zakaz wjazdu", "Wysokość 3.5m"
5. **Wybór 3 tras** — najszybsza/najkrótsza/bez autostrad
6. **Oś trasy ze złotymi POI** — eleganckie miarki + parkingi
7. **CB Radio chat** — wiadomości od innych kierowców

---

## KROK 6 — Publikacja

1. Utwórz aplikację w Google Play Console
2. Wypełnij wszystkie sekcje (sklep, ocena treści, dostępność)
3. Wgraj AAB do ścieżki "Produkcja"
4. Wyślij do review (zwykle 1-3 dni robocze)

---

## KROK 7 — Aktualizacje

Po każdej zmianie:
1. Zwiększ `versionCode` (np. 2, 3...) i `versionName` ("1.1", "1.2"...)
2. Zbuduj nowe AAB
3. Wgraj do Play Console → Produkcja → nowa wersja

---

## Checklist przed wysłaniem

- [ ] Keystore wygenerowany i zbackupowany
- [ ] build.gradle skonfigurowany z signingConfig
- [ ] AAB zbudowany (`bundleRelease`)
- [ ] Screenshoty gotowe (min. 2)
- [ ] Ikona 512x512
- [ ] Opis PL napisany
- [ ] Konto Play Developer ($25)
- [ ] Ocena treści wypełniona
