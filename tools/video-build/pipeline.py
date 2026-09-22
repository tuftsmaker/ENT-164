#!/usr/bin/env python3
"""Build a narrated, captioned tutorial video from a narration script and a
set of recorded browser takes.

    python3 tools/video-build/pipeline.py <step> [--project DIR]

Steps (run in order, or use `all` for the post-production chain):

    tts        synthesis the narration with Deepgram Aura-2
    align      forced-align each clip with whisper.cpp -> sentence timings
    cards      render the opening title card and closing card
    captions   render one caption PNG per sentence
    plan       cut points per take, from the recorded marks
    assemble   cut, burn captions, mix narration, encode H.264

`tts` and `align` need the audio; the rest are pure ffmpeg/PIL and can be
re-run freely. `cards`, `captions`, `plan` and `assemble` are deterministic
given the recordings.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

FPS = 30
WHISPER_MODEL = os.environ.get(
    'WHISPER_MODEL', os.path.expanduser('~/.cache/whisper.cpp/ggml-tiny.en.bin'))
DEEPGRAM_KEY = os.path.expanduser('~/.config/deepgram/api_key')

INK = (26, 32, 44)
ACCENT = (214, 90, 49)
WHITE = (255, 255, 255)
MUTED = (170, 180, 196)
DIM = (120, 132, 152)


# ---------------------------------------------------------------- utilities

def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print('CMD:', ' '.join(str(c) for c in cmd[:10]), '...', file=sys.stderr)
        print(r.stderr[-3000:], file=sys.stderr)
        raise SystemExit(f'command failed: {cmd[0]}')
    return r


def dur(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                      '-of', 'csv=p=0', path]).stdout.strip())


def work(proj, cfg):
    """Where recordings and intermediates live - outside the repo by design."""
    w = cfg.get('workDir')
    if not w:
        raise SystemExit(
            f"{proj}/video.json has no workDir.\n\n"
            "Media must not be written inside the repo (see the Tutorial videos\n"
            "section in AGENTS.md): it bloats git and gets published by Pages.\n"
            "Set workDir to a path outside the repo, e.g.\n"
            '  "workDir": "~/Movies/ent164-onshape-tutorial/<slug>-build"'
        )
    w = os.path.expanduser(w)
    os.makedirs(w, exist_ok=True)
    return w


# ------------------------------------------------------------------------ tts

def step_tts(proj, cfg):
    """Synthesise each scene's narration with Deepgram Aura-2."""
    import urllib.request
    import time

    script = json.load(open(os.path.join(proj, 'script.json')))
    out = os.path.join(work(proj, cfg), 'audio')
    os.makedirs(out, exist_ok=True)
    key = open(DEEPGRAM_KEY).read().strip()
    voice = cfg['voice']

    total = 0.0
    for sid in sorted(script):
        path = os.path.join(out, sid + '.wav')
        if os.path.exists(path) and os.path.getsize(path) > 2000:
            print(f'  {sid:16s} cached')
        else:
            url = ('https://api.deepgram.com/v1/speak'
                   f'?model={voice}&encoding=linear16&container=wav&sample_rate=24000')
            body = json.dumps({'text': script[sid]}).encode()
            req = urllib.request.Request(url, data=body, method='POST', headers={
                'Authorization': f'Token {key}', 'Content-Type': 'application/json'})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=120) as r:
                        data = r.read()
                    if len(data) < 2000:
                        raise RuntimeError('short response')
                    open(path, 'wb').write(data)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    print(f'   retry ({e})')
                    time.sleep(3)
        d = dur(path)
        total += d
        print(f'  {sid:16s} {d:7.3f}s')
    print(f'\n  {"TOTAL":16s} {total:7.3f}s   voice={voice}')


# ---------------------------------------------------------------------- align

def _words(j):
    out = []
    for seg in (j.get('transcription') or []):
        off = seg.get('offsets') or {}
        txt = (seg.get('text') or '').strip()
        if txt:
            out.append((off.get('from', 0) / 1000.0, off.get('to', 0) / 1000.0, txt))
    return out


def _norm(t):
    return re.sub(r'[^a-z0-9]', '', t.lower())


def _sentences(text):
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text.strip()) if p.strip()]


def step_align(proj, cfg):
    """Forced-align each narration clip so captions and beats share one timeline."""
    import difflib

    if not shutil.which('whisper-cli'):
        raise SystemExit('whisper-cli not found (brew install whisper-cpp)')
    if not os.path.exists(WHISPER_MODEL):
        raise SystemExit(f'whisper model not found: {WHISPER_MODEL}\n'
                         f'  set WHISPER_MODEL or install a ggml model')

    script = json.load(open(os.path.join(proj, 'script.json')))
    wavdir = os.path.join(work(proj, cfg), 'wav')
    out = os.path.join(work(proj, cfg), 'align')
    os.makedirs(wavdir, exist_ok=True)
    os.makedirs(out, exist_ok=True)

    plan = {}
    for sid in sorted(script):
        src = os.path.join(work(proj, cfg), 'audio', sid + '.wav')
        wav = os.path.join(wavdir, sid + '.wav')
        run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-ar', '16000', '-ac', '1',
             '-c:a', 'pcm_s16le', wav])
        pref = os.path.join(out, sid)
        if not os.path.exists(pref + '.json'):
            run(['whisper-cli', '-m', WHISPER_MODEL, '-f', wav, '-ojf', '-ml', '1',
                 '-sow', '-of', pref, '-np'])
        j = json.load(open(pref + '.json'))
        ws = _words(j)
        sents = _sentences(script[sid])
        stoks, tok_sent = [], []
        for si, s in enumerate(sents):
            for t in s.split():
                stoks.append(_norm(t))
                tok_sent.append(si)
        wtoks = [_norm(w[2]) for w in ws]
        sm = difflib.SequenceMatcher(a=stoks, b=wtoks, autojunk=False)
        s2w = {}
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ('equal', 'replace'):
                for k in range(i1, i2):
                    jj = j1 + (k - i1)
                    if jj < j2:
                        s2w[k] = jj
        rows = []
        for si, s in enumerate(sents):
            idxs = [k for k in range(len(stoks)) if tok_sent[k] == si and k in s2w]
            rows.append({
                'i': si, 'text': s,
                'start': ws[s2w[idxs[0]]][0] if idxs else None,
                'end': ws[s2w[idxs[-1]]][1] if idxs else None,
            })
        plan[sid] = {'duration': round(dur(src), 3), 'sentences': rows}
        print(f'  {sid:16s} {plan[sid]["duration"]:7.3f}s  {len(rows)} sentences')

    json.dump(plan, open(os.path.join(work(proj, cfg), 'sentence-timings.json'), 'w'), indent=1)
    print('\n  -> sentence-timings.json')


# ---------------------------------------------------------------------- cards

def _card(path, heading, subtitle, footer, eyebrow=None, heading_size=96):
    from PIL import Image, ImageDraw, ImageFont
    BOLD = '/System/Library/Fonts/Supplemental/Arial Bold.ttf'
    REG = '/System/Library/Fonts/Supplemental/Arial.ttf'
    W, H = 1920, 1080
    img = Image.new('RGB', (W, H), INK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 14, H], fill=ACCENT)
    for (x, y, dx, dy) in [(120, 120, 1, 1), (W - 120, 120, -1, 1),
                           (120, H - 120, 1, -1), (W - 120, H - 120, -1, -1)]:
        d.line([x, y, x + 70 * dx, y], fill=(60, 70, 88), width=3)
    cx = W // 2

    def centred(text, font, y, fill):
        w = d.textlength(text, font=font)
        d.text((cx - w / 2, y), text, font=font, fill=fill)

    if eyebrow:
        centred(eyebrow, ImageFont.truetype(BOLD, 40), 330, ACCENT)
        centred(heading, ImageFont.truetype(BOLD, heading_size), 410, WHITE)
        d.line([cx - 320, 560, cx + 320, 560], fill=(70, 80, 100), width=2)
        centred(subtitle, ImageFont.truetype(REG, 46), 605, MUTED)
    else:
        centred(heading, ImageFont.truetype(BOLD, heading_size + 8), 400, WHITE)
        d.line([cx - 260, 560, cx + 260, 560], fill=(70, 80, 100), width=2)
        centred(subtitle, ImageFont.truetype(REG, 44), 605, MUTED)
    centred(footer, ImageFont.truetype(REG, 34), 900, DIM)
    img.save(path)


def step_cards(proj, cfg):
    """Title card at the head, closing card at the tail."""
    build = os.path.join(work(proj, cfg), 'build')
    os.makedirs(build, exist_ok=True)
    t = os.path.join(build, 'title.png')
    e = os.path.join(build, 'endcard.png')
    _card(t, cfg['heading'], cfg['subtitle'], cfg['footer'],
          eyebrow=cfg.get('eyebrow'), heading_size=96)
    _card(e, cfg['endHeading'], cfg['endSubtitle'], cfg['endFooter'],
          heading_size=104)

    td = float(cfg.get('titleDuration', 5.0))
    ed = float(cfg.get('endCardDuration', 6.0))
    run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', t, '-t', str(td),
         '-vf', f'fade=t=in:st=0:d=0.7,fade=t=out:st={td - 0.8:.2f}:d=0.8',
         '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
         '-pix_fmt', 'yuv420p', os.path.join(build, 'title.mp4')])
    run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', e, '-t', str(ed),
         '-vf', f'fade=t=in:st=0:d=0.8,fade=t=out:st={ed - 1.2:.2f}:d=1.2',
         '-r', str(FPS), '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
         '-pix_fmt', 'yuv420p', os.path.join(build, 'endcard.mp4')])
    print(f'  title {td}s, end card {ed}s')


# ------------------------------------------------------------------- captions

def _wrap(d, text, font, maxw):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _caption_png(path, text, size=42):
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1920, 1080
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', size)
    lines = _wrap(d, text, font, int(W * 0.76))
    line_h = int(size * 1.34)
    pad_x, pad_y = 34, 20
    bar_w = max(d.textlength(l, font=font) for l in lines) + pad_x * 2
    bar_h = line_h * len(lines) + pad_y * 2
    cx, cy = W // 2, H - 116
    x0, y0 = int(cx - bar_w / 2), int(cy - bar_h / 2)
    d.rounded_rectangle([x0, y0, int(cx + bar_w / 2), int(cy + bar_h / 2)],
                        radius=16, fill=(0, 0, 0, 208))
    ty = y0 + pad_y
    for l in lines:
        d.text((cx - d.textlength(l, font=font) / 2, ty), l, font=font,
               fill=(255, 255, 255, 255))
        ty += line_h
    img.save(path)


def _scene_layout(cfg):
    """Per take: scene ids and the offset of each scene within the take."""
    layout = []
    for t in cfg['takes']:
        offs, acc = {}, 0.0
        for sid in t['scenes']:
            offs[sid] = acc
            acc += _timings()[sid]['duration']
        layout.append({'take': t['name'], 'scenes': t['scenes'],
                       'offs': offs, 'length': acc + cfg.get('tail', 0.5)})
    return layout


_TIMINGS = {}


def _timings():
    global _TIMINGS
    return _TIMINGS


def step_captions(proj, cfg):
    """One transparent PNG per narration sentence, timed within its take."""
    global _TIMINGS
    _TIMINGS = json.load(open(os.path.join(work(proj, cfg), 'sentence-timings.json')))
    out = os.path.join(work(proj, cfg), 'cap')
    os.makedirs(out, exist_ok=True)
    layout = _scene_layout(cfg)
    manifest, plan = {}, []
    for seg in layout:
        files, caps = [], []
        for sid in seg['scenes']:
            base = seg['offs'][sid]
            for s in _TIMINGS[sid]['sentences']:
                if s['start'] is None:
                    continue
                caps.append({'text': s['text'],
                             'start': round(base + s['start'], 3),
                             'end': round(base + s['end'], 3)})
        for i, c in enumerate(caps):
            fn = os.path.join(out, f"{seg['take']}_{i:02d}.png")
            _caption_png(fn, c['text'])
            files.append(fn)
        manifest[seg['take']] = files
        plan.append({'take': seg['take'], 'len': round(seg['length'], 3),
                     'captions': caps})
        print(f"  {seg['take']:8s} {seg['length']:7.2f}s  {len(files)} captions")
    json.dump(plan, open(os.path.join(work(proj, cfg), 'caption-plan.json'), 'w'), indent=1)
    json.dump(manifest, open(os.path.join(work(proj, cfg), 'caption-files.json'), 'w'), indent=1)


# ----------------------------------------------------------------------- plan

def _marks(takes_dir, take):
    """Absolute wall-clock offset of the scene start within the recording."""
    d = takes_dir
    start = json.load(open(os.path.join(d, take + '.start.json')))
    ex = json.load(open(os.path.join(d, take + '.exec.json')))
    v = ex.get('value') or {}
    t0 = v.get('t0')
    if not t0:
        marks = v.get('marks') or []
        t0 = marks[0]['wall'] if marks else None
    return t0, start['startedAt']


def step_plan(proj, cfg):
    """Work out which slice of each recording belongs to which narration."""
    global _TIMINGS
    _TIMINGS = json.load(open(os.path.join(work(proj, cfg), 'sentence-timings.json')))
    d = os.path.join(work(proj, cfg), 'takes')
    tail = cfg.get('tail', 0.5)
    lead = cfg.get('lead', 0.0)
    plan, cursor = [], 0.0
    for t in cfg['takes']:
        take = t['name']
        t0, started = _marks(d, take)
        if not t0:
            raise SystemExit(f'{take}: no marks; cannot locate the scene start')
        vt0 = (t0 - started) / 1000.0
        narr = sum(_TIMINGS[s]['duration'] for s in t['scenes'])
        src = os.path.join(d, take + '.mp4')
        cut_in = max(0.0, vt0 - lead)
        cut_out = min(vt0 + narr + tail, dur(src))
        seg = max(cut_out - cut_in, narr + tail)
        plan.append({'take': take, 'scenes': t['scenes'], 'video_t0': round(vt0, 3),
                     'cut_in': round(cut_in, 3), 'cut_out': round(cut_out, 3),
                     'len': round(seg, 3), 'narration_len': round(narr, 3),
                     'out_start': round(cursor, 3)})
        cursor += plan[-1]['len']
    json.dump(plan, open(os.path.join(work(proj, cfg), 'assembly-plan.json'), 'w'), indent=1)
    print(f"  {'take':8s} {'vt0':>7s} {'in':>7s} {'out':>7s} {'len':>7s} {'narr':>7s}")
    for p in plan:
        print(f"  {p['take']:8s} {p['video_t0']:7.2f} {p['cut_in']:7.2f} "
              f"{p['cut_out']:7.2f} {p['len']:7.2f} {p['narration_len']:7.2f}")
    print(f'\n  TOTAL {cursor:.3f}s')


# -------------------------------------------------------------------- assemble

def _content_rect(path, at=1.0, tol=12, w=192, h=108):
    """Content rectangle of a frame, or None when it already fills the picture.

    Recordings occasionally come back letterboxed (the emulated viewport is not
    picked up by the compositor); cropping and scaling recovers them.
    """
    import numpy as np
    from PIL import Image
    r = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(at), '-i', path, '-frames:v', '1',
                        '-vf', f'scale={w}:{h}:flags=area,format=rgb24',
                        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True)
    raw = r.stdout
    if len(raw) < w * h * 3:
        return None
    a = np.frombuffer(raw[:w * h * 3], dtype=np.uint8).reshape(h, w, 3).astype(int)
    corners = [a[0, 0], a[0, w - 1], a[h - 1, 0], a[h - 1, w - 1]]
    bg = max(corners, key=lambda c: sum(1 for k in corners if abs(k - c).sum() < 6))
    diff = (np.abs(a - bg).sum(axis=2) > tol)
    xs, ys = np.where(diff.any(axis=0))[0], np.where(diff.any(axis=1))[0]
    if not len(xs) or not len(ys):
        return None
    x0, x1 = int(xs[0]), int(xs[-1]) + 1
    y0, y1 = int(ys[0]), int(ys[-1]) + 1
    sx, sy = 1920.0 / w, 1080.0 / h
    return (round(x0 * sx), round(y0 * sy), round((x1 - x0) * sx), round((y1 - y0) * sy))


def _fit_filter(path, at):
    r = _content_rect(path, at=at)
    if not r:
        return ''
    x, y, cw, ch = r
    if cw >= 1900 and ch >= 1060:
        return ''
    if cw < 900 or ch < 500:
        return ''
    print(f'    (letterboxed {cw}x{ch}; cropping and scaling)')
    return f'crop={cw}:{ch}:{x}:{y},scale=1920:1080'


def _caption_track(length, files, caps, out_path):
    """Transparent overlay video: each caption held for its own duration."""
    inputs, filters, labels = [], [], []
    idx, t = 0, 0.0
    def gap(to):
        nonlocal idx
        inputs.extend(['-f', 'lavfi', '-t', f'{to - t:.3f}',
                       '-i', f'color=c=black@0.0:s=1920x1080:r={FPS},format=rgba'])
        filters.append(f'[{idx}:v]null[v{idx}]')
        labels.append(f'v{idx}')
        idx += 1
    for i, c in enumerate(caps):
        if c['start'] > t + 0.001:
            gap(c['start'])
        inputs.extend(['-loop', '1', '-t', f"{c['end'] - c['start']:.3f}", '-i', files[i]])
        filters.append(f'[{idx}:v]format=rgba,setsar=1[v{idx}]')
        labels.append(f'v{idx}')
        idx += 1
        t = c['end']
    if length > t + 0.001:
        gap(length)
    fc = ';'.join(filters) + ';' + ''.join(f'[{l}]' for l in labels) + \
         f'concat=n={len(labels)}:v=1:a=0[out]'
    run(['ffmpeg', '-v', 'error', '-y'] + inputs +
        ['-filter_complex', fc, '-map', '[out]',
         '-c:v', 'qtrle', '-pix_fmt', 'argb', '-r', str(FPS), out_path])
    actual = dur(out_path)
    if actual > length + 0.02:
        tmp = out_path + '.trim.mov'
        run(['ffmpeg', '-v', 'error', '-y', '-i', out_path, '-t', f'{length:.3f}',
             '-c:v', 'qtrle', '-pix_fmt', 'argb', tmp])
        os.replace(tmp, out_path)
    return dur(out_path)


def step_assemble(proj, cfg):
    """Cut each take, burn its captions, mix the narration, encode."""
    global _TIMINGS
    _TIMINGS = json.load(open(os.path.join(work(proj, cfg), 'sentence-timings.json')))
    build = os.path.join(work(proj, cfg), 'build')
    os.makedirs(build, exist_ok=True)
    plan = json.load(open(os.path.join(work(proj, cfg), 'assembly-plan.json')))
    caps = {c['take']: c for c in json.load(open(os.path.join(work(proj, cfg), 'caption-plan.json')))}
    capfiles = json.load(open(os.path.join(work(proj, cfg), 'caption-files.json')))
    src_dir = os.path.join(work(proj, cfg), 'takes')
    title = os.path.join(build, 'title.mp4')
    endcard = os.path.join(build, 'endcard.mp4')
    title_dur = dur(title) if os.path.exists(title) else 0.0

    pieces = []
    for p in plan:
        take, length = p['take'], p['len']
        print(f'--- {take}: cut {p["cut_in"]:.2f}-{p["cut_out"]:.2f} ({length:.2f}s), '
              f'{len(caps[take]["captions"])} captions')
        src = os.path.join(src_dir, take + '.mp4')
        cut = os.path.join(build, take + '.cut.mp4')
        fit = _fit_filter(src, p['cut_in'] + 1.0)
        vf = f'{fit},scale=1920:1080' if fit else 'null'
        run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{p["cut_in"]:.3f}', '-i', src,
             '-t', f'{length:.3f}', '-an', '-vf', vf,
             '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
             '-pix_fmt', 'yuv420p', '-r', str(FPS), cut])

        ctrack = os.path.join(build, take + '.caps.mov')
        actual = _caption_track(length, capfiles[take], caps[take]['captions'], ctrack)
        if abs(actual - length) > 0.12:
            print(f'    note: caption track {actual:.3f}s vs take {length:.3f}s')

        comp = os.path.join(build, take + '.comp.mp4')
        pad = max(0.0, length - dur(cut))
        pre = f'tpad=stop_mode=clone:stop_duration={pad:.3f},' if pad > 0.02 else ''
        run(['ffmpeg', '-v', 'error', '-y', '-i', cut, '-i', ctrack,
             '-filter_complex',
             f'[0:v]{pre}setpts=PTS-STARTPTS[base];[base][1:v]overlay=0:0:format=auto:shortest=0[v]',
             '-map', '[v]', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16',
             '-pix_fmt', 'yuv420p', '-r', str(FPS), comp])
        pieces.append(comp)

    lst = os.path.join(build, 'concat.txt')
    with open(lst, 'w') as f:
        if os.path.exists(title):
            f.write(f"file '{title}'\n")
        for c in pieces:
            f.write(f"file '{c}'\n")
        if os.path.exists(endcard):
            f.write(f"file '{endcard}'\n")
    video = os.path.join(build, 'video.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
         '-c', 'copy', video])

    # Narration, delayed to each scene's position on the final timeline.
    lead = cfg.get('lead', 0.0)
    ins, fc, labs = [], [], []
    ai = 0
    for p in plan:
        t = title_dur + p['out_start'] + lead
        for sid in p['scenes']:
            ms = int(round(t * 1000))
            path = os.path.join(work(proj, cfg), 'audio', sid + '.wav')
            ins += ['-i', path]
            fc.append(f'[{ai}:a]aresample=48000,adelay={ms}|{ms}[a{ai}]')
            labs.append(f'a{ai}')
            t += _TIMINGS[sid]['duration']
            ai += 1
    fc.append(''.join(f'[{l}]' for l in labs) +
              f'amix=inputs={len(labs)}:duration=longest:normalize=0[aout]')
    audio = os.path.join(build, 'audio.wav')
    run(['ffmpeg', '-v', 'error', '-y'] + ins +
        ['-filter_complex', ';'.join(fc), '-map', '[aout]',
         '-c:a', 'pcm_s16le', '-ar', '48000', '-ac', '2', audio])

    out = os.path.expanduser(cfg['output'])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    vdur, adur = dur(video), dur(audio)
    extra = max(0.0, adur + 0.30 - vdur)
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-i', audio,
         '-filter_complex', f'[0:v]tpad=stop_mode=clone:stop_duration={extra:.3f}[v]',
         '-map', '[v]', '-map', '1:a',
         '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
         '-profile:v', 'high', '-level', '4.1', '-pix_fmt', 'yuv420p', '-r', str(FPS),
         '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart', out])
    print(f'\nWROTE {out}  ({dur(out):.3f}s, {os.path.getsize(out) / 1e6:.1f} MB)')


STEPS = {
    'tts': step_tts, 'align': step_align, 'cards': step_cards,
    'captions': step_captions, 'plan': step_plan, 'assemble': step_assemble,
}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('step', choices=list(STEPS) + ['all'])
    ap.add_argument('--project', default=None,
                    help='project directory (default: the only one under projects/)')
    a = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    proj = a.project
    if not proj:
        base = os.path.join(here, 'projects')
        names = [n for n in sorted(os.listdir(base))
                 if os.path.isdir(os.path.join(base, n))]
        if len(names) != 1:
            raise SystemExit(f'--project required; found: {names}')
        proj = os.path.join(base, names[0])
    cfg = json.load(open(os.path.join(proj, 'video.json')))
    cfg.setdefault('output', os.path.expanduser(
        f"~/Movies/ent164-onshape-tutorial/{cfg['slug']}.mp4"))

    steps = list(STEPS) if a.step == 'all' else [a.step]
    for s in steps:
        print(f'== {s} ==')
        STEPS[s](proj, cfg)


if __name__ == '__main__':
    main()
