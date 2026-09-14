"""Airflow 3 daily transformation over completed upstream export intervals."""
from datetime import timedelta
import os
from pathlib import Path
import subprocess
import pendulum
from airflow.sdk import DAG, task, get_current_context
from airflow.timetables.interval import CronDataIntervalTimetable

with DAG('fitness_daily', schedule=CronDataIntervalTimetable('@daily', timezone='UTC'), start_date=pendulum.datetime(2026, 9, 7, tz='UTC'),
         end_date=pendulum.parse(os.environ['FITNESS_SCHEDULE_END']) if os.environ.get('FITNESS_SCHEDULE_END') else None,
         catchup=True, max_active_runs=1, default_args={'retries': 2, 'retry_delay': timedelta(minutes=1)}) as dag:
    @task
    def ingest_interval():
        context=get_current_context()
        root=Path(os.environ['FITNESS_PROJECT_ROOT']).resolve()
        state=Path(os.environ['FITNESS_STATE_ROOT']).resolve()
        stamp=context['data_interval_end'].strftime('%Y%m%dT%H%M%SZ')
        subprocess.run([str(root/'.venv/bin/python'),'-m','fitness.exports',
            '--database',str(state/'source.db'),'--envelope',str(state/'exports'/(stamp+'.json')),
            '--heartbeats',str(state/'heartbeats'/(stamp+'.json')),
            '--cutoff',context['data_interval_end'].strftime('%Y-%m-%dT%H:%M:%SZ')],cwd=root,check=True)

    @task(execution_timeout=timedelta(minutes=20))
    def transform_interval():
        context = get_current_context()
        root = Path(os.environ['FITNESS_PROJECT_ROOT']).resolve()
        state = Path(os.environ['FITNESS_STATE_ROOT']).resolve()
        # Separate dbt environment avoids Airflow/dbt dependency conflicts.
        command = [str(root / '.venv/bin/python'), '-m', 'fitness.operations',
                   '--database', str(state / 'source.db'),
                   '--heartbeats', str(state / 'heartbeats' / (context['data_interval_end'].strftime('%Y%m%dT%H%M%SZ') + '.json')),
                   '--output', str(state / 'published'),
                   '--start', context['data_interval_start'].strftime('%Y-%m-%dT%H:%M:%SZ'),
                   '--end', context['data_interval_end'].strftime('%Y-%m-%dT%H:%M:%SZ')]
        for source in os.environ.get('FITNESS_REQUIRED_SOURCES', 'watch,phone,manual').split(','):
            command.extend(['--source', source.strip()])
        subprocess.run(command, cwd=root, check=True)
    ingest_interval() >> transform_interval()
