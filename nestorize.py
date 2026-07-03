#!/usr/bin/env python3
"""
Coloration synthetique « robot Nabaztag » — couche DSP appliquee par-dessus
les voix brutes, pour juger les candidats « en costume ».

C'est une couche SEPAREE du choix de la voix : elle sera rejouee plus tard
dans la passerelle TTS (k8s), sur ElevenLabs comme sur Piper. On peut donc la
retoucher independamment sans regenerer les voix.

Usage:
    python3 nestorize.py                 # applique tous les presets a tous les candidats
    python3 nestorize.py --preset robot  # un seul preset
    python3 nestorize.py in.mp3 out.mp3 --preset robot   # fichier isole (test)

Chaines ffmpeg. Retoucher les presets ci-dessous puis relancer : c'est local et gratuit.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from design import GALLERY, AUDIO, MANIFEST, load_manifest, render_html

SYNTH = AUDIO / "synth"

# --- Presets de coloration -------------------------------------------------
# Chaque preset = une chaine de filtres audio ffmpeg (-af).
PRESETS = {
    # Majordome raffine derriere un petit haut-parleur : discret, intelligible,
    # juste un vernis electronique. Le curseur « respectable ».
    "sobre": (
        "highpass=f=140,lowpass=f=7800,"
        "acrusher=bits=10:samples=1:mode=log:mix=0.35,"
        "aphaser=in_gain=0.7:out_gain=0.85:delay=2.5:decay=0.35:speed=0.6,"
        "aecho=0.85:0.9:5:0.12,"
        "alimiter=limit=0.95"
    ),
    # Franchement synthetique : band-limit serre facon jouet, bitcrush marque,
    # tremolo qui apporte le buzz metallique (facon ring-mod GLaDOS/Nabaztag).
    "robot": (
        "highpass=f=210,lowpass=f=6200,"
        "acrusher=bits=7:samples=1:mode=log:mix=0.55,"
        "tremolo=f=58:d=0.5,"
        "aphaser=in_gain=0.6:out_gain=0.8:delay=3:decay=0.5:speed=1.2,"
        "aecho=0.8:0.85:7:0.2,"
        "alimiter=limit=0.95"
    ),
}


def apply(src: Path, dst: Path, preset: str):
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-af", PRESETS[preset], str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg a echoue ({preset}):\n{r.stderr}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", help="fichier source (mode isole)")
    ap.add_argument("dst", nargs="?", help="fichier sortie (mode isole)")
    ap.add_argument("--preset", choices=list(PRESETS), help="un seul preset (defaut: tous)")
    args = ap.parse_args()

    presets = [args.preset] if args.preset else list(PRESETS)

    # Mode isole : un fichier -> un fichier
    if args.src and args.dst:
        p = args.preset or "robot"
        apply(Path(args.src), Path(args.dst), p)
        print(f"✓ {args.dst}  ({p})")
        return

    # Mode galerie : tous les candidats du manifest
    batches = load_manifest()
    n = 0
    for b in batches:
        for c in b["candidates"]:
            base = GALLERY / c["audio"]
            if not base.exists():
                continue
            c.setdefault("synth", {})
            for preset in presets:
                out = SYNTH / f"{base.stem}__{preset}.mp3"
                apply(base, out, preset)
                c["synth"][preset] = f"audio/synth/{out.name}"
                n += 1
                print(f"   {c['synth'][preset]}")
    MANIFEST.write_text(json.dumps(batches, indent=2, ensure_ascii=False))
    (GALLERY / "index.html").write_text(render_html(batches))
    print(f"✓ {n} versions colorees. Galerie mise a jour → gallery/index.html")


if __name__ == "__main__":
    main()
