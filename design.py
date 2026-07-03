#!/usr/bin/env python3
"""
Nestor Voice — boucle d'iteration de timbre via ElevenLabs Voice Design.

Genere 3 apercus de voix a partir d'une description texte (prompt) et de la
phrase de reference, les sauve en .mp3 et met a jour la galerie HTML de
comparaison (gallery/index.html).

Usage:
    python3 design.py --label "majordome-froid" "<description de la voix>"
    python3 design.py --variant 1        # utilise un prompt de prompts.py

Puis ouvrir gallery/index.html pour ecouter/comparer.
Quand un apercu plait : python3 save.py <generated_voice_id>
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GALLERY = ROOT / "gallery"
AUDIO = GALLERY / "audio"
MANIFEST = GALLERY / "candidates.json"

API = "https://api.elevenlabs.io/v1/text-to-voice/create-previews"

# Phrase de reference commune a TOUS les candidats (comparaison a iso-texte).
REFERENCE_TEXT = (
    "Il est vingt-trois heures, Monsieur. J'ai baissé le chauffage et éteint "
    "les lumières du salon. J'ose espérer que cette fois, vous n'oublierez pas "
    "de fermer la porte du garage… comme hier, avant-hier, et l'ensemble des "
    "jours précédents."
)


def load_api_key() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip().lower() == "elevenlabs_api_key":
                return v.strip().strip('"').strip("'")
    key = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("elevenlabs_api_key")
    if key:
        return key
    sys.exit("Cle API introuvable (.env: elevenlabs_api_key)")


def create_previews(key: str, description: str, text: str, model_id: str) -> dict:
    body = {
        "voice_description": description,
        "text": text,
        "auto_generate_text": False,
        "model_id": model_id,
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        sys.exit(f"Erreur API {e.code} {e.reason}:\n{detail}")


def load_manifest() -> list:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return []


def render_html(batches: list) -> str:
    cards = []
    for b in reversed(batches):  # plus recent en haut
        cand_html = []
        for c in b["candidates"]:
            saved = " ✓ sauvegardee" if c.get("saved") else ""
            players = [f"""
            <div class="player"><span class="ptag">brut</span>
              <audio controls preload="none" src="{c['audio']}"></audio></div>"""]
            for preset, path in (c.get("synth") or {}).items():
                players.append(f"""
            <div class="player"><span class="ptag synth">{preset}</span>
              <audio controls preload="none" src="{path}"></audio></div>""")
            cand_html.append(f"""
        <div class="cand{' saved' if c.get('saved') else ''}">
          <div class="cand-head">Candidat {c['n']}{saved}</div>
          <div class="players">{''.join(players)}</div>
          <div class="cand-foot">
            <code class="vid" title="generated_voice_id">{c['generated_voice_id']}</code>
            <button onclick="navigator.clipboard.writeText('{c['generated_voice_id']}')">copier l'id</button>
          </div>
        </div>""")
        cards.append(f"""
    <section class="batch">
      <div class="batch-head">
        <span class="label">{b['label']}</span>
        <span class="meta">{b['timestamp']} · {b['model_id']}</span>
      </div>
      <p class="prompt">{b['prompt']}</p>
      <div class="cands">{''.join(cand_html)}</div>
    </section>""")
    return TEMPLATE.replace("{{CARDS}}", "\n".join(cards)).replace(
        "{{REF}}", REFERENCE_TEXT
    )


TEMPLATE = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nestor — galerie de voix</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 820px;
    margin: 0 auto; padding: 2rem 1rem; line-height: 1.5;
    background: Canvas; color: CanvasText; }
  h1 { font-size: 1.5rem; margin: 0 0 .25rem; }
  .ref { opacity: .7; font-style: italic; border-left: 3px solid; padding-left: .75rem;
    margin: 1rem 0 2rem; }
  .batch { border: 1px solid color-mix(in srgb, CanvasText 18%, transparent);
    border-radius: 12px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }
  .batch-head { display: flex; justify-content: space-between; align-items: baseline;
    gap: 1rem; flex-wrap: wrap; }
  .label { font-weight: 650; font-size: 1.05rem; }
  .meta { opacity: .55; font-size: .8rem; font-variant-numeric: tabular-nums; }
  .prompt { opacity: .8; font-size: .9rem; margin: .5rem 0 1rem; }
  .cands { display: grid; gap: .9rem; }
  .cand { padding: .7rem .85rem; border-radius: 9px;
    background: color-mix(in srgb, CanvasText 5%, transparent); }
  .cand.saved { outline: 2px solid seagreen; }
  .cand-head { font-weight: 600; font-size: .9rem; margin-bottom: .5rem; }
  .players { display: grid; gap: .4rem; }
  .player { display: flex; align-items: center; gap: .6rem; }
  .ptag { font-size: .7rem; text-transform: uppercase; letter-spacing: .04em;
    min-width: 62px; opacity: .6; }
  .ptag.synth { opacity: .9; color: mediumpurple; font-weight: 600; }
  audio { height: 34px; flex: 1; min-width: 220px; }
  .cand-foot { display: flex; align-items: center; gap: .6rem; margin-top: .5rem; }
  .vid { font-size: .72rem; opacity: .6; }
  button { font-size: .72rem; padding: .2rem .5rem; cursor: pointer;
    border-radius: 6px; border: 1px solid color-mix(in srgb, CanvasText 30%, transparent);
    background: transparent; color: inherit; }
  button:hover { background: color-mix(in srgb, CanvasText 12%, transparent); }
</style></head><body>
<h1>🐰🎩 Nestor — galerie de voix</h1>
<p class="ref">Phrase de reference : « {{REF}} »</p>
{{CARDS}}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("description", nargs="?", help="description texte de la voix (prompt)")
    ap.add_argument("--label", default=None, help="nom court du candidat")
    ap.add_argument("--variant", type=int, help="index de prompt dans prompts.py")
    ap.add_argument("--text", default=REFERENCE_TEXT, help="texte d'exemple (defaut: reference)")
    ap.add_argument("--model", default="eleven_multilingual_ttv_v2", help="model_id ElevenLabs")
    args = ap.parse_args()

    description, label = args.description, args.label
    if args.variant is not None:
        from prompts import PROMPTS
        p = PROMPTS[args.variant]
        description, label = p["prompt"], label or p["label"]
    if not description:
        sys.exit("Fournir une description ou --variant N")
    label = label or datetime.now().strftime("run-%H%M%S")

    key = load_api_key()
    AUDIO.mkdir(parents=True, exist_ok=True)

    print(f"→ Generation « {label} » (model {args.model})…")
    data = create_previews(key, description, args.text, args.model)
    previews = data.get("previews", [])
    if not previews:
        sys.exit(f"Aucun apercu retourne:\n{json.dumps(data, indent=2)}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    batch = {
        "batch_id": ts, "timestamp": ts, "label": label,
        "prompt": description, "model_id": args.model, "candidates": [],
    }
    for i, p in enumerate(previews, 1):
        fname = f"{ts}-{label}-{i}.mp3"
        (AUDIO / fname).write_bytes(base64.b64decode(p["audio_base_64"]))
        batch["candidates"].append({
            "n": i, "audio": f"audio/{fname}",
            "generated_voice_id": p["generated_voice_id"], "saved": False,
        })
        print(f"   candidat {i}: gallery/audio/{fname}  (id {p['generated_voice_id']})")

    batches = load_manifest()
    batches.append(batch)
    MANIFEST.write_text(json.dumps(batches, indent=2, ensure_ascii=False))
    (GALLERY / "index.html").write_text(render_html(batches))
    print(f"✓ Galerie mise a jour → gallery/index.html ({len(previews)} candidats)")


if __name__ == "__main__":
    main()
