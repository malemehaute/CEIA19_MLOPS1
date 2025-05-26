# Operaciones de Aprendizaje Automático I - TP Final

Este repositorio contiene el material utilizado para el trabajo práctico final para la materia *Operaciones de Aprendizaje Automático I* de la Carrera de Especialización en Inteligencia Artificial (CEIA) de FIUBA.

Integrantes:

* Gustavo Ramoscelli
* Martín Errázquin
* Marcelo Le Mehaute
  
## Temática elegida

El dataset seleccionado es un conjunto de datos sintético sobre episodios de podcast con diferentes features como el nombre del podcast, el título del episodio, la duración en minutos, etc. a partir de las cuales se plantea predecir el tiempo medio de escucha del mismo, también informada en el dataset.

## Referencias

* [Fuente de dataset principal](https://www.kaggle.com/datasets/ysthehurricane/podcast-listening-time-prediction-dataset)

## Integración con `uv`

Para gestión de dependencias se provee un archivo `pyproject.toml` y se prefiere el uso de [uv](https://docs.astral.sh/uv/).

Actualizar las dependencias requiere una simple linea

```bash
$ uv sync
```

Y levantar una instancia local de Jupyter Lab, con un kernel con las dependencias del proyecto, también:

```bash
$ uv run --with jupyter jupyter lab
```

## Instrucciones para setup local
### Prerequisitos

- Docker y Docker Compose
- Python 3.8+
- AWS CLI (for MinIO configuration if needed)

## Variables de environment
Se encuentran en el archivo .env en el repositorio:

### Airflow configuration
AIRFLOW_UID=50000
AIRFLOW_GID=0
AIRFLOW_PROJ_DIR=./airflow
AIRFLOW_PORT=8080
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow

### PostgreSQL configuration
PG_USER=airflow
PG_PASSWORD=airflow
PG_DATABASE=airflow
PG_PORT=5432

### Mlflow configuration
MLFLOW_PORT=5001
MLFLOW_S3_ENDPOINT_URL=http://s3:9000

### MinIO configuration
MINIO_ACCESS_KEY=minio
MINIO_SECRET_ACCESS_KEY=minio123
MINIO_PORT=9000
MINIO_PORT_UI=9001
MLFLOW_BUCKET_NAME=mlflow
DATA_REPO_BUCKET_NAME=data

## FastAPI configuration
FASTAPI_PORT=8800

## Detalle de acceso a los servicios
### 1. Airflow
Descripción: Maneja el pipeline ETL que entrenará al dataset de podcasts.
URL: [http://localhost:8080](http://localhost:8080)
User: airflow
Password: airflow

### 2. MLflow
Descripción: Monitorea el flujo de tasks del proyecto y es donde se muestran los resultados de los entrenamientos.
URL: [http://localhost:5001](http://localhost:5001)

### 3. MinIO
Descripción: Provee storage para poder almacenar los datos en formato simil S3.
URL: [http://localhost:9009](http://localhost:9001)
Credenciales:
Access key: minio
Secret: minio123

### 4. FastAPI
Descripción: Muestra el API Rest endpoint para servir el modelo y poder pegarle comandos.
URL:  [http://localhost:8800](http://localhost:8800)
Documentación de la API: [http://localhost:8800/docs](http://localhost:8800/docs)

## Pasos para ejecutar el proyecto
### Paso 1: Iniciar los servicios
- Correr el siguiente comando para iniciar todos los servicios utilizando Docker Compose:

```bash
$ docker compose --profile all up
```

### Paso 2: Activar el DAG ETL en Airflow para entrenar el modelo
- Acceder al portal de Airflow.
- Activar el DAG llamado process_etl_podcast_data.

### Paso 3: Monitorear el resultado de los experimentos en Airflow y MLflow
- Ver los logs de la ejecución del ETL en Airflow. 
- Ver los resultados del entrenamiento en MLflow.

###  Paso 4: Utilizar FastAPI para interactuar con el dataset y realizar predicciones utilizando el modelo
- Utilizar el endpoint de FastAPI para realizar consultas con el modelo

