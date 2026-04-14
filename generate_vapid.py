"""
Generuje klucze VAPID do Web Push.
Uruchom: python generate_vapid.py
Następnie ustaw w Render Environment Variables:
  VAPID_PRIVATE_KEY = <private>
  VAPID_PUBLIC_KEY  = <public>
  VAPID_EMAIL       = mailto:twoj@email.com
"""
try:
    from py_vapid import Vapid
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywebpush"])
    from py_vapid import Vapid

v = Vapid()
v.generate_keys()
private = v.private_pem().decode().strip()
public  = v.public_key.public_bytes(
    __import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding','PublicFormat']).Encoding.X962,
    __import__('cryptography.hazmat.primitives.serialization', fromlist=['Encoding','PublicFormat']).PublicFormat.UncompressedPoint
)
import base64
pub_b64 = base64.urlsafe_b64encode(public).rstrip(b'=').decode()

print("\n=== VAPID Keys ===")
print(f"\nVAPID_PUBLIC_KEY={pub_b64}")
print(f"\nVAPID_PRIVATE_KEY=")
print(private)
print("\nWklej powyższe jako zmienne środowiskowe w Render Dashboard → Environment")
print("(Environment → Add Environment Variable)\n")

# Zapisz do pliku .env.vapid dla wygody
with open(".env.vapid", "w") as f:
    f.write(f"VAPID_PUBLIC_KEY={pub_b64}\n")
    f.write(f"VAPID_PRIVATE_KEY={private}\n")
    f.write("VAPID_EMAIL=mailto:admin@truckspot.app\n")
print("Zapisano do .env.vapid")
