#!/usr/bin/env python3
"""
Passerelle TTS Nestor — serveur Wyoming pour Home Assistant.

A chaque phrase demandee par HA (Assist / satellite ESPHome) :
    texte -> ElevenLabs (voix figee) -> coloration Nestor (ffmpeg) -> PCM -> HA

Aligne sur l'integration officielle HA ElevenLabs :
    model eleven_multilingual_v2, output mp3_44100_128,
    voice_settings stability=0.5 similarity=0.75 style=0 speaker_boost=on.

Cache disque : les phrases deja synthetisees sont resservies instantanement
(latence nulle + zero credit ElevenLabs). Le cache s'invalide si le filtre change.

Config par variables d'environnement (voir plus bas).

Phase 3 : pour passer a Piper local, remplacer _tts_mp3() par un appel Piper ;
le reste (Wyoming + filtre + cache) ne bouge pas.
"""
import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from functools import partial
from pathlib import Path

from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.event import Event
from wyoming.info import Attribution, Describe, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncEventHandler, AsyncServer
from wyoming.tts import (
    Synthesize, SynthesizeChunk, SynthesizeStart, SynthesizeStop,
    SynthesizeStopped)

import nestor_fx

_LOGGER = logging.getLogger("nestor")

API_KEY = os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("elevenlabs_api_key")
MODEL = os.environ.get("NESTOR_MODEL", "eleven_multilingual_v2")
RATE = int(os.environ.get("NESTOR_SAMPLE_RATE", "22050"))
URI = os.environ.get("NESTOR_URI", "tcp://0.0.0.0:10200")
CACHE_DIR = Path(os.environ.get("NESTOR_CACHE_DIR", "/data/cache"))
VERSION = os.environ.get("NESTOR_VERSION", "1.0.0")

# Modele Piper local pour Skippy (clone vocal, entraine hors ligne).
# Le .onnx.json accole porte length_scale=1.2 (debit de la voix).
SKIPPY_PIPER_MODEL = os.environ.get("SKIPPY_PIPER_MODEL", "/models/skippy-v2-5h.onnx")

# Registre des voix exposees a HA. Chaque voix a un "backend" :
#   - "elevenlabs" : voice_id + settings (nestor)
#   - "piper"      : modele .onnx local (skippy)
# Le profil DSP de meme nom vit dans nestor_fx.PROFILES.
VOICES = {
    "nestor": {
        "backend": "elevenlabs",
        "voice_id": os.environ.get("NESTOR_VOICE_ID", "yY3c56wtYbsunxZsENmx"),
        "settings": {"stability": 0.5, "similarity_boost": 0.75,
                     "style": 0.0, "use_speaker_boost": True},
        "description": "Voix de Nestor (FR) — majordome domotique caustique",
    },
    "skippy": {
        "backend": "piper",
        "piper_model": SKIPPY_PIPER_MODEL,
        "description": "Voix de Skippy le Magnifique (FR) — clone vocal local + voile canette",
    },
}
DEFAULT_VOICE = os.environ.get("NESTOR_DEFAULT_VOICE", "nestor")


def _backend(voice: str) -> str:
    return VOICES[voice].get("backend", "elevenlabs")


def _voice_ident(voice: str) -> str:
    """Identite de la voix pour la cle de cache (voice_id ou chemin du modele)."""
    cfg = VOICES[voice]
    return cfg.get("voice_id") or cfg.get("piper_model", "")


def _resolve(name: str | None) -> str:
    """Nom de voix demande par HA -> cle connue (sinon voix par defaut)."""
    return name if name in VOICES else DEFAULT_VOICE


def _tts_mp3(text: str, voice: str) -> bytes:
    """Appel bloquant ElevenLabs -> mp3. Execute dans un thread."""
    cfg = VOICES[voice]
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}"
           "?output_format=mp3_44100_128")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": cfg["settings"]}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _tts_piper(text: str, voice: str) -> bytes:
    """Synthese locale Piper -> wav (bytes). Execute dans un thread.

    Le debit (length_scale) est lu depuis le .onnx.json accole, pas impose ici.
    ffmpeg detecte le format en aval, donc renvoyer du wav est transparent.
    """
    model = VOICES[voice]["piper_model"]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        out = tf.name
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "piper", "-m", model,
             "--data-dir", os.path.dirname(model) or ".", "-f", out],
            input=text.encode(), capture_output=True)
        if proc.returncode != 0 or not os.path.getsize(out):
            raise RuntimeError(f"piper: {proc.stderr.decode(errors='replace')[-300:]}")
        return Path(out).read_bytes()
    finally:
        try:
            os.remove(out)
        except OSError:
            pass


def _tts_audio(text: str, voice: str) -> bytes:
    """Audio encode (mp3 ou wav) selon le backend de la voix."""
    return _tts_piper(text, voice) if _backend(voice) == "piper" else _tts_mp3(text, voice)


def _cache_key(text: str, voice: str) -> str:
    h = hashlib.sha256()
    # identite = voice_id (ElevenLabs) OU chemin du modele (Piper) ; le backend
    # entre dans la cle pour ne pas resservir un audio d'une source differente.
    h.update("|".join([text, _backend(voice), _voice_ident(voice), MODEL, str(RATE),
                       nestor_fx.filter_complex(voice)]).encode())
    return h.hexdigest()


async def synth_pcm(text: str, voice: str) -> bytes:
    """Texte -> PCM colore pour <voice> (via cache si possible)."""
    cache_file = CACHE_DIR / f"{_cache_key(text, voice)}.pcm"
    if cache_file.exists():
        _LOGGER.info("cache HIT [%s]: %r", voice, text[:60])
        return cache_file.read_bytes()

    _LOGGER.info("synthese [%s/%s]: %r", voice, _backend(voice), text[:60])
    loop = asyncio.get_running_loop()
    audio = await loop.run_in_executor(None, _tts_audio, text, voice)

    proc = await asyncio.create_subprocess_exec(
        *nestor_fx.ffmpeg_pcm_cmd("pipe:0", RATE, voice),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    pcm, err = await proc.communicate(audio)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg: {err.decode(errors='replace')}")

    cache_file.write_bytes(pcm)
    return pcm


class NestorHandler(AsyncEventHandler):
    def __init__(self, info_event: Event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info_event = info_event
        self._stream_text: list | None = None  # tampon de texte streaming
        self._stream_voice: str = DEFAULT_VOICE  # voix du stream en cours

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info_event)
            return True

        # --- synthese one-shot (texte complet en un evenement) ---
        if Synthesize.is_type(event.type):
            syn = Synthesize.from_event(event)
            await self._speak(syn.text, _resolve(getattr(syn.voice, "name", None)))
            return True

        # --- synthese streaming (comme Piper : le texte arrive en morceaux) ---
        if SynthesizeStart.is_type(event.type):
            start = SynthesizeStart.from_event(event)
            self._stream_voice = _resolve(getattr(start.voice, "name", None))
            self._stream_text = []
            return True
        if SynthesizeChunk.is_type(event.type):
            if self._stream_text is None:
                self._stream_text = []
            self._stream_text.append(SynthesizeChunk.from_event(event).text)
            return True
        if SynthesizeStop.is_type(event.type):
            text = "".join(self._stream_text or [])
            self._stream_text = None
            await self._speak(text, self._stream_voice)
            await self.write_event(SynthesizeStopped().event())
            return True

        return True

    async def _speak(self, text: str, voice: str = DEFAULT_VOICE) -> None:
        """Synthetise + colore + emet l'audio Wyoming."""
        text = " ".join((text or "").split()).strip()
        if not text:
            return
        try:
            pcm = await synth_pcm(text, voice)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("echec synthese")
            return

        await self.write_event(AudioStart(rate=RATE, width=2, channels=1).event())
        chunk = 2048
        for i in range(0, len(pcm), chunk):
            await self.write_event(AudioChunk(
                rate=RATE, width=2, channels=1, audio=pcm[i:i + chunk]).event())
        await self.write_event(AudioStop().event())


async def main() -> None:
    logging.basicConfig(level=os.environ.get("NESTOR_LOG", "INFO"))
    # La cle n'est requise que si une voix passe reellement par ElevenLabs.
    if any(_backend(v) == "elevenlabs" for v in VOICES) and not API_KEY:
        raise SystemExit("ELEVENLABS_API_KEY manquant (requis par une voix ElevenLabs)")
    for v in VOICES:
        if _backend(v) == "piper" and not Path(VOICES[v]["piper_model"]).exists():
            _LOGGER.warning("voix %s: modele Piper introuvable (%s)", v, VOICES[v]["piper_model"])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    info = Info(tts=[TtsProgram(
        name="nestor",
        description="Nestor & Skippy — voix domotiques (ElevenLabs + coloration DSP)",
        attribution=Attribution(name="antor", url="https://antor.fr"),
        installed=True, version=VERSION,
        supports_synthesize_streaming=True,
        voices=[TtsVoice(
            name=name, description=cfg["description"],
            attribution=Attribution(name="ElevenLabs + DSP", url=""),
            installed=True, version=None, languages=["fr"])
            for name, cfg in VOICES.items()],
    )])

    server = AsyncServer.from_uri(URI)
    _LOGGER.info("TTS Wyoming sur %s — voix: %s, modele %s",
                 URI, ", ".join(VOICES), MODEL)
    await server.run(partial(NestorHandler, info.event()))


if __name__ == "__main__":
    asyncio.run(main())
