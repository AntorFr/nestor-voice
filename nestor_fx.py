#!/usr/bin/env python3
"""
Coloration OFFICIELLE de Nestor (source unique de verite).

Chaine validee le 2026-07-03 :
  voix ElevenLabs  ->  jouet-aigu-fort  ->  ring-mod 30 Hz @ 45%  ->  choeur + chambre (lush)

C'est cette recette qui sera rejouee dans la passerelle TTS (k8s), sur
ElevenLabs aujourd'hui comme sur Piper demain.
"""

# Etage 1 — "jouet-aigu-fort" : pitch +9%, petit haut-parleur, bitcrush, tremolo.
JAF = ("asetrate=48069,atempo=0.9174,aresample=44100,highpass=f=380,lowpass=f=4600,"
       "acrusher=bits=7:mix=0.5,tremolo=f=50:d=0.35")

# Etage 2 — ring-modulation (metal facon Nabaztag/GLaDOS).
RM_HZ, RM_WET = 30, 0.45

# Etage 3 — "lush" : choeur detune ample + grande chambre metallique.
EXTRA = ("chorus=0.6:0.9:60|70:0.4|0.32:0.25|0.4:2|1.5,"
         "aecho=0.8:0.88:29|47|71:0.45|0.35|0.25")

# Etage 4 — loudness comparable + limiteur de securite.
TAIL = ",dynaudnorm=f=150:g=15,alimiter=limit=0.95"


def filter_complex() -> str:
    dry = 1 - RM_WET
    return (f"[0:a]aformat=channel_layouts=mono,{JAF},asplit[d][w];"
            f"[w][1:a]amultiply[rm];"
            f"[d][rm]amix=inputs=2:weights={dry:.2f} {RM_WET:.2f}:normalize=0[base];"
            f"[base]{EXTRA}{TAIL}[out]")


def ffmpeg_cmd(src: str, dst: str) -> list:
    """Commande ffmpeg qui applique la coloration Nestor -> fichier (mp3/wav...)."""
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
            "-f", "lavfi", "-i", f"sine=frequency={RM_HZ}:sample_rate=44100",
            "-filter_complex", filter_complex(), "-map", "[out]", "-shortest", dst]


def ffmpeg_pcm_cmd(src: str = "pipe:0", rate: int = 22050) -> list:
    """Coloration Nestor -> PCM brut (s16le mono) sur stdout, pour Wyoming."""
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
            "-f", "lavfi", "-i", f"sine=frequency={RM_HZ}:sample_rate=44100",
            "-filter_complex", filter_complex(), "-map", "[out]", "-shortest",
            "-f", "s16le", "-ar", str(rate), "-ac", "1", "pipe:1"]
