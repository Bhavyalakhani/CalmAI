"""
Airflow DAG for mental health data pipeline.
Two tasks: download datasets and generate synthetic journals.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
import logging
import sys

logger = logging.getLogger(__name__)
sys.path.insert(0, '/opt/airflow/src')
sys.path.insert(0, '/opt/airflow/src/acquisition')

default_args = {
    "owner": "calmai",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

# Wrapper function for generate_journals
def generate_journals_callable(**context):
    """
    Wrapper to call the run() function from generate_journals.py
    """
    # Import inside the function to avoid DAG parsing issues
    from acquisition.generate_journals import run
    
    logger.info("Starting journal generation...")
    
    # Call run() directly (not main(), which expects CLI args)
    output_path = run(skip_existing=False)
    
    logger.info(f"Journal generation completed: {output_path}")
    
    # Push to XCom for downstream tasks
    context['ti'].xcom_push(key='journals_path', value=str(output_path))
    
    return str(output_path)

with DAG(
    dag_id="mental_health_data_pipeline",
    default_args=default_args,
    description="Download datasets and generate synthetic journals",
    schedule_interval=None,  # Manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["mental-health", "data-pipeline"],
) as dag:

    generate_journals_task = PythonOperator(
        task_id="generate_journals",
        python_callable=generate_journals_callable,
        provide_context=True,  # Pass context to the callable
    )

    generate_journals_task