FROM python:3.12-slim

# ffmpeg = moteur de la coloration Nestor
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Filtre (source unique de verite) + serveur Wyoming
COPY nestor_fx.py .
COPY gateway/server.py .

ENV NESTOR_URI=tcp://0.0.0.0:10200 \
    NESTOR_CACHE_DIR=/data/cache \
    SKIPPY_PIPER_MODEL=/models/skippy-v2-5h.onnx \
    SKIPPY_LENGTH_SCALE=1.2

# Modele Piper de skippy : monte en volume (/models via le chart Helm), JAMAIS
# embarque dans cette image publique. Doit contenir .onnx ET .onnx.json.
EXPOSE 10200
VOLUME ["/data", "/models"]

CMD ["python", "server.py"]
