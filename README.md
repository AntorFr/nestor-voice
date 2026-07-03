# nestor-voice

Voix de **Nestor**, l'assistant domotique : un majordome très formel mais caustique
(façon GLaDOS), au timbre mi-lapin (Nabaztag) mi-synthétique.

Le rendu final = une **voix ElevenLabs figée** + une **coloration DSP** (ffmpeg :
pitch, ring-modulation, chœur, chambre métallique), servie à Home Assistant via une
**passerelle Wyoming**.

## Passerelle TTS (production)

`gateway/server.py` — serveur Wyoming pour Home Assistant :

```
texte  →  ElevenLabs (voice_id figé)  →  coloration Nestor (ffmpeg)  →  PCM  →  HA
```

- Aligné sur l'intégration HA ElevenLabs officielle (`eleven_multilingual_v2`,
  `mp3_44100_128`, voice_settings stability 0.5 / similarity 0.75 / style 0 / speaker_boost).
- Cache disque : les phrases déjà synthétisées sont resservies instantanément
  (latence nulle, zéro crédit).
- Filtre défini une seule fois dans `nestor_fx.py` (source de vérité), réutilisé partout.

### Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | **requis** |
| `NESTOR_VOICE_ID` | `yY3c56wtYbsunxZsENmx` | voix ElevenLabs figée |
| `NESTOR_MODEL` | `eleven_multilingual_v2` | modèle TTS |
| `NESTOR_SAMPLE_RATE` | `22050` | fréquence du PCM renvoyé |
| `NESTOR_URI` | `tcp://0.0.0.0:10200` | écoute Wyoming |
| `NESTOR_CACHE_DIR` | `/data/cache` | cache PCM |

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
3. Cible full local : entraîner un modèle **Piper** (la voix ElevenLabs sert à
   générer le corpus). Seam : remplacer `_tts_mp3()` dans la passerelle, le reste
   ne bouge pas.
