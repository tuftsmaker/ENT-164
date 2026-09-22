# TuftsMaker brand assets

Channel banner for the YouTube channel, generated (not hand-edited).

## Rebuild

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1 \
  --window-size=2048,1152 \
  --screenshot=banner-render.png \
  --virtual-time-budget=6000 \
  "file://$PWD/brand/TuftsMaker-banner.html"
```

Then convert to JPEG (YouTube wants **2048×1152, JPEG, ≤ 6 MB**):

```sh
python3 - <<'PY'
from PIL import Image
im = Image.open("banner-render.png").convert("RGB")
im.save("TuftsMaker-banner-2048x1152.jpg", "JPEG",
        quality=95, optimize=True, subsampling=0, progressive=True)
PY
```

The committed `TuftsMaker-banner-2048x1152.jpg` is ~435 KB at quality 95, so the
6 MB ceiling is never a constraint — do not lower quality to hit it.

## The safe zone matters

YouTube only shows the **central 1235 × 338 px** on every device; phones and TVs
crop everything outside it. `TuftsMaker-banner.html` keeps the wordmark and
tagline inside that band, and the photo strips are decorative — they are allowed
to be cropped away.

To check a render, crop the centre and confirm the text is intact:

```sh
python3 -c "
from PIL import Image
im = Image.open('banner-render.png'); W,H = im.size
x, y = (W-1235)//2, (H-338)//2
im.crop((x,y,x+1235,y+338)).save('safe-zone.png')
"
```

## Palette

Matches `assets/site.css`: Tufts blue `#3E8EDE`, deep blue `#1F6FD0`,
ink `#0d1526`, with the same maker icon mark used in the site nav. Keep it
consistent if the site theme changes.
