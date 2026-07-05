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
VOICE_ID = os.environ.get("NESTOR_VOICE_ID", "yY3c56wtYbsunxZsENmx")
MODEL = os.environ.get("NESTOR_MODEL", "eleven_multilingual_v2")
RATE = int(os.environ.get("NESTOR_SAMPLE_RATE", "22050"))
URI = os.environ.get("NESTOR_URI", "tcp://0.0.0.0:10200")
CACHE_DIR = Path(os.environ.get("NESTOR_CACHE_DIR", "/data/cache"))
VERSION = os.environ.get("NESTOR_VERSION", "1.0.0")

VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.75,
                  "style": 0.0, "use_speaker_boost": True}


def _tts_mp3(text: str) -> bytes:
    """Appel bloquant ElevenLabs -> mp3. Execute dans un thread."""
    url = (f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"
           "?output_format=mp3_44100_128")
    body = json.dumps({"text": text, "model_id": MODEL,
                       "voice_settings": VOICE_SETTINGS}).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json",
                 "Accept": "audio/mpeg"}, method="POST")
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _cache_key(text: str) -> str:
    h = hashlib.sha256()
    h.update("|".join([text, VOICE_ID, MODEL, str(RATE),
                       nestor_fx.filter_complex()]).encode())
    return h.hexdigest()


async def synth_pcm(text: str) -> bytes:
    """Texte -> PCM colore (via cache si possible)."""
    cache_file = CACHE_DIR / f"{_cache_key(text)}.pcm"
    if cache_file.exists():
        _LOGGER.info("cache HIT: %r", text[:60])
        return cache_file.read_bytes()

    _LOGGER.info("synthese: %r", text[:60])
    loop = asyncio.get_running_loop()
    mp3 = await loop.run_in_executor(None, _tts_mp3, text)

    proc = await asyncio.create_subprocess_exec(
        *nestor_fx.ffmpeg_pcm_cmd("pipe:0", RATE),
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)
    pcm, err = await proc.communicate(mp3)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg: {err.decode(errors='replace')}")

    cache_file.write_bytes(pcm)
    return pcm


class NestorHandler(AsyncEventHandler):
    def __init__(self, info_event: Event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info_event = info_event
        self._stream_text: list | None = None  # tampon de texte streaming

    async def handle_event(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            await self.write_event(self._info_event)
            return True

        # --- synthese one-shot (texte complet en un evenement) ---
        if Synthesize.is_type(event.type):
            await self._speak(Synthesize.from_event(event).text)
            return True

        # --- synthese streaming (comme Piper : le texte arrive en morceaux) ---
        if SynthesizeStart.is_type(event.type):
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
            await self._speak(text)
            await self.write_event(SynthesizeStopped().event())
            return True

        return True

    async def _speak(self, text: str) -> None:
        """Synthetise + colore + emet l'audio Wyoming."""
        text = " ".join((text or "").split()).strip()
        if not text:
            return
        try:
            pcm = await synth_pcm(text)
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
    if not API_KEY:
        raise SystemExit("ELEVENLABS_API_KEY manquant")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    info = Info(tts=[TtsProgram(
        name="nestor",
        description="Nestor — majordome domotique (ElevenLabs + coloration DSP)",
        attribution=Attribution(name="antor", url="https://antor.fr"),
        installed=True, version=VERSION,
        supports_synthesize_streaming=True,
        voices=[TtsVoice(
            name="nestor", description="Voix de Nestor (FR)",
            attribution=Attribution(name="ElevenLabs + DSP Nestor", url=""),
            installed=True, version=None, languages=["fr"])],
    )])

    server = AsyncServer.from_uri(URI)
    _LOGGER.info("Nestor TTS (Wyoming) sur %s — voix %s, modele %s",
                 URI, VOICE_ID, MODEL)
    await server.run(partial(NestorHandler, info.event()))


if __name__ == "__main__":
    asyncio.run(main())
