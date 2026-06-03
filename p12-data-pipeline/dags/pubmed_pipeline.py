"""
p12 — Daily PubMed pipeline DAG.

Runs every day at 06:00 UTC. Fetches abstracts published in the previous day,
validates them, transforms to structured features, and loads to the Ceph
feature store.

Tasks:
  extract    → validate → transform → load → lineage

Each task is independent and retryable. Failures in one task do not affect
data already written by earlier tasks.
"""

from datetime import datetime, timedelta

from airflow.decorators import dag, task

DEFAULT_ARGS = {
    "owner":            "p12-pipeline",
    "retries":          2,
    "retry_delay":      timedelta(minutes=5),
    "email_on_failure": False,
}


@dag(
    dag_id="pubmed_daily_pipeline",
    default_args=DEFAULT_ARGS,
    schedule="0 6 * * *",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["p12", "biomedical", "pubmed"],
)
def pubmed_pipeline():

    @task
    def extract(logical_date=None) -> list[dict]:
        from src.extract import fetch
        date_str = logical_date.strftime("%Y/%m/%d")
        return fetch(date_from=date_str, date_to=date_str)

    @task
    def validate(records: list[dict]) -> dict:
        from src.validate import validate as run_validate
        result = run_validate(records)
        return {
            "accepted": result.accepted,
            "rejected_count": len(result.rejected),
            "acceptance_rate": result.acceptance_rate,
        }

    @task
    def transform(validation_output: dict) -> list[dict]:
        from src.transform import transform as run_transform
        return run_transform(validation_output["accepted"])

    @task
    def load(records: list[dict], logical_date=None) -> dict:
        from src.load import write
        from datetime import date
        run_date = date(logical_date.year, logical_date.month, logical_date.day)
        return write(records, run_date=run_date)

    @task
    def lineage(
        extract_count: int,
        validation_output: dict,
        load_output: dict,
        logical_date=None,
    ) -> None:
        from src.lineage import record_run
        record_run(
            run_date=logical_date.strftime("%Y-%m-%d"),
            extracted=extract_count,
            accepted=len(validation_output["accepted"]),
            rejected=validation_output["rejected_count"],
            partitions=load_output,
        )

    raw      = extract()
    val      = validate(raw)
    features = transform(val)
    loaded   = load(features)
    lineage(
        extract_count=raw.map(len),
        validation_output=val,
        load_output=loaded,
    )


pubmed_pipeline()
