FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

# install dependencies
RUN pip install --no-cache-dir \
    sentence-transformers>=2.2.0 \
    fastapi>=0.100.0 \
    uvicorn[standard]>=0.20.0 \
    pydantic>=2.0.0

# pre-download model and save in fp16 at build time so startup is fast
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ARG HF_TOKEN=""
ENV EMBEDDING_MODEL=$EMBEDDING_MODEL
# download model to HF cache at build time (no GPU needed, no save/convert)
RUN HF_TOKEN="${HF_TOKEN}" python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('${EMBEDDING_MODEL}')"

COPY server.py .

# skip all huggingface network calls at runtime — use cached model only
ENV HF_HUB_OFFLINE=1
ENV TRANSFORMERS_OFFLINE=1
ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
