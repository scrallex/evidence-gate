FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV EVIDENCE_GATE_AUDIT_ROOT=/data/audit
ENV EVIDENCE_GATE_KB_ROOT=/data/knowledge_bases

WORKDIR /opt/evidence-gate

COPY pyproject.toml README.md ./
COPY app ./app
COPY scripts ./scripts

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --upgrade pip \
    && python -m pip install .

EXPOSE 8000 8001

CMD ["sh", "./scripts/run_container.sh"]
