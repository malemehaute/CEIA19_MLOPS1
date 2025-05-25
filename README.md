# Aprendizaje de Máquina 1 - TP Final

Este repositorio contiene el material utilizado para el trabajo práctico final para la materia *Aprendizaje de Máquina 1* de la Carrera de Especialización en Inteligencia Artificial (CEIA) de FIUBA.

Integrantes:

* Alejandro Le Mehaute
* Gustavo Ramoscelli
* Javier Etcheto
* Martín Errázquin

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