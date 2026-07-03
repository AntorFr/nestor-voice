#!/usr/bin/env python3
"""
Labo de filtres — couche « vaisseau spatial » par-dessus la base retenue.

Base figee : jouet-aigu-fort + ring-mod 30 Hz dose 45%.
On empile ensuite differents effets sci-fi (interphone, choeur, reverb
metallique, flanger, phaser...) pour rendre Nestor plus synthetique.

Usage:
    python3 filterlab.py                       # voix par defaut (majordome-glacial c2)
    python3 filterlab.py audio/xxx.mp3         # une autre voix de base
"""
import subprocess
import sys
from pathlib import Path

from design import GALLERY

BASE_DEFAULT = "audio/20260703-153923-majordome-glacial-2.mp3"
BRUT_REF = BASE_DEFAULT
ROBOT_V0_REF = "audio/synth/20260703-153923-majordome-glacial-2__robot.mp3"

OUT = GALLERY / "filter-lab"
TAIL = ",dynaudnorm=f=150:g=15,alimiter=limit=0.95"

# Base figee : jouet-aigu-fort + ring-mod 30 Hz @ 45%.
JAF = ("asetrate=48069,atempo=0.9174,aresample=44100,highpass=f=380,lowpass=f=4600,"
       "acrusher=bits=7:mix=0.5,tremolo=f=50:d=0.35")
BASE_HZ, BASE_WET = 30, 0.45

# --- Couches "vaisseau spatial" : (nom, desc, chaine ajoutee) ----------------
SPACE = [
    ("space-base", "Base seule (rappel, sans effet ajoute).", "anull"),
    ("space-chorus", "Choeur detune seul (repere).",
     "chorus=0.7:0.9:55:0.4:0.25:2"),
    ("space-chamber", "Chambre metallique seule (repere).",
     "aecho=0.85:0.88:29|43|59:0.4|0.3|0.2"),
    ("space-cc-soft", "MIX leger : choeur discret + petite chambre.",
     "chorus=0.7:0.9:50:0.3:0.2:1.5,aecho=0.85:0.9:23|37:0.3|0.2"),
    ("space-cc", "MIX medium : choeur + chambre (dose de reference).",
     "chorus=0.7:0.9:55:0.4:0.25:2,aecho=0.85:0.88:29|43|59:0.4|0.3|0.2"),
    ("space-cc-lush", "MIX riche : choeur ample + grande chambre metallique.",
     "chorus=0.6:0.9:60|70:0.4|0.32:0.25|0.4:2|1.5,"
     "aecho=0.8:0.88:29|47|71:0.45|0.35|0.25"),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg a echoue:\n{' '.join(cmd)}\n{r.stderr}")


def render(items):
    rows = []
    for name, desc, chain in items:
        rows.append(f"""
    <div class="fx">
      <div class="fx-head"><span class="fx-name">{name}</span></div>
      <p class="fx-desc">{desc}</p>
      <audio controls preload="none" src="filter-lab/{name}.mp3"></audio>
      <details><summary>chaine ffmpeg</summary><code>{chain}</code></details>
    </div>""")
    return (HTML.replace("{{ROWS}}", "\n".join(rows))
                .replace("{{BRUT}}", BRUT_REF).replace("{{ROBOT}}", ROBOT_V0_REF))


HTML = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nestor — labo vaisseau</title>
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 780px;
    margin: 0 auto; padding: 2rem 1rem; line-height: 1.5; background: Canvas; color: CanvasText; }
  h1 { font-size: 1.4rem; margin: 0 0 .3rem; }
  .sub { opacity: .65; margin: 0 0 1.5rem; font-size: .9rem; }
  .ref { border: 1px dashed color-mix(in srgb, CanvasText 30%, transparent);
    border-radius: 10px; padding: .8rem 1rem; margin-bottom: 1.5rem; }
  .fx { border: 1px solid color-mix(in srgb, CanvasText 16%, transparent);
    border-radius: 10px; padding: .7rem .9rem; margin-bottom: .8rem;
    background: color-mix(in srgb, CanvasText 4%, transparent); }
  .fx-head { display: flex; align-items: baseline; gap: .6rem; }
  .fx-name { font-weight: 650; color: mediumpurple; }
  .fx-desc { margin: .3rem 0 .5rem; font-size: .85rem; opacity: .8; }
  audio { width: 100%; height: 34px; }
  details { margin-top: .4rem; }
  summary { font-size: .72rem; opacity: .55; cursor: pointer; }
  code { font-size: .68rem; opacity: .7; word-break: break-all; display: block; margin-top: .3rem; }
</style></head><body>
<h1>🚀 Nestor — labo vaisseau</h1>
<p class="sub">Base figee : <b>jouet-aigu-fort + ring-mod 30 Hz 45%</b>. On empile les effets sci-fi.</p>
<div class="ref">
  <div class="fx-head"><span class="fx-name">brut</span></div>
  <audio controls preload="none" src="{{BRUT}}"></audio>
  <div class="fx-head" style="margin-top:.6rem"><span class="fx-name">robot v0</span></div>
  <audio controls preload="none" src="{{ROBOT}}"></audio>
</div>
{{ROWS}}
</body></html>"""


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else GALLERY / BASE_DEFAULT
    if not base.is_absolute():
        base = GALLERY / base
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.mp3"):
        old.unlink()

    dry_w = 1 - BASE_WET
    items = []
    for name, desc, extra in SPACE:
        dst = OUT / f"{name}.mp3"
        fc = (f"[0:a]aformat=channel_layouts=mono,{JAF},asplit[d][w];"
              f"[w][1:a]amultiply[rm];"
              f"[d][rm]amix=inputs=2:weights={dry_w:.2f} {BASE_WET:.2f}:normalize=0[base];"
              f"[base]{extra}{TAIL}[out]")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(base),
             "-f", "lavfi", "-i", f"sine=frequency={BASE_HZ}:sample_rate=44100",
             "-filter_complex", fc, "-map", "[out]", "-shortest", str(dst)])
        print(f"   {name}")
        items.append((name, desc, extra))

    (GALLERY / "filter-lab.html").write_text(render(items))
    print(f"✓ {len(items)} variantes → gallery/filter-lab.html")


if __name__ == "__main__":
    main()
