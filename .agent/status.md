# Status — nestor-voice
> MàJ : 2026-10-08

**État :** passerelle TTS Wyoming en prod (image nestor-tts v0.4.3, voix nestor ElevenLabs + skippy Piper) : phrases plus doublées, streaming phrase par phrase.

**Prochaines étapes :**
- [ ] Paroles encore doublées sur Voice Bureau (1 seule synthèse côté passerelle) : lire la trace `[cN]` de v0.4.5 sur un test réel pour localiser le doublon
- [ ] Valider à l'oreille en conditions réelles (intonation / volume entre phrases)
- [ ] Skippy : garder le modèle Piper chargé en mémoire (aujourd'hui rechargé à chaque phrase)
- [ ] Clé ElevenLabs en clair dans k8s-home-lab → vrai Secret + rotation
