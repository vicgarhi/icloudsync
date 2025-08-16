FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates tzdata git && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      "pyicloud-ipd==0.10.2" \
      "pytz==2022.7.1" \
      "tqdm>=4.66" \
      "tenacity>=8.2" \
      "PyYAML>=6.0" \
      "requests>=2.31" \
      "piexif>=1.1" \
      "python-dateutil>=2.8" \
      "typer>=0.12,<0.16"

WORKDIR /appsrc
RUN git clone --depth 1 https://github.com/vicgarhi/icloudsync.git /appsrc
RUN pip install --no-cache-dir --no-deps .

ENTRYPOINT ["icloudsync"]
