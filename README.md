# nestor-voice

Voix domotiques servies à Home Assistant via une **passerelle Wyoming**. Chaque voix
= un **moteur TTS** (ElevenLabs *ou* Piper local) + une **coloration DSP** (ffmpeg :
pitch, ring-modulation, chœur, chambre métallique).

Voix exposées :
- **Nestor** — majordome très formel mais caustique (façon GLaDOS), timbre mi-lapin
  (Nabaztag) mi-synthétique. Moteur : **ElevenLabs**.
- **Skippy** — l'IA Elder arrogante et théâtrale (*Expeditionary Force*), timbre
  **clone vocal (Piper local)** + voile « canette » léger (ring-mod 110 Hz @ 12 %).
  Moteur : **Piper**, 100 % local, zéro crédit.

## Passerelle TTS (production)

`gateway/server.py` — serveur Wyoming pour Home Assistant :

```
texte + voix demandée  →  moteur TTS (ElevenLabs | Piper local)  →  coloration DSP (ffmpeg)  →  PCM  →  HA
```

- **Multi-voix, multi-moteur** : HA choisit la voix (`nestor` ou `skippy`) ; le serveur
  route vers le bon **backend** (`elevenlabs`/`piper`) + le bon filtre DSP. Voix par
  défaut si non précisée.
- **Skippy = Piper local** (`skippy-v2-5h.onnx`, clone vocal entraîné hors ligne) : aucune
  dépendance réseau, aucun crédit. Le débit (`length_scale=1.2`) est porté par le `.onnx.json`.
- **Nestor = ElevenLabs**, aligné sur l'intégration HA officielle (`eleven_multilingual_v2`).
- Cache disque : phrases déjà synthétisées resservies instantanément (latence nulle) ;
  la clé de cache intègre le backend + l'identité de la voix + le filtre.
- Registre des profils DSP dans `nestor_fx.py` (source de vérité), réutilisé partout.

### Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | requis **si** une voix ElevenLabs est exposée (nestor) |
| `NESTOR_VOICE_ID` | `yY3c56wtYbsunxZsENmx` | voice_id ElevenLabs de la voix `nestor` |
| `SKIPPY_PIPER_MODEL` | `/models/skippy-v2-5h.onnx` | modèle Piper de la voix `skippy` (+ `.onnx.json` accolé) |
| `SKIPPY_LENGTH_SCALE` | `1.2` | débit de skippy (>1 = plus lent) ; imposé au CLI Piper, indépendant du `.onnx.json`. `""` = laisser le json décider |
| `NESTOR_DEFAULT_VOICE` | `nestor` | voix utilisée si HA n'en précise pas |
| `NESTOR_MODEL` | `eleven_multilingual_v2` | modèle TTS ElevenLabs |
| `NESTOR_SAMPLE_RATE` | `22050` | fréquence du PCM renvoyé |
| `NESTOR_URI` | `tcp://0.0.0.0:10200` | écoute Wyoming |
| `NESTOR_CACHE_DIR` | `/data/cache` | cache PCM |

Le modèle Piper de Skippy (`.onnx` + `.onnx.json`) est **monté en volume** (`/models`),
**jamais commité dans ce repo public** ni embarqué dans l'image (il est versionné à part,
en privé). Le chart Helm doit fournir ce montage.

### Image & déploiement

Le workflow `.github/workflows/build-image.yml` build et publie l'image sur un tag `v*` :
`ghcr.io/antorfr/nestor-tts:<version>` (+ `latest`). Le chart Helm `nestor-voice`
vit dans [smart-home-charts](https://github.com/antorFr/smart-home-charts).

## Outils de conception (R&D)

Comment la voix a été fabriquée (nécessite `.env` avec `elevenlabs_api_key`) :

- `design.py` — Voice Design ElevenLabs (génère des candidats)
- `save.py` — promeut un candidat en voix permanente
- `nestorize.py` / `filterlab.py` — exploration des filtres de coloration
- `say.py` — fait parler Nestor sur n'importe quel texte (TTS + filtre)

## Roadmap

1. ✅ Figer le timbre (ElevenLabs Voice Design + filtre DSP)
2. 🚧 Intégration Home Assistant (passerelle Wyoming, satellites ESPHome)
3. ✅ **Skippy full local** : modèle **Piper** `skippy-v2-5h` (clone vocal entraîné
   hors ligne, corpus 5,12 h validé + normalisé). Backend `piper` ajouté à la passerelle
   (`_tts_piper`) à côté d'ElevenLabs ; le DSP + le cache + Wyoming n'ont pas bougé.
   Voile « léger » validé à l'oreille (profil `skippy` dans `nestor_fx.py`).
4. Nestor full local (même chemin : entraîner un Piper depuis le corpus ElevenLabs).
