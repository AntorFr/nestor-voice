# nestor-voice

Voix domotiques servies à Home Assistant via une **passerelle Wyoming**. Chaque voix
= une **voix ElevenLabs figée** + une **coloration DSP** (ffmpeg : pitch, ring-modulation,
chœur, chambre métallique).

Voix exposées :
- **Nestor** — majordome très formel mais caustique (façon GLaDOS), timbre mi-lapin
  (Nabaztag) mi-synthétique.
- **Skippy** — l'IA Elder arrogante et théâtrale (*Expeditionary Force*), baryton
  « canette » façon Luchini + patine métallique (ring-mod 90 Hz).

## Passerelle TTS (production)

`gateway/server.py` — serveur Wyoming pour Home Assistant :

```
texte + voix demandée  →  ElevenLabs (voice_id)  →  coloration DSP (ffmpeg)  →  PCM  →  HA
```

- **Multi-voix** : HA choisit la voix dans son sélecteur (`nestor` ou `skippy`) ; le
  serveur route vers le bon `voice_id` + le bon filtre. Voix par défaut si non précisée.
- Aligné sur l'intégration HA ElevenLabs officielle (`eleven_multilingual_v2`, `mp3_44100_128`).
- Cache disque : les phrases déjà synthétisées sont resservies instantanément
  (latence nulle, zéro crédit) ; la clé de cache intègre la voix.
- Registre des profils DSP dans `nestor_fx.py` (source de vérité), réutilisé partout.

### Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `ELEVENLABS_API_KEY` | — | **requis** |
| `NESTOR_VOICE_ID` | `yY3c56wtYbsunxZsENmx` | voice_id ElevenLabs de la voix `nestor` |
| `SKIPPY_VOICE_ID` | `xwOTosRH5SpGGYsxw4Jt` | voice_id ElevenLabs de la voix `skippy` |
| `NESTOR_DEFAULT_VOICE` | `nestor` | voix utilisée si HA n'en précise pas |
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
