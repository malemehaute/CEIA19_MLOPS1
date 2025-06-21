import datetime
from airflow.decorators import dag, task

markdown_text = """
### ETL Process for Podcast Data

This DAG extracts information from the original podcast CSV file.
Preprocessing consists of:
1. Dropping duplicated rows
2. Making a relative target
3. Encoding ordinal categories as numbers
4. Filling some columns with NAs
5. Dropping remaining rows with NAs (non-NA-supported columns)
6. Dropping irrelevant/redundant columns

After preprocessing, the data is split in 70-train/30-test subsets 
and saved back into a S3 bucket as two separate CSV files.
"""

default_args = {
    'owner': "Marcelo Alejandro Le Mehaute",
    'depends_on_past': False,
    'schedule_interval': None,
    'retries': 1,
    'retry_delay': datetime.timedelta(minutes=5),
    'dagrun_timeout': datetime.timedelta(minutes=15)
}


@dag(
    dag_id="process_etl_podcast_data",
    description="ETL process for podcast data, separating the dataset into training and testing sets.",
    doc_md=markdown_text,
    tags=["ETL", "Podcast Data"],
    default_args=default_args,
    catchup=False,
)
def process_etl_podcast_data():

    @task.virtualenv(
        task_id="obtain_original_data",
        requirements=["awswrangler==3.6.0", "pandas"],
        system_site_packages=True
    )
    def get_data():
        """
        Load the raw data from CSV file
        """
        import awswrangler as wr
        from airflow.models import Variable
        import pandas as pd

        data_path = "s3://data/raw/podcast.csv"

        # simulate downloading data
        dataframe = pd.read_csv("/podcast_dataset.csv")

        wr.s3.to_csv(df=dataframe,
                     path=data_path,
                     index=False)


    @task.virtualenv(
        task_id="preprocessing",
        requirements=["awswrangler==3.6.0"],
        system_site_packages=True
    )
    def preprocessing():
        """
        Drop duplicated rows, encode ordinals, fill NAs, drop columns.
        """
        import json
        import boto3
        import botocore.exceptions
        import mlflow

        import awswrangler as wr
        import pandas as pd
        import numpy as np
        import datetime

        from airflow.models import Variable

        data_original_path = "s3://data/raw/podcast.csv"
        data_end_path = "s3://data/raw/podcast_preproc.csv"
        df_original = wr.s3.read_csv(data_original_path)

        # drop duplicates
        df = df_original.drop_duplicates().copy()

        # relative target
        target_abs_col = Variable.get('target_abs_col')
        target_rel_col = Variable.get('target_rel_col')
        df[target_rel_col] = df[target_abs_col] / df['Episode_Length_minutes']

        # episode number encoding as int
        df['Episode_Number'] = df['Episode_Title'].apply(lambda x: x.split(" ")[-1]).astype(int)

        # guest absence
        df['no_guest'] = df['Guest_Popularity_percentage'].isna()

        # NA imputation
        df.fillna({'Guest_Popularity_percentage':-1}, inplace=True)

        # drop rows with NAs on other columns
        df.dropna(inplace=True)

        # reset index
        df.reset_index(inplace=True, drop=True)

        # sentiment encoding
        df['sentiment_encoded'] = df['Episode_Sentiment'].map({'Neutral':0, 'Negative':-1, 'Positive':1}).astype(int)

        # drop redundant/irrelevant columns
        df.drop(columns=['Episode_Title', 'Episode_Sentiment', target_abs_col], inplace=True)

        wr.s3.to_csv(df=df,
                     path=data_end_path,
                     index=False)

        # Save information of the dataset
        client = boto3.client('s3')


        data_dict = {}
        try:
            client.head_object(Bucket='data', Key='data_info/data.json')
            result = client.get_object(Bucket='data', Key='data_info/data.json')
            text = result["Body"].read().decode()
            data_dict = json.loads(text)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] != "404":
                # Something else has gone wrong.
                raise e

        df_original_log = df_original.drop(columns=target_abs_col)
        df_log = df.drop(columns=target_rel_col)

        # Upload JSON String to an S3 Object
        data_dict['target_abs_col'] = target_abs_col
        data_dict['target_rel_col'] = target_rel_col
        today_date = datetime.datetime.today().strftime('%Y/%m/%d-%H:%M:%S"')
        data_dict['date'] = today_date

        for ds, suffix in (
            (df_original_log, '_original'),
            (df_log, '_after_preproc')
        ):
            data_dict['columns'+suffix] = ds.columns.to_list()
            data_dict['categorical_columns'+suffix] = ds.columns[ds.dtypes=='object'].tolist()

            categories_list = {
                k: str(v)
                for k, v in ds.dtypes.to_dict().items()
            }

            data_dict['columns_dtypes'+suffix] = categories_list

            data_dict['categories_values_per_categorical'+suffix] = {
                category: np.sort(ds[category].unique()).tolist()
                for category, dtype in categories_list.items()
                if dtype == 'object'
            }

        data_string = json.dumps(data_dict, indent=2)

        client.put_object(
            Bucket='data',
            Key='data_info/data.json',
            Body=data_string
        )
        

        mlflow.set_tracking_uri('http://mlflow:5000')
        experiment = mlflow.set_experiment("Podcast Data")

        mlflow.start_run(run_name='ETL_run_' + today_date,
                         experiment_id=experiment.experiment_id,
                         tags={"experiment": "etl", "dataset": "Podcast data"},
                         log_system_metrics=True)

        mlflow_dataset = mlflow.data.from_pandas(df_original,
                                                 source="/podcast_dataset.csv",
                                                 targets=target_abs_col,
                                                 name="podcast_data_complete")
        
        mlflow_dataset_preproc = mlflow.data.from_pandas(df,
                                                         source="/podcast_dataset.csv",
                                                         targets=target_rel_col,
                                                         name="podcast_data_complete_preprocessed")
        
        mlflow.log_input(mlflow_dataset, context="Dataset")
        mlflow.log_input(mlflow_dataset_preproc, context="Dataset")

    @task.virtualenv(
        task_id="split_dataset",
        requirements=["awswrangler==3.6.0",
                      "scikit-learn==1.3.2"],
        system_site_packages=True
    )
    def split_dataset():
        """
        Generate a dataset split into a training part and a test part
        """
        import awswrangler as wr
        from sklearn.model_selection import train_test_split
        from airflow.models import Variable

        def save_to_csv(df, path):
            wr.s3.to_csv(df=df,
                         path=path,
                         index=False)

        data_original_path = "s3://data/raw/podcast_preproc.csv"
        dataset = wr.s3.read_csv(data_original_path)

        test_size = Variable.get("test_size_podcast")
        target_col = Variable.get("target_rel_col")

        X = dataset.drop(columns=target_col)
        y = dataset[[target_col]]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=float(test_size))


        save_to_csv(X_train, "s3://data/final/train/podcast_X_train.csv")
        save_to_csv(X_test, "s3://data/final/test/podcast_X_test.csv")
        save_to_csv(y_train, "s3://data/final/train/podcast_y_train.csv")
        save_to_csv(y_test, "s3://data/final/test/podcast_y_test.csv")

    get_data() >> preprocessing() >> split_dataset()

dag = process_etl_podcast_data()