#!/usr/bin/env python3
"""
Fait parler Nestor : texte -> TTS ElevenLabs (voix figee) -> coloration Nestor -> mp3.

C'est le pipeline complet de bout en bout (la future passerelle HA en miniature).

Usage:
    python3 say.py "Bonsoir Monsieur."
    python3 say.py "..." --raw       # garde aussi la version SANS coloration
    python3 say.py "..." --no-play   # ne joue pas le resultat
"""
import argparse
import subprocess
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

from design import ROOT, load_api_key
from nestor_fx import ffmpeg_cmd

VOICE_ID = "yY3c56wtYbsunxZsENmx"          # Nestor-base-v1
MODEL_ID = "eleven_multilingual_v2"         # multilingue -> francais
OUT = ROOT / "out"


def tts(text: str, dst: Path):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128"
    body = json.dumps({"text": text, "model_id": MODEL_ID}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"xi-api-key": load_api_key(), "Content-Type": "application/json",
                 "Accept": "audio/mpeg"},
        method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            dst.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Erreur TTS {e.code}: {e.read().decode(errors='replace')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--raw", action="store_true", help="garde aussi la version brute (sans filtre)")
    ap.add_argument("--no-play", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%H%M%S")
    raw = OUT / f"nestor-{ts}-raw.mp3"
    final = OUT / f"nestor-{ts}.mp3"

    print("→ Synthese ElevenLabs…")
    tts(args.text, raw)
    print("→ Coloration Nestor…")
    r = subprocess.run(ffmpeg_cmd(str(raw), str(final)), capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg a echoue:\n{r.stderr}")
    if not args.raw:
        raw.unlink()
    print(f"✓ {final}")
    if args.raw:
        print(f"  (brut conserve : {raw})")

    if not args.no_play:
        subprocess.run(["afplay", str(final)])


if __name__ == "__main__":
    main()
