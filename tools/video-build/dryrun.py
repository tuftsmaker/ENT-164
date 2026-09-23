#!/usr/bin/env python3
"""Dry-run a native (Inkscape) take, with the recorder off.

Lands the take's setup, runs its timed action list, and samples the document
window every few seconds so the result can be inspected frame by frame. Useful
before spending real time on `ink-drive.py record`, and the only way to see
whether a panel click landed where it was meant to.

    python3 dryrun.py projects/laser-cutting-in-inkscape take02 --outdir /tmp/dr02

The take's `endSave` hand-off is written as well, so the next take's setup has
something to open (which is what recording would have produced).
"""
import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
ink = importlib.import_module('ink-drive')


def sample(outdir, stop, period):
    i = 0
    while not stop.is_set():
        try:
            ink.shot(os.path.join(outdir, f'frame-{i:03d}.png'))
        except Exception as e:                       # a moving window, a dialog
            print('sample failed:', e)
        i += 1
        stop.wait(period)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('project')
    ap.add_argument('take')
    ap.add_argument('--sample', type=float, default=5.0,
                    help='seconds between screenshots (default 5)')
    ap.add_argument('--outdir', default='/tmp/dryrun')
    args = ap.parse_args()

    cfg = json.load(open(os.path.join(args.project, 'video.json')))
    work = os.path.expanduser(cfg['workDir'])
    take_cfg = next(t for t in cfg['takes'] if t['name'] == args.take)
    spec = json.load(open(os.path.join(args.project, 'takes', args.take + '.json')))

    ink.load_timings(work)
    ink._set_take(take_cfg['scenes'])
    ink.prepare_dxf(cfg, work, take_cfg.get('setup', 'setup-open-dxf'))

    os.makedirs(args.outdir, exist_ok=True)
    stop = threading.Event()
    t = threading.Thread(target=sample, args=(args.outdir, stop, args.sample), daemon=True)
    t.start()
    t0 = time.time()
    try:
        ink.run_actions(spec.get('actions', []))
    finally:
        stop.set()
        t.join(timeout=5)
    end_save = take_cfg.get('endSave')
    if end_save:
        ink.save_as(os.path.join(work, end_save))
        print(f'hand-off written: {end_save}')
    print(f'dry run of {args.take} finished in {time.time() - t0:.1f}s')


if __name__ == '__main__':
    main()
