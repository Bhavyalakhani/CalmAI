FROM apache/airflow:2.8.1-python3.10

# suppress noisy git warning from mlflow
ENV GIT_PYTHON_REFRESH=quiet

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
