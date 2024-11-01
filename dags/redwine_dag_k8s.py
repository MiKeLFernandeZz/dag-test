"""
This module defines the Airflow DAG for the Red Wine MLOps lifecycle. The DAG includes tasks
for various stages of the pipeline, including data reading, data processing, model training, 
and selecting the best model. 

The tasks are defined as functions and executed within the DAG. The execution order of the tasks 
is defined using task dependencies.

Note: The actual logic inside each task is not shown in the code, as it may reside in external 
script files.

The DAG is scheduled to run every day at 12:00 AM.

Please ensure that the necessary dependencies are installed and accessible for executing the tasks.

Por el amor...
""" 

from datetime import datetime
from airflow.decorators import dag, task
from kubernetes.client import models as k8s
from airflow.models import Variable

@dag(
    description='MLOps lifecycle',
    schedule_interval='* 12 * * *', 
    start_date=datetime.now(),
    catchup=False,
    tags=['demo', 'redWine'], 
) 
def redwine_dag_shape_test():

    env_vars={
        "POSTGRES_USERNAME": Variable.get("POSTGRES_USERNAME"),
        "POSTGRES_PASSWORD": Variable.get("POSTGRES_PASSWORD"),
        "POSTGRES_DATABASE": Variable.get("POSTGRES_DATABASE"),
        "POSTGRES_HOST": Variable.get("POSTGRES_HOST"),
        "POSTGRES_PORT": Variable.get("POSTGRES_PORT"),
        "TRUE_CONNECTOR_EDGE_IP": Variable.get("CONNECTOR_EDGE_IP"),
        "TRUE_CONNECTOR_EDGE_PORT": Variable.get("IDS_EXTERNAL_ECC_IDS_PORT"),
        "TRUE_CONNECTOR_CLOUD_IP": Variable.get("CONNECTOR_CLOUD_IP"),
        "TRUE_CONNECTOR_CLOUD_PORT": Variable.get("IDS_PROXY_PORT"),
        "MLFLOW_ENDPOINT": Variable.get("MLFLOW_ENDPOINT"),
        "MLFLOW_TRACKING_USERNAME": Variable.get("MLFLOW_TRACKING_USERNAME"),
        "MLFLOW_TRACKING_PASSWORD": Variable.get("MLFLOW_TRACKING_PASSWORD") 
    }

    volume_mount = k8s.V1VolumeMount(
        name="dag-dependencies", mount_path="/git"
    )

    init_container_volume_mounts = [
        k8s.V1VolumeMount(mount_path="/git", name="dag-dependencies")
    ]
    
    volume = k8s.V1Volume(name="dag-dependencies", empty_dir=k8s.V1EmptyDirVolumeSource())

    init_container = k8s.V1Container(
        name="git-clone",
        image="alpine/git:latest",
        command=["sh", "-c", "mkdir -p /git && cd /git && git clone -b main --single-branch https://github.com/MiKeLFernandeZz/dag-test.git"],
        volume_mounts=init_container_volume_mounts
    )

    # Define as many task as needed
    @task.kubernetes(
        image='clarusproject/dag-image:1.0.0-slim',
        name='read_data',
        task_id='read_data',
        namespace='airflow',
        init_containers=[init_container],
        volumes=[volume],
        volume_mounts=[volume_mount],
        do_xcom_push=True,
        env_vars=env_vars
    )
    def read_data_procces_task():
        import sys
        import redis
        import uuid
        import pickle


        sys.path.insert(1, '/git/dag-test/src/redwine')
        from Data.read_data import read_data
        from Process.data_processing import data_processing

        redis_client = redis.StrictRedis(
            host='redis-headless.redis.svc.cluster.local',
            port=6379,  # El puerto por defecto de Redis
            password='pass'
        )

        df = read_data()
        dp = data_processing(df)

        read_id = str(uuid.uuid4())

        redis_client.set('data-' + read_id, pickle.dumps(dp))

        return read_id
    
    @task.kubernetes(
        image='clarusproject/dag-image:1.0.0-slim',
        name='elasticNet_model_training',
        task_id='elasticNet_model_training',
        namespace='airflow',
        get_logs=True,
        init_containers=[init_container],
        volumes=[volume],
        volume_mounts=[volume_mount],
        env_vars=env_vars
    )
    def print_shape_task(read_id=None):
        import sys
        import redis
        import pickle
        import pandas as pd

        sys.path.insert(1, '/git/dag-test/src/redwine')
        from Models.ElasticNet_model_training import elasticNet_model_training

        redis_client = redis.StrictRedis(
            host='redis-headless.redis.svc.cluster.local',
            port=6379,  # El puerto por defecto de Redis
            password='pass'
        )

        data = redis_client.get('data-' + read_id)
        res = pickle.loads(data)
        print('res', res)
        res_df = pd.DataFrame([res])
        print(res_df.shape)

    # Instantiate each task and define task dependencies
    processing_result = read_data_procces_task()
    shape_result = print_shape_task(processing_result)


    # Define the order of the pipeline
    processing_result >> shape_result

# Call the DAG 
redwine_dag_shape_test()