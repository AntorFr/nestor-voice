#!/usr/bin/env python3
"""
Promeut un apercu Voice Design en voix permanente dans la bibliotheque ElevenLabs.

Usage:
    python3 save.py <generated_voice_id> [--name Nestor]

Le generated_voice_id se lit dans la galerie (gallery/index.html) ou dans
gallery/candidates.json. La description est reprise du batch d'origine.
"""
import argparse
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "gallery" / "candidates.json"
API = "https://api.elevenlabs.io/v1/text-to-voice/create-voice-from-preview"

from design import load_api_key, render_html, load_manifest  # reutilise la config


def find(batches, gvid):
    for b in batches:
        for c in b["candidates"]:
            if c["generated_voice_id"] == gvid:
                return b, c
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("generated_voice_id")
    ap.add_argument("--name", default="Nestor")
    args = ap.parse_args()

    batches = load_manifest()
    batch, cand = find(batches, args.generated_voice_id)
    if not batch:
        sys.exit(f"generated_voice_id introuvable dans le manifest: {args.generated_voice_id}")

    body = {
        "voice_name": args.name,
        "voice_description": batch["prompt"],
        "generated_voice_id": args.generated_voice_id,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"xi-api-key": load_api_key(), "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Erreur API {e.code}: {e.read().decode(errors='replace')}")

    voice_id = result.get("voice_id", "?")
    cand["saved"] = True
    cand["voice_id"] = voice_id
    MANIFEST.write_text(json.dumps(batches, indent=2, ensure_ascii=False))
    (ROOT / "gallery" / "index.html").write_text(render_html(batches))
    print(f"✓ Voix « {args.name} » creee. voice_id = {voice_id}")
    print("  Reutilisable dans HA / ton pipeline TTS.")


if __name__ == "__main__":
    main()
