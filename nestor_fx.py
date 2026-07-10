#!/usr/bin/env python3
"""
Colorations DSP des voix (source unique de verite).

Registre de profils : chaque voix = etages pre-ring-mod + ring-mod (Hz, wet)
+ etage "extra" + tail (loudness/limiteur). La meme recette est rejouee dans la
passerelle TTS (k8s), sur ElevenLabs aujourd'hui comme sur Piper demain.

- nestor : jouet-aigu-fort -> ring-mod 30 Hz @ 45% -> choeur + chambre (lush).
  Chaine validee le 2026-07-03. NE PAS modifier (voix de prod figee).
- skippy : voile "canette" LEGER sur la voix Piper (clone vocal local) -> passe-bande
  + comb court + ring-mod 110 Hz @ 12%. Valide le 2026-07-10. Traduction ffmpeg d'un
  preset numpy "leger" recale sur le spectre de reference (HF>4k ~16%, centroide
  ~2050 Hz). L'ancien profil ElevenLabs lourd (robot-A, ring 90 Hz @ 45% + bitcrush)
  est garde sous "skippy_eleven_robot".
"""
from dataclasses import dataclass

TAIL = ",dynaudnorm=f=150:g=15,alimiter=limit=0.95"


@dataclass(frozen=True)
class VoiceFX:
    pre: str        # filtres appliques avant la ring-modulation
    rm_hz: float    # frequence de la porteuse (sine)
    rm_wet: float   # part de signal ring-mode dans le melange (0..1)
    extra: str      # filtres appliques apres le melange (sans virgule initiale)
    tail: str = TAIL


PROFILES = {
    # --- Nestor : jouet-aigu-fort + ring-mod grave + chambre lush (INCHANGE) ---
    "nestor": VoiceFX(
        pre=("asetrate=48069,atempo=0.9174,aresample=44100,highpass=f=380,"
             "lowpass=f=4600,acrusher=bits=7:mix=0.5,tremolo=f=50:d=0.35"),
        rm_hz=30, rm_wet=0.45,
        extra=("chorus=0.6:0.9:60|70:0.4|0.32:0.25|0.4:2|1.5,"
               "aecho=0.8:0.88:29|47|71:0.45|0.35|0.25"),
    ),
    # --- Skippy : voile "canette" LEGER sur la voix Piper (clone vocal local) ---
    # Passe-bande petit-HP (180-7500) + comb court 5 ms (resonance boitier) +
    # ring-mod 110 Hz a seulement 12% : on garde le timbre de la voix, on ajoute juste
    # le grain machine. Recale sur un preset numpy "leger" valide a l'oreille (2026-07-10).
    "skippy": VoiceFX(
        pre="highpass=f=180,lowpass=f=7500,aecho=0.9:0.9:5:0.22",
        rm_hz=110, rm_wet=0.12,
        extra="",
    ),
    # --- Ancien Skippy ElevenLabs (robot lourd) : garde pour reference / A-B ---
    "skippy_eleven_robot": VoiceFX(
        pre=("highpass=f=170,lowpass=f=7500,equalizer=f=1700:t=q:w=3:g=4,"
             "equalizer=f=2600:t=q:w=4:g=3,aecho=0.85:0.85:4:0.4,"
             "chorus=0.7:0.9:55:0.4:0.35:2.2,acrusher=bits=5:mix=0.4"),
        rm_hz=90, rm_wet=0.45,
        extra="acompressor=threshold=0.1:ratio=4:makeup=3",
    ),
}

DEFAULT_VOICE = "nestor"


def filter_complex(voice: str = DEFAULT_VOICE) -> str:
    fx = PROFILES[voice]
    dry = 1 - fx.rm_wet
    # extra + tail attaches au label [base]. tail commence par ',' (suit un extra
    # non vide) ; si extra est vide, on retire cette virgule de tete pour ne pas
    # laisser un filtre vide ([base],dynaudnorm -> ffmpeg "No such filter: ''").
    post = f"{fx.extra}{fx.tail}" if fx.extra else fx.tail.lstrip(",")
    return (f"[0:a]aformat=channel_layouts=mono,{fx.pre},asplit[d][w];"
            f"[w][1:a]amultiply[rm];"
            f"[d][rm]amix=inputs=2:weights={dry:.2f} {fx.rm_wet:.2f}:normalize=0[base];"
            f"[base]{post}[out]")


def _sine(voice: str) -> str:
    return f"sine=frequency={PROFILES[voice].rm_hz}:sample_rate=44100"


def ffmpeg_cmd(src: str, dst: str, voice: str = DEFAULT_VOICE) -> list:
    """Applique la coloration <voice> -> fichier (mp3/wav...)."""
    return ["ffmpeg", "-y", "-loglevel", "error", "-i", src,
            "-f", "lavfi", "-i", _sine(voice),
            "-filter_complex", filter_complex(voice), "-map", "[out]", "-shortest", dst]


def ffmpeg_pcm_cmd(src: str = "pipe:0", rate: int = 22050,
                   voice: str = DEFAULT_VOICE) -> list:
    """Coloration <voice> -> PCM brut (s16le mono) sur stdout, pour Wyoming."""
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src,
            "-f", "lavfi", "-i", _sine(voice),
            "-filter_complex", filter_complex(voice), "-map", "[out]", "-shortest",
            "-f", "s16le", "-ar", str(rate), "-ac", "1", "pipe:1"]
