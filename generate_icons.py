"""
TruckSpot — generator ikon PNG ze SVG
Uruchom: python generate_icons.py
Wymagania: pip install cairosvg
"""
import os

try:
    import cairosvg
except ImportError:
    print("Instaluję cairosvg...")
    os.system("pip install cairosvg")
    import cairosvg

STATIC = os.path.join(os.path.dirname(__file__), "static")
ICON_SVG = os.path.join(STATIC, "icon.svg")
SPLASH_SVG = os.path.join(STATIC, "splash.svg")

# Rozmiary ikon do sklepów i PWA
ICON_SIZES = [
    (1024, "icon-1024.png"),   # App Store (iOS) — wymagany
    (512,  "icon-512.png"),    # Google Play — wymagany (high-res)
    (192,  "icon-192.png"),    # PWA manifest large
    (180,  "apple-touch-icon.png"),  # iOS Safari
    (152,  "icon-152.png"),    # iPad
    (144,  "icon-144.png"),    # Android Chrome
    (128,  "icon-128.png"),    # Chrome Web Store
    (96,   "icon-96.png"),     # Android MDPI+
    (72,   "icon-72.png"),     # Android MDPI
    (48,   "icon-48.png"),     # Android LDPI
    (32,   "favicon-32.png"),  # Browser tab
    (16,   "favicon-16.png"),  # Browser tab small
]

# Splash screens (portret)
SPLASH_SIZES = [
    (1242, 2688, "splash-iphone14.png"),   # iPhone 14 Pro Max
    (1170, 2532, "splash-iphone13.png"),   # iPhone 13
    (828,  1792, "splash-iphone11.png"),   # iPhone 11
    (1080, 1920, "splash-android.png"),    # Android standard
    (1284, 2778, "splash-ipad.png"),       # iPad Pro 12.9"
]

print("=== TruckSpot Icon Generator ===\n")

print("Generuję ikony...")
for size, filename in ICON_SIZES:
    out = os.path.join(STATIC, filename)
    cairosvg.svg2png(
        url=ICON_SVG,
        write_to=out,
        output_width=size,
        output_height=size,
    )
    print(f"  ✓ {filename} ({size}x{size})")

print("\nGeneruję splash screeny...")
for w, h, filename in SPLASH_SIZES:
    out = os.path.join(STATIC, filename)
    cairosvg.svg2png(
        url=SPLASH_SVG,
        write_to=out,
        output_width=w,
        output_height=h,
    )
    print(f"  ✓ {filename} ({w}x{h})")

print("\n✅ Wszystkie ikony wygenerowane w static/")
print("\nDo App Store wyślij:  static/icon-1024.png")
print("Do Google Play wyślij: static/icon-512.png")
