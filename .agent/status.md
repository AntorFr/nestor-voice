# Status — nestor-voice
> MàJ : 2026-09-26

**État :** passerelle TTS Wyoming en prod (image nestor-tts v0.4.2, voix nestor ElevenLabs + skippy Piper). Branche `fix/double-synthese` prête : fin des phrases dites 2 fois + vrai streaming phrase par phrase.

**Prochaines étapes :**
- [ ] Fusionner `fix/double-synthese`, taguer v0.4.3, bumper le tag dans k8s-home-lab
- [ ] Valider à l'oreille en conditions réelles (intonation / volume entre phrases)
- [ ] Skippy : garder le modèle Piper chargé en mémoire (aujourd'hui rechargé à chaque phrase)
- [ ] Clé ElevenLabs en clair dans k8s-home-lab → vrai Secret + rotation
