# TuftsMaker brand assets

YouTube channel artwork: banner and avatar. Both are generated (not hand-edited).

| Asset | File | Size |
|---|---|---|
| Channel banner | `TuftsMaker-banner-2048x1152.jpg` | 2048×1152, ~435 KB |
| Channel avatar (recommended upload) | `TuftsMaker-avatar-800x800.png` | 800×800, ~204 KB |
| Channel avatar (small) | `TuftsMaker-avatar-120x120.png` | 120×120, ~8 KB |

Sources: `TuftsMaker-banner.html`, `TuftsMaker-avatar.html`.

## Avatar notes

- YouTube recommends uploading **800×800** (1:1) and downsamples it itself;
  **98×98 is the minimum**. The 120×120 file is included for use anywhere that
  imposes a 120px cap, but prefer the 800×800 upload on YouTube — the flat
  colour and hard edges make the difference visible.
- Avatars are **circle-cropped**, so the avatar source fills the whole square
  with the gradient. Do not reintroduce a rounded-square mark: its corners
  would be cut off. Check any change as a circle at 98px before shipping.
- The icon is the same maker mark used in the site nav and the banner, sized at
  the same icon-to-mark ratio.

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

Avatar (rendered at 800×800, then downsampled for the 120px copy):

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless=new --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=1.6667 \
  --window-size=480,480 \
  --screenshot=avatar-render.png \
  --virtual-time-budget=5000 \
  "file://$PWD/brand/TuftsMaker-avatar.html"

python3 - <<'PY'
from PIL import Image
im = Image.open("avatar-render.png").convert("RGB")   # 800x800
im.save("TuftsMaker-avatar-800x800.png", "PNG", optimize=True)
im.resize((120, 120), Image.LANCZOS).save("TuftsMaker-avatar-120x120.png", "PNG", optimize=True)
PY
```

Render large and downsample — rendering straight to 120px gives visibly rougher
edges on the diagonal hammer.

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
