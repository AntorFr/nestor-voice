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
import itertools
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from functools import partial
from pathlib import Path

from sentence_stream import SentenceBoundaryDetector
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
SKIPPY_PIPER_MODEL = os.environ.get("SKIPPY_PIPER_MODEL", "/models/skippy-v2-5h.onnx")
# Debit de la voix. PAR DEFAUT vide -> c'est le length_scale du .onnx.json qui decide :
# le debit est une propriete du MODELE, donc il voyage avec lui (reentrainer = juste
# livrer un nouveau json, sans toucher au code). La variable reste une soupape optionnelle
# pour forcer un debit (>1 = plus lent) sans remplacer le modele.
SKIPPY_LENGTH_SCALE = os.environ.get("SKIPPY_LENGTH_SCALE", "").strip()

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

    Le debit (length_scale) vient du .onnx.json ; SKIPPY_LENGTH_SCALE ne le surcharge
    que s'il est defini. ffmpeg detecte le format en aval, wav transparent.
    """
    model = VOICES[voice]["piper_model"]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        out = tf.name
    argv = [sys.executable, "-m", "piper", "-m", model,
            "--data-dir", os.path.dirname(model) or ".", "-f", out]
    if SKIPPY_LENGTH_SCALE:
        argv += ["--length-scale", SKIPPY_LENGTH_SCALE]
    try:
        proc = subprocess.run(argv, input=text.encode(), capture_output=True)
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
    ls = SKIPPY_LENGTH_SCALE if _backend(voice) == "piper" else ""
    h.update("|".join([text, _backend(voice), _voice_ident(voice), MODEL, ls, str(RATE),
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


_CONN_IDS = itertools.count(1)


def _sec(pcm_bytes: int) -> float:
    """Duree (s) d'un PCM s16le mono a RATE."""
    return pcm_bytes / 2 / RATE


class NestorHandler(AsyncEventHandler):
    """Un message = un flux audio (AudioStart .. AudioStop), synthetise phrase par
    phrase : la premiere phrase part des qu'elle est complete, sans attendre la fin
    du texte (streaming Wyoming, comme wyoming-piper).

    Trace de diagnostic : chaque connexion HA a un id [cN] ; on journalise chaque
    evenement recu (texte verbatim), chaque phrase emise, et un bilan a la
    deconnexion. Sert a localiser une parole doublee : deux connexions, un texte
    recu deux fois, ou un audio emis deux fois se lisent directement dans les logs.
    """

    def __init__(self, info_event: Event, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._info_event = info_event
        self._sbd: SentenceBoundaryDetector | None = None  # non-None = stream en cours
        self._stream_voice: str = DEFAULT_VOICE  # voix du stream en cours
        self._audio_started = False  # AudioStart deja emis pour le message en cours
        # --- trace ---
        self._cid = next(_CONN_IDS)
        self._t0 = time.monotonic()
        self._msg_sentences = 0  # phrases emises dans le message en cours
        self._msg_bytes = 0  # octets PCM emis dans le message en cours
        self._tot_messages = 0
        self._tot_sentences = 0
        self._tot_bytes = 0
        peer = self.writer.get_extra_info("peername")
        self._log("connexion de %s", f"{peer[0]}:{peer[1]}" if peer else "?")

    def _log(self, fmt: str, *args) -> None:
        _LOGGER.info("[c%d +%.2fs] " + fmt, self._cid, time.monotonic() - self._t0, *args)

    async def disconnect(self) -> None:
        if self._sbd is not None:
            self._log("ATTENTION stream non clos (pas de synthesize-stop recu)")
        self._log("deconnexion — %d message(s), %d phrase(s), %.2fs d'audio emis",
                  self._tot_messages, self._tot_sentences, _sec(self._tot_bytes))

    async def handle_event(self, event: Event) -> bool:
        try:
            return await self._handle(event)
        except Exception:
            self._log("ERREUR en traitant %s", event.type)
            raise

    async def _handle(self, event: Event) -> bool:
        if Describe.is_type(event.type):
            self._log("recu describe")
            await self.write_event(self._info_event)
            return True

        # --- synthese one-shot (texte complet en un evenement) ---
        if Synthesize.is_type(event.type):
            # En streaming, HA renvoie aussi le texte complet dans un Synthesize
            # (compat. anciens serveurs) entre Start et Stop : l'ignorer, sinon
            # chaque phrase est dite deux fois.
            syn = Synthesize.from_event(event)
            if self._sbd is not None:
                self._log("recu synthesize (texte complet, IGNORE car stream en cours): %r",
                          syn.text)
                return True
            voice = _resolve(getattr(syn.voice, "name", None))
            self._log("recu synthesize one-shot voix=%s (demandee %r): %r", voice,
                      getattr(syn.voice, "name", None), syn.text)
            sbd = SentenceBoundaryDetector()
            for sentence in [*sbd.add_chunk(syn.text), sbd.finish()]:
                await self._speak(sentence, voice)
            await self._end_audio()
            return True

        # --- synthese streaming (le texte arrive en morceaux depuis le LLM) ---
        if SynthesizeStart.is_type(event.type):
            start = SynthesizeStart.from_event(event)
            self._stream_voice = _resolve(getattr(start.voice, "name", None))
            if self._sbd is not None:
                self._log("ATTENTION synthesize-start alors qu'un stream est deja ouvert")
            self._sbd = SentenceBoundaryDetector()
            self._log("recu synthesize-start voix=%s (demandee %r)", self._stream_voice,
                      getattr(start.voice, "name", None))
            return True
        if SynthesizeChunk.is_type(event.type):
            chunk_text = SynthesizeChunk.from_event(event).text
            self._log("recu synthesize-chunk: %r", chunk_text)
            if self._sbd is None:
                self._log("ATTENTION chunk hors stream (pas de synthesize-start)")
                self._sbd = SentenceBoundaryDetector()
            for sentence in self._sbd.add_chunk(chunk_text):
                await self._speak(sentence, self._stream_voice)
            return True
        if SynthesizeStop.is_type(event.type):
            self._log("recu synthesize-stop")
            if self._sbd is not None:
                await self._speak(self._sbd.finish(), self._stream_voice)
                self._sbd = None
            await self._end_audio()
            await self.write_event(SynthesizeStopped().event())
            self._log("envoye synthesize-stopped")
            return True

        self._log("recu %s (non gere)", event.type)
        return True

    async def _speak(self, text: str, voice: str = DEFAULT_VOICE) -> None:
        """Synthetise + colore + emet l'audio d'une phrase (AudioStart a la 1re)."""
        text = " ".join((text or "").split()).strip()
        if not text:
            return
        t = time.monotonic()
        try:
            pcm = await synth_pcm(text, voice)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("[c%d] echec synthese: %r", self._cid, text)
            return

        if not self._audio_started:
            await self.write_event(AudioStart(rate=RATE, width=2, channels=1).event())
            self._audio_started = True
            self._log("envoye audio-start")
        chunk = 2048
        for i in range(0, len(pcm), chunk):
            await self.write_event(AudioChunk(
                rate=RATE, width=2, channels=1, audio=pcm[i:i + chunk]).event())
        self._msg_sentences += 1
        self._msg_bytes += len(pcm)
        self._log("phrase emise [%s] %.2fs d'audio (synthese %.2fs): %r",
                  voice, _sec(len(pcm)), time.monotonic() - t, text)

    async def _end_audio(self) -> None:
        """Clot le flux audio du message (rien si aucune phrase n'a ete emise)."""
        if self._audio_started:
            await self.write_event(AudioStop().event())
            self._audio_started = False
            self._log("envoye audio-stop — message: %d phrase(s), %.2fs d'audio",
                      self._msg_sentences, _sec(self._msg_bytes))
            self._tot_messages += 1
            self._tot_sentences += self._msg_sentences
            self._tot_bytes += self._msg_bytes
        else:
            self._log("message sans audio (aucune phrase emise)")
        self._msg_sentences = 0
        self._msg_bytes = 0


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
