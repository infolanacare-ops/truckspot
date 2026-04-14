"""
TruckSpot — generator ikon PNG (Pillow, działa na Windows bez dodatkowych bibliotek)
Uruchom: python generate_icons.py
Wymagania: pip install Pillow
"""
import os, math

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Instaluję Pillow...")
    os.system("pip install Pillow")
    from PIL import Image, ImageDraw, ImageFont

STATIC = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC, exist_ok=True)

# ── Kolory ──────────────────────────────────────────────────────────────────
BG_TOP    = (26,  31,  46)   # #1a1f2e
BG_BOT    = (37,  45,  69)   # #252d45
BLUE      = (59,  130, 246)  # #3b82f6
PURPLE    = (109, 40,  217)  # #6d28d9
WHITE     = (255, 255, 255)
WHITE_DIM = (224, 231, 255)

def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i]-c1[i])*t) for i in range(3))

def gradient_bg(draw, size):
    """Rysuje gradient tła od góry do dołu."""
    for y in range(size):
        t = y / size
        c = lerp_color(BG_TOP, BG_BOT, t)
        draw.line([(0, y), (size, y)], fill=c)

def pin_path(cx, cy, r, tip_y):
    """Zwraca punkty kształtu pin (łezka) jako lista punktów."""
    pts = []
    # Górna okrągła część
    for a in range(181):
        angle = math.radians(a - 90)
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        pts.append((x, y))
    # Czubek na dole
    pts.append((cx, tip_y))
    return pts

def draw_pin_gradient(draw, cx, cy, r, tip_y, color_top, color_bot):
    """Rysuje pin z gradientem."""
    pts = pin_path(cx, cy, r, tip_y)
    # Rysuj wielokąt gradientowo linia po linii
    # Najpierw narysuj pełny kształt
    draw.polygon(pts, fill=color_top)
    # Gradient - nakładaj ciemniejsze warstwy od dołu
    for i in range(60):
        t = i / 60
        y_val = cy - r + (tip_y - cy + r) * (1 - t)
        c = lerp_color(color_bot, color_top, t)
        try:
            draw.line([(cx - r - 5, int(y_val)), (cx + r + 5, int(y_val))], fill=c)
        except:
            pass
    # Narysuj jeszcze raz pełny kształt na wierzchu żeby przyciąć
    # (uproszczone - po prostu solid)
    draw.polygon(pts, fill=color_top)

def make_icon(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Tło
    gradient_bg(draw, size)

    # Proporcje
    s = size
    cx = s // 2
    pin_top = int(s * 0.13)
    pin_r = int(s * 0.32)
    pin_cy = pin_top + pin_r
    pin_tip = int(s * 0.82)

    # Cień pinu (przesunięty w dół)
    shadow_pts = pin_path(cx + int(s*0.02), pin_cy + int(s*0.03), pin_r, pin_tip + int(s*0.03))
    draw.polygon(shadow_pts, fill=(0, 0, 0, 80))

    # Pin — gradient niebieski → fioletowy
    pts = pin_path(cx, pin_cy, pin_r, pin_tip)
    # Rysuj gradient ręcznie
    min_y = int(pin_cy - pin_r)
    max_y = pin_tip
    for y in range(min_y, max_y + 1):
        t = (y - min_y) / (max_y - min_y)
        c = lerp_color(BLUE, PURPLE, t)
        draw.line([(0, y), (s, y)], fill=c + (255,))
    # Maskuj kształtem pinu
    mask = Image.new("L", (s, s), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.polygon(pts, fill=255)
    pin_layer = img.copy()
    # Zastosuj maskę — prostsze: narysuj kształt na nowej warstwie
    overlay = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    # Gradient w kształcie pinu
    for y in range(min_y, max_y + 1):
        t = (y - min_y) / (max_y - min_y)
        c = lerp_color(BLUE, PURPLE, t)
        odraw.line([(0, y), (s, y)], fill=c + (255,))
    # Wytnij do kształtu pinu
    pmask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(pmask).polygon(pts, fill=255)
    overlay.putalpha(pmask)
    img = Image.new("RGBA", (s, s), (0,0,0,0))
    draw2 = ImageDraw.Draw(img)
    gradient_bg(draw2, size)
    # Cień
    sdraw = ImageDraw.Draw(img)
    sdraw.polygon(shadow_pts, fill=(0, 0, 0, 60))
    img.paste(overlay, mask=overlay.split()[3])
    draw = ImageDraw.Draw(img)

    # Wewnętrzny okrąg (dekoracja)
    inner_r = int(pin_r * 0.85)
    draw.ellipse([cx-inner_r, pin_cy-inner_r, cx+inner_r, pin_cy+inner_r],
                 outline=(255,255,255,30), width=max(1,size//120))

    # ── Truck (tylko dla rozmiarów >= 48px) ────────────────────────────────
    if size < 48:
        # Dla favicon: tylko litera "T"
        try:
            fnt = ImageFont.truetype("arialbd.ttf", max(8, size//2))
        except:
            fnt = ImageFont.load_default()
        draw.text((cx, pin_cy), "T", font=fnt, fill=WHITE, anchor="mm")
        return img.convert("RGB")

    tw = int(s * 0.44)   # szerokość ciężarówki
    th = int(s * 0.21)   # wysokość
    tx = cx - tw // 2    # lewy górny X
    ty = pin_cy - th // 2 - int(s*0.02)  # lewy górny Y

    cab_w = int(tw * 0.55)
    cargo_w = tw - cab_w - int(s*0.01)
    cargo_x = tx + cab_w + int(s*0.01)

    # Kabina
    draw.rounded_rectangle([tx, ty, tx+cab_w, ty+th],
                            radius=max(3, size//80), fill=WHITE)
    # Cargo
    draw.rounded_rectangle([cargo_x, ty+int(th*0.1), cargo_x+cargo_w, ty+th],
                            radius=max(2, size//120), fill=(240,245,255))

    # Okno kabiny
    win_pad = max(2, size//140)
    win_h = int(th * 0.45)
    draw.rounded_rectangle([tx+win_pad*3, ty+win_pad*2, tx+cab_w-win_pad*2, ty+win_pad*2+win_h],
                            radius=max(2, size//160), fill=(59, 130, 246, 200))

    # Koła
    wheel_r = int(s * 0.065)
    wheel_y = ty + th + wheel_r // 2
    wheel_inner = int(wheel_r * 0.55)
    for wx in [tx + int(cab_w*0.32), cargo_x + int(cargo_w*0.55)]:
        draw.ellipse([wx-wheel_r, wheel_y-wheel_r, wx+wheel_r, wheel_y+wheel_r],
                     fill=(26,31,46))
        draw.ellipse([wx-wheel_inner, wheel_y-wheel_inner, wx+wheel_inner, wheel_y+wheel_inner],
                     fill=BLUE)
        hub_r = max(2, wheel_r//4)
        draw.ellipse([wx-hub_r, wheel_y-hub_r, wx+hub_r, wheel_y+hub_r], fill=WHITE)

    # Biała kropka na końcu pinu
    dot_r = max(4, size//60)
    draw.ellipse([cx-dot_r, pin_tip-dot_r*2, cx+dot_r, pin_tip], fill=WHITE)

    # ── Tekst "TS" dla małych rozmiarów lub "TruckSpot" dla dużych ──────────
    if size >= 256:
        font_size = max(12, size // 11)
        try:
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except:
            try:
                font = ImageFont.truetype("Arial Bold.ttf", font_size)
            except:
                font = ImageFont.load_default()

        text = "TruckSpot" if size >= 512 else "TS"
        text_y = int(s * 0.89)
        # Cień tekstu
        draw.text((cx+2, text_y+2), text, font=font, fill=(0,0,0,120), anchor="mm")
        draw.text((cx, text_y), text, font=font, fill=WHITE, anchor="mm")

    return img.convert("RGB")

# ── Generuj wszystkie rozmiary ───────────────────────────────────────────────
ICON_SIZES = [
    (1024, "icon-1024.png"),
    (512,  "icon-512.png"),
    (192,  "icon-192.png"),
    (180,  "apple-touch-icon.png"),
    (152,  "icon-152.png"),
    (144,  "icon-144.png"),
    (128,  "icon-128.png"),
    (96,   "icon-96.png"),
    (72,   "icon-72.png"),
    (48,   "icon-48.png"),
    (32,   "favicon-32.png"),
    (16,   "favicon-16.png"),
]

print("=== TruckSpot Icon Generator (Pillow) ===\n")
print("Generuję ikony...")
for size, filename in ICON_SIZES:
    img = make_icon(size)
    out = os.path.join(STATIC, filename)
    img.save(out, "PNG", optimize=True)
    print(f"  OK {filename} ({size}x{size})")

# Splash screen — prosty gradient z tekstem
def make_splash(w, h, filename):
    img = Image.new("RGB", (w, h), BG_TOP)
    draw = ImageDraw.Draw(img)
    gradient_bg(draw, max(w,h))
    img = img.crop((0,0,w,h))
    draw = ImageDraw.Draw(img)

    # Ikona wyśrodkowana
    icon_size = min(w, h) // 3
    icon = make_icon(icon_size)
    ix = (w - icon_size) // 2
    iy = int(h * 0.28)
    img.paste(icon, (ix, iy))

    # Tekst
    try:
        font_big = ImageFont.truetype("arialbd.ttf", min(w,h)//14)
        font_small = ImageFont.truetype("arial.ttf", min(w,h)//22)
    except:
        font_big = ImageFont.load_default()
        font_small = font_big

    draw.text((w//2, int(h*0.72)), "TruckSpot", font=font_big, fill=WHITE, anchor="mm")
    draw.text((w//2, int(h*0.79)), "Parkingi dla kierowców TIR", font=font_small, fill=(136,144,168), anchor="mm")

    # Trzy kropki
    dot_y = int(h * 0.86)
    dot_r = max(6, min(w,h)//80)
    for i, color in enumerate([BLUE, PURPLE, (59,130,246,128)]):
        dx = w//2 + (i-1) * dot_r * 3
        c = color[:3]
        a = 255 if i < 2 else 140
        draw.ellipse([dx-dot_r, dot_y-dot_r, dx+dot_r, dot_y+dot_r], fill=c)

    out = os.path.join(STATIC, filename)
    img.save(out, "PNG", optimize=True)
    print(f"  OK {filename} ({w}x{h})")

print("\nGeneruję splash screeny...")
make_splash(1242, 2688, "splash-iphone14.png")
make_splash(1170, 2532, "splash-iphone13.png")
make_splash(828,  1792, "splash-iphone11.png")
make_splash(1080, 1920, "splash-android.png")
make_splash(2048, 2732, "splash-ipad.png")

print("\nDONE: Wszystko gotowe w static/")
print("  → App Store:    static/icon-1024.png")
print("  → Google Play:  static/icon-512.png")
print("  → PWA:          static/icon-192.png")
