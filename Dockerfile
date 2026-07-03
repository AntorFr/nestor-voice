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
    NESTOR_CACHE_DIR=/data/cache

EXPOSE 10200
VOLUME ["/data"]

CMD ["python", "server.py"]
