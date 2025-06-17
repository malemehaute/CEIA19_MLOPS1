#!/bin/bash

sleep 5
/usr/bin/mc alias set s3 http://s3:9000 ${MINIO_ACCESS_KEY:-minio} ${MINIO_SECRET_ACCESS_KEY:-minio123}
/usr/bin/mc mb s3/${MLFLOW_BUCKET_NAME:-mlflow}
/usr/bin/mc mb s3/${DATA_REPO_BUCKET_NAME:-data}
exit 0
