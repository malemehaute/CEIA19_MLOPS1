import datetime

from airflow.decorators import dag, task

markdown_text = """
### Re-Train model on new data and optimize HPs

This DAG re-trains the model based on new data, optimizing hyperparameters
based on a cross-validation scheme. It then compares the new model's performance
against the previous' one on the test set.
If the new model is better, then it replaces the old one in production.
The evaluation metric used is RMSE.
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
    dag_id="retrain_the_model",
    description="Re-train the model based on new data, search hps,"
                "test the previous model, and put in production the new one if "
                "it performs better than the old one",
    doc_md=markdown_text,
    tags=["Re-Train", "HP-search","Podcast"],
    default_args=default_args,
    catchup=False,
)
def hp_search_retrain():
    @task.virtualenv(
        task_id="train_the_challenger_model",
        requirements=["scikit-learn==1.3.2",
                      "mlflow==2.10.2",
                      "awswrangler==3.6.0",
                      "optuna==4.4.0"],
        system_site_packages=True
    )
    def hp_search_challenger():
        """
        TODO: Agregar docstring
        """

        import optuna
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.preprocessing import TargetEncoder
        from sklearn.pipeline import make_pipeline
        from sklearn.compose import make_column_transformer
        from sklearn.model_selection import KFold
        import numpy as np
        import pandas as pd
        from sklearn.metrics import root_mean_squared_error, mean_absolute_error
        import awswrangler as wr
        import mlflow
        from airflow.models import Variable
        from mlflow.models import infer_signature
        import datetime

        # preliminaries
        mlflow.set_tracking_uri('http://mlflow:5000')
        target_metric = Variable.get('target_metric')
        target_col = Variable.get('target_rel_col')
        length_ep_col = Variable.get('length_ep_col')
        optuna_n_trials = Variable.get('hp_search_n_trials')
        today = datetime.datetime.today().strftime('%Y/%m/%d-%H:%M:%S"')

        # mlflow experiment setting
        def get_or_create_experiment(experiment_name):
            """
            Retrieve the ID of an existing MLflow experiment or create a new one if it doesn't exist.

            This function checks if an experiment with the given name exists within MLflow.
            If it does, the function returns its ID. If not, it creates a new experiment
            with the provided name and returns its ID.

            Parameters:
            - experiment_name (str): Name of the MLflow experiment.

            Returns:
            - str: ID of the existing or newly created MLflow experiment.
            """

            if experiment := mlflow.get_experiment_by_name(experiment_name):
                return experiment.experiment_id
            else:
                return mlflow.create_experiment(experiment_name)

        experiment_id = get_or_create_experiment("Podcast Data")
        mlflow.set_experiment(experiment_id=experiment_id)


        # metrics, splitter
        SPLITTER = KFold(n_splits=5, random_state=42, shuffle=True)
        METRICS = {
            'rmse': root_mean_squared_error,
            'mae': mean_absolute_error
        }

        # TODO: es assert la forma correcta de chequear esto o MLFlow/Airflow prefieren otra?
        assert target_metric in METRICS, f"Target metric {target_metric} not found in METRICS"

        # get newest train data
        X = wr.s3.read_csv("s3://data/final/train/podcast_X_train.csv")
        y = wr.s3.read_csv("s3://data/final/train/podcast_y_train.csv")

        cat_cols = X.columns[X.dtypes=='object'].tolist()
        numeric_cols = X.columns[X.dtypes!='object'].tolist()


        def make_rf_pip(rf_params, cat_encoder):
            """
            Make a simple pipeline where
            * Numerical columns are passed through
            * Categorical columns are encoded using a passed `cat_encoder` encoder
            * A RandomForestRegressor is used as final estimator using `rf_params` parameters

            Both the preprocessing and RF models are passed `n_jobs=-1` for max usage of cores.
            """
            return make_pipeline(
                make_column_transformer(
                    ('passthrough',numeric_cols),
                    (cat_encoder, cat_cols),
                    sparse_threshold=0,
                    n_jobs=-1
                ),
                RandomForestRegressor(n_jobs=-1, **rf_params)
            )

        def cv_model(rf_params, cat_encoder, X, y):
            """
            TODO: docstring
            """
            n_splits = SPLITTER.get_n_splits()

            results = {k:np.empty(n_splits) for k in METRICS}
            for i, (train_idx, test_idx) in enumerate(SPLITTER.split(X)):

                # get splits
                X_train = X.iloc[train_idx]
                X_test = X.iloc[test_idx]

                y_train_rel = y.iloc[train_idx]
                y_test_abs = y.iloc[test_idx] * X_test[length_ep_col]

                # train model
                pipe = make_rf_pip(rf_params, cat_encoder)
                pipe.fit(X_train, y_train_rel)

                # get absolute preds
                y_pred_rel = pipe.predict(X_test)
                y_pred_abs = y_pred_rel * X_test[length_ep_col]

                # calculate metrics, save them
                for k, metric in METRICS.items():
                    results[k][i] = metric(
                        y_test_abs,
                        y_pred_abs
                    )
            # return results
            return results

        # override Optuna's default logging to ERROR only
        optuna.logging.set_verbosity(optuna.logging.ERROR)

        # define a logging callback that will report on only new challenger parameter configurations if a
        # trial has usurped the state of 'best conditions'
        def champion_callback(study, frozen_trial):
            """
            Logging callback that will report when a new trial iteration improves upon existing
            best trial values.
            """

            winner = study.user_attrs.get("winner", None)

            if study.best_value and winner != study.best_value:
                study.set_user_attr("winner", study.best_value)
                if winner:
                    improvement_percent = (abs(winner - study.best_value) / study.best_value) * 100
                    print(
                        f"Trial {frozen_trial.number} achieved value: {frozen_trial.value} with "
                        f"{improvement_percent: .4f}% improvement"
                    )
                else:
                    print(f"Initial trial {frozen_trial.number} achieved value: {frozen_trial.value}")

        # define Optuna's objective f
        def objective(trial):
            with mlflow.start_run(nested=True):
                # define hps
                rf_params = dict(
                    n_estimators = trial.suggest_int('n_estimators', 50, 100),
                    max_depth = trial.suggest_int('max_depth', 3, 6),
                    min_samples_split = trial.suggest_int('min_samples_split', 2, 10)
                )

                # CV the HPs
                results = cv_model(
                    rf_params=rf_params,
                    cat_encoder=TargetEncoder(target_type='continuous', random_state=42),
                    X=X,
                    y=y[target_col]
                )

                # log metrics x params
                mlflow.log_params(rf_params)
                for name, values in results.items():
                    mlflow.log_metric(name, values.mean().item())

            # return mean target metric
            return results[target_metric].mean()

        # define MLFlow challenger registering procedure
        def register_challenger(model, score, model_uri):

            client = mlflow.MlflowClient()
            name = "podcast_model_prod"

            # Save the model params as tags
            tags = model.get_params()
            tags["model"] = type(model).__name__
            tags[target_metric] = score

            # Save the version of the model
            result = client.create_model_version(
                name=name,
                source=model_uri,
                run_id=model_uri.split("/")[-3],
                tags=tags
            )

            # Save the alias as challenger
            client.set_registered_model_alias(name, "challenger", result.version)

        with mlflow.start_run(run_name='Challenger_run_' + today,
                             experiment_id=experiment_id,
                             tags={"experiment": "challenger models", "dataset": "Podcast data"},
                             nested=True,
                             log_system_metrics=True):

            # create optuna study
            study = optuna.create_study(direction="minimize")

            # run it
            study.optimize(objective, n_trials=optuna_n_trials, callbacks=[champion_callback])

            # log params, metrics
            mlflow.log_params(study.best_params)
            mlflow.log_metric(f"best_{target_metric}", study.best_value)

            # Log tags
            mlflow.set_tags(
                tags={
                    "project": "Podcast Listening Time Project",
                    "optimizer_engine": "optuna",
                    "model_family": "randomforest",
                    "feature_set_version": 1,
                }
            )

            # full training
            challenger = make_rf_pip(
                study.best_params,
                TargetEncoder(target_type='continuous', random_state=42)
            )

            challenger.fit(X, y[target_col])

            # log model
            artifact_path = "model"

            signature = infer_signature(X, challenger.predict(X))

            mlflow.sklearn.log_model(
                sk_model=challenger,
                artifact_path=artifact_path,
                signature=signature,
                serialization_format='cloudpickle',
                registered_model_name="podcast_model_dev",
                metadata={"model_data_version": 1}
            )

            artifact_uri = mlflow.get_artifact_uri(artifact_path)

            # Record the model
            register_challenger(challenger, study.best_value, artifact_uri)

    @task.virtualenv(
        task_id="evaluate_champion_challenge",
        requirements=["scikit-learn==1.3.2",
                      "mlflow==2.10.2",
                      "awswrangler==3.6.0"],
        system_site_packages=True
    )
    def evaluate_champion_challenge():
        import mlflow
        import awswrangler as wr
        from airflow.models import Variable

        from sklearn.metrics import root_mean_squared_error

        # preliminaries
        mlflow.set_tracking_uri('http://mlflow:5000')
        METRIC = root_mean_squared_error
        length_ep_col = Variable.get('length_ep_col')
        target_col = Variable.get('target_rel_col')

        def dict_argmin(d):
            """
            Returns the key for which the value is minimum.
            If there's more than one minimum, only one will be returned.
            """
            return min(d, key=d.get)

        def load_the_model(alias):
            model_name = "podcast_model_prod"

            client = mlflow.MlflowClient()
            model_data = client.get_model_version_by_alias(model_name, alias)

            model = mlflow.sklearn.load_model(model_data.source)

            return model

        def load_the_test_data():
            X_test = wr.s3.read_csv("s3://data/final/test/podcast_X_test.csv")
            y_test = wr.s3.read_csv("s3://data/final/test/podcast_y_test.csv")

            return X_test, y_test

        def promote_challenger(name):

            client = mlflow.MlflowClient()

            # Demote the champion
            client.delete_registered_model_alias(name, "champion")

            # Load the challenger from registry
            challenger_version = client.get_model_version_by_alias(name, "challenger")

            # delete the alias of challenger
            client.delete_registered_model_alias(name, "challenger")

            # Transform in champion
            client.set_registered_model_alias(name, "champion", challenger_version.version)

        def demote_challenger(name):

            client = mlflow.MlflowClient()

            # delete the alias of challenger
            client.delete_registered_model_alias(name, "challenger")

        # Load the dataset
        X_test, y_test = load_the_test_data()
        y_test_abs = y_test[target_col] * X_test[length_ep_col]

        # load models, get metrics for each
        metrics = dict()
        for alias in ('champion','challenger'):
            model = load_the_model(alias)

            y_pred_rel = model.predict(X_test)
            y_pred_abs = y_pred_rel * X_test[length_ep_col]

            metrics[alias] = METRIC(
                y_test_abs,
                y_pred_abs
            )

        # get winner, which is the one that minimizes target metric
        winner = dict_argmin(metrics)

        experiment = mlflow.set_experiment("Podcast Data")

        # Obtain the last experiment run_id to log the new information
        list_run = mlflow.search_runs([experiment.experiment_id], output_format="list")

        with mlflow.start_run(run_id=list_run[0].info.run_id):
            for alias in ('champion','challenger'):
                mlflow.log_metric(f"test_f1_{alias}", metrics[alias])


            mlflow.log_param("Winner", winner)

        # promote or demote according to values
        name = "podcast_model_prod"

        if winner == 'challenger':
            promote_challenger(name)
        else:
            demote_challenger(name)

    hp_search_challenger() >> evaluate_champion_challenge()


my_dag = hp_search_retrain()