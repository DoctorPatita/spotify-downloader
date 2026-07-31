FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV DENO_INSTALL="/usr/local"
ENV PATH="$DENO_INSTALL/bin:$PATH"

RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deno.land/install.sh | sh -s -- -y

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY . .

RUN useradd -m appuser
USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["playlist"]
