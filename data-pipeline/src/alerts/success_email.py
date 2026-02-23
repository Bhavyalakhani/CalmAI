# html success email sent after the pipeline completes
# includes task durations table, mongodb stats

from airflow.utils.email import send_email
from datetime import datetime, timezone


RECIPIENTS = [
    "gala.jain@northeastern.edu",
    "lakhani.bha@northeastern.edu",
    "shah.mir@northeastern.edu",
    "mane.prit@northeastern.edu",
    "adhikari.t@northeastern.edu",
]

MINION_GIF_URL = "https://media.giphy.com/media/v1.Y2lkPTc5MGI3NjExcTl0cWRsMjVqcHB6Ynlxd2I2NTF6b2k4OGl2ZXN4NnN0MnF3aSZlcD12MV9naWZzX3NlYXJjaCZjdD1n/11sBLVxNs7v6WA/giphy.gif"

# task display order for the duration table
TASK_ORDER = [
    ("start", "Start"),
    ("download_conversations", "Download Conversations"),
    ("generate_journals", "Generate Journals"),
    ("preprocess_conversations", "Preprocess Conversations"),
    ("preprocess_journals", "Preprocess Journals"),
    ("validate_data", "Validate Data"),
    ("embed_conversations", "Embed Conversations"),
    ("embed_journals", "Embed Journals"),
    ("train_journal_model", "Train Journal Topic Model"),
    ("train_conversation_model", "Train Conversation Topic Model"),
    ("bias_conversations", "Bias Analysis — Conversations"),
    ("bias_journals", "Bias Analysis — Journals"),
    ("compute_patient_analytics", "Compute Patient Analytics"),
    ("store_to_mongodb", "Store to MongoDB"),
]

# task order for incoming (micro-batch) pipeline
TASK_ORDER_INCOMING = [
    ("start", "Start"),
    ("fetch_new_entries", "Fetch New Entries"),
    ("preprocess_entries", "Preprocess"),
    ("validate_entries", "Validate"),
    ("embed_entries", "Embed"),
    ("store_to_mongodb", "Store to MongoDB"),
    ("update_analytics", "Update Analytics"),
    ("mark_processed", "Mark Processed"),
]


def _format_duration(seconds):
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _build_task_rows(ti):
    rows = []
    for task_id, label in TASK_ORDER:
        duration = ti.xcom_pull(task_ids=task_id, key="duration")
        duration_str = _format_duration(duration)
        rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{label}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center;'>{duration_str}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def _build_task_rows_incoming(ti):
    rows = []
    for task_id, label in TASK_ORDER_INCOMING:
        duration = ti.xcom_pull(task_ids=task_id, key="duration")
        duration_str = _format_duration(duration)
        rows.append(
            f"<tr>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;'>{label}</td>"
            f"<td style='padding:8px 12px;border-bottom:1px solid #eee;text-align:center;'>{duration_str}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def send_success_email(**context):
    ti = context["ti"]
    dag_run = context.get("dag_run")

    run_id = ti.xcom_pull(task_ids="start", key="run_id") or "unknown"
    execution_date = dag_run.execution_date if dag_run else datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    stats = ti.xcom_pull(task_ids="store_to_mongodb", key="collection_stats") or {}
    insert_results = ti.xcom_pull(task_ids="store_to_mongodb", key="insert_results") or {}

    task_rows = _build_task_rows(ti)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:650px;margin:0 auto;">
        <div style="background:#4CAF50;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;">CalmAI Static Data Pipeline Succeeded</h1>
        </div>

        <div style="padding:20px;background:#f9f9f9;border:1px solid #ddd;">
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
                <tr>
                    <td style="padding:6px 0;"><b>Run ID:</b></td>
                    <td>{run_id}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Execution Date:</b></td>
                    <td>{execution_date}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Finished At:</b></td>
                    <td>{finished_at}</td>
                </tr>
            </table>

            <h3 style="color:#333;border-bottom:2px solid #4CAF50;padding-bottom:6px;">Task Durations</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#4CAF50;color:white;">
                    <th style="padding:8px 12px;text-align:left;">Task</th>
                    <th style="padding:8px 12px;text-align:center;">Duration</th>
                </tr>
                {task_rows}
            </table>

            <h3 style="color:#333;border-bottom:2px solid #4CAF50;padding-bottom:6px;margin-top:20px;">MongoDB Stats</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr>
                    <td style="padding:6px 0;"><b>Insert Results:</b></td>
                    <td>{insert_results}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Collection Stats:</b></td>
                    <td>{stats}</td>
                </tr>
            </table>

            <div style="text-align:center;margin-top:24px;">
                <img src="{MINION_GIF_URL}" alt="Minions Celebrating" style="max-width:400px;border-radius:8px;" />
                <p style="color:#888;font-size:13px;margin-top:8px;">The minions approve this pipeline run.</p>
            </div>
        </div>

        <div style="background:#333;color:#aaa;padding:12px;text-align:center;font-size:12px;border-radius:0 0 8px 8px;">
            CalmAI Data Pipeline &mdash; Automated Notification
        </div>
    </div>
    """

    send_email(
        to=RECIPIENTS,
        subject=f"CalmAI Pipeline Succeeded — Run {run_id}",
        html_content=html,
    )


def send_incoming_success_email(**context):
    """Send a concise success email for the incoming_journals micro-batch DAG."""
    ti = context["ti"]
    dag_run = context.get("dag_run")

    run_id = ti.xcom_pull(task_ids="start", key="run_id") or "unknown"
    execution_date = dag_run.execution_date if dag_run else datetime.now(timezone.utc)
    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    journal_count = ti.xcom_pull(task_ids="fetch_new_entries", key="journal_count") or 0
    preprocessed_count = ti.xcom_pull(task_ids="preprocess_entries", key="preprocessed_count") or 0
    valid_count = ti.xcom_pull(task_ids="validate_entries", key="valid_count") or 0
    embedded = ti.xcom_pull(task_ids="embed_entries", key="embedded_journals") or []
    embedded_count = len(embedded) if isinstance(embedded, (list, tuple)) else 0
    insert_result = ti.xcom_pull(task_ids="store_to_mongodb", key="insert_result") or {}
    patients_updated = ti.xcom_pull(task_ids="update_analytics", key="patients_updated") or 0

    task_rows = _build_task_rows_incoming(ti)

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:650px;margin:0 auto;">
        <div style="background:#4CAF50;padding:20px;text-align:center;border-radius:8px 8px 0 0;">
            <h1 style="color:white;margin:0;">CalmAI Incoming Journals Pipeline Succeeded</h1>
        </div>

        <div style="padding:20px;background:#f9f9f9;border:1px solid #ddd;">
            <table style="width:100%;border-collapse:collapse;margin-bottom:16px;">
                <tr>
                    <td style="padding:6px 0;"><b>Run ID:</b></td>
                    <td>{run_id}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Execution Date:</b></td>
                    <td>{execution_date}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Finished At:</b></td>
                    <td>{finished_at}</td>
                </tr>
            </table>

            <h3 style="color:#333;border-bottom:2px solid #4CAF50;padding-bottom:6px;">Task Durations</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr style="background:#4CAF50;color:white;">
                    <th style="padding:8px 12px;text-align:left;">Task</th>
                    <th style="padding:8px 12px;text-align:center;">Duration</th>
                </tr>
                {task_rows}
            </table>

            <h3 style="color:#333;border-bottom:2px solid #4CAF50;padding-bottom:6px;margin-top:20px;">Run Summary</h3>
            <table style="width:100%;border-collapse:collapse;">
                <tr>
                    <td style="padding:6px 0;"><b>Fetched Journals:</b></td>
                    <td>{journal_count}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Preprocessed:</b></td>
                    <td>{preprocessed_count}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Validated:</b></td>
                    <td>{valid_count}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Embedded:</b></td>
                    <td>{embedded_count}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Inserted:</b></td>
                    <td>{insert_result}</td>
                </tr>
                <tr>
                    <td style="padding:6px 0;"><b>Patients Updated:</b></td>
                    <td>{patients_updated}</td>
                </tr>
            </table>

            <div style="text-align:center;margin-top:24px;">
                <img src="{MINION_GIF_URL}" alt="Minions Celebrating" style="max-width:400px;border-radius:8px;" />
                <p style="color:#888;font-size:13px;margin-top:8px;">Micro-batch run complete.</p>
            </div>
        </div>

        <div style="background:#333;color:#aaa;padding:12px;text-align:center;font-size:12px;border-radius:0 0 8px 8px;">
            CalmAI Incoming Journals Pipeline — Automated Notification
        </div>
    </div>
    """

    send_email(
        to=RECIPIENTS,
        subject=f"CalmAI Incoming Journals Succeeded — Run {run_id}",
        html_content=html,
    )
