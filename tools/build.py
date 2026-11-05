#!/usr/bin/env python3
"""
Сборка приложения под клиента.
Читает config.js и обновляет: manifest.webmanifest, иконки (icons/), sw.js (список файлов и версию кеша).
Запуск из корня проекта:  python3 tools/build.py
Нужен Pillow:  pip install pillow
"""
import json, re, hashlib, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

src = open('config.js', encoding='utf-8').read()
m = re.search(r'window\.BH_CONFIG\s*=\s*(\{.*\})\s*;?\s*$', src, re.S)
if not m:
    sys.exit('Не найден блок window.BH_CONFIG = {...} в config.js')
try:
    C = json.loads(m.group(1))
except json.JSONDecodeError as e:
    sys.exit(f'Ошибка в config.js (строка {e.lineno} внутри настроек): {e.msg}')

# --- проверка настроек ---
errors = []
for k in ['brand', 'colors', 'hero', 'services', 'barbers', 'contacts', 'schedule', 'booking']:
    if k not in C: errors.append(f'нет раздела "{k}"')
ids = [s.get('id') for s in C.get('services', [])]
if len(ids) != len(set(ids)): errors.append('повторяются id услуг')
for s in C.get('services', []):
    for f in ['id', 'name', 'price', 'duration']:
        if s.get(f) in (None, ''): errors.append(f'у услуги {s.get("name")} не заполнено поле {f}')
photos = [C['hero'].get('photo')] + [x.get('photo') for x in C['services'] + C['barbers']]
for p in filter(None, photos):
    if not p.startswith('http') and not os.path.exists(p): errors.append(f'нет файла фото {p}')
if C['booking'].get('mode') == 'external' and not C['booking'].get('externalUrl'):
    errors.append('booking.mode = "external", но не указан externalUrl')
if errors:
    sys.exit('Исправьте config.js:\n- ' + '\n- '.join(errors))

b, col = C['brand'], C['colors']
bg, accent = col.get('background', '#0e0e0f'), col.get('accent', '#c8a15a')

# --- манифест ---
manifest = {
    "name": f"{b['name']} — запись онлайн",
    "short_name": b.get('shortName') or b['name'][:12],
    "description": f"{b.get('tagline', '')}. Онлайн-запись".strip('. '),
    "lang": "ru", "start_url": "./index.html", "scope": "./",
    "display": "standalone", "orientation": "portrait",
    "background_color": bg, "theme_color": bg,
    "icons": [
        {"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}
json.dump(manifest, open('manifest.webmanifest', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

# --- иконки ---
from PIL import Image, ImageDraw, ImageFont
font = None
for p in ['tools/icon-font.ttf'] + glob.glob('/usr/share/fonts/**/*Serif-Bold.ttf', recursive=True) + \
         glob.glob('/System/Library/Fonts/Supplemental/Georgia Bold.ttf') + glob.glob('C:/Windows/Fonts/georgiab.ttf'):
    if os.path.exists(p): font = p; break
os.makedirs('icons', exist_ok=True)
mono = b.get('monogram', b['name'][:2])
def icon(size, path):
    S = size * 4; im = Image.new('RGB', (S, S), bg); d = ImageDraw.Draw(im)
    r, c = S * 0.31, S / 2
    d.ellipse([c - r, c - r, c + r, c + r], outline=accent, width=int(S * 0.014))
    fs = int(S * (0.30 if len(mono) <= 2 else 0.22))
    f = ImageFont.truetype(font, fs) if font else ImageFont.load_default()
    d.text((c, c), mono, font=f, fill=accent, anchor='mm')
    im.resize((size, size), Image.LANCZOS).save(path)
icon(192, 'icons/icon-192.png'); icon(512, 'icons/icon-512.png'); icon(180, 'icons/apple-touch-icon.png')

# --- service worker ---
files = ['index.html', 'config.js', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'] \
        + sorted({p for p in photos if p and not p.startswith('http')})
h = hashlib.sha1()
for f in files: h.update(open(f, 'rb').read())
ver = 'v-' + h.hexdigest()[:10]
sw = f"""// Сгенерировано tools/build.py — не редактируйте вручную.
const V='{ver}';
const SHELL=['./',{','.join(repr(f) for f in files)}];
self.addEventListener('install',e=>{{e.waitUntil(caches.open(V).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting()))}});
self.addEventListener('activate',e=>{{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==V).map(x=>caches.delete(x)))).then(()=>self.clients.claim()))}});
self.addEventListener('fetch',e=>{{
  if(e.request.method!=='GET')return;
  e.respondWith(fetch(e.request).then(r=>{{const c=r.clone();caches.open(V).then(x=>x.put(e.request,c));return r}}).catch(()=>caches.match(e.request).then(r=>r||caches.match('index.html'))));
}});
"""
open('sw.js', 'w', encoding='utf-8').write(sw)
print(f'Готово: {b["name"]}, услуг {len(C["services"])}, мастеров {len(C["barbers"])}, версия кеша {ver}')
