FROM pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime

WORKDIR /app

# install dependencies
RUN pip install --no-cache-dir \
    sentence-transformers>=2.2.0 \
    fastapi>=0.100.0 \
    uvicorn[standard]>=0.20.0 \
    pydantic>=2.0.0

# pre-download the model at build time so startup is fast
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV EMBEDDING_MODEL=$EMBEDDING_MODEL
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

COPY server.py .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
