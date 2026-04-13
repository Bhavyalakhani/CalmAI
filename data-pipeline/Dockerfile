FROM apache/airflow:2.8.1-python3.10

# suppress noisy git warning from mlflow
ENV GIT_PYTHON_REFRESH=quiet

# install build tools needed to compile C extensions (hdbscan, etc.) on ARM
USER root
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ build-essential && \
    rm -rf /var/lib/apt/lists/*
USER airflow

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code into the image so the VM only needs docker pull, not git pull
USER root
COPY --chown=airflow:root dags/ /opt/airflow/dags/
COPY --chown=airflow:root src/ /opt/airflow/src/
COPY --chown=airflow:root configs/ /opt/airflow/configs/
RUN mkdir -p /opt/airflow/plugins && chown airflow:root /opt/airflow/plugins
USER airflow

