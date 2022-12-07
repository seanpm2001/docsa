"""Publish a model trained on artifical data."""

# pylint: disable=invalid-name,too-many-locals

import logging
import os

from sklearn.metrics import f1_score

import slub_docsa

from slub_docsa.common.paths import get_serve_dir
from slub_docsa.evaluation.classification.incidence import subject_incidence_matrix_from_targets, unique_subject_order
from slub_docsa.evaluation.classification.score.scikit import scikit_metric_for_best_threshold_based_on_f1score
from slub_docsa.evaluation.classification.split import scikit_kfold_train_test_split
from slub_docsa.experiments.common.datasets import filter_and_cache_named_datasets
from slub_docsa.experiments.qucosa.datasets import qucosa_named_datasets_tuple_list
from slub_docsa.serve.common import PublishedClassificationModelStatistics, current_date_as_model_creation_date
from slub_docsa.serve.models.classification.classic import get_classic_classification_models_map
from slub_docsa.serve.rest.service.models import classify_with_limit_and_threshold
from slub_docsa.serve.store.models import PublishedClassificationModelInfo, load_published_classification_model
from slub_docsa.serve.store.models import save_as_published_classification_model


logger = logging.getLogger(__name__)


def _evaluate_model(model, test_dataset, subject_order):
    predicted_probabilities = model.predict_proba(test_dataset.documents)
    test_incidence = subject_incidence_matrix_from_targets(test_dataset.subjects, subject_order)
    score = scikit_metric_for_best_threshold_based_on_f1score(
        f1_score, average="micro", zero_division=0
    )(test_incidence, predicted_probabilities)
    return score


def _publish_model(model_generator, model_type, dataset, dataset_name, random_state=123):
    model_id = dataset_name + "__" + model_type
    models_directory = os.path.join(get_serve_dir(), "classification_models")
    model_directory = os.path.join(models_directory, model_id)

    if os.path.exists(model_directory):
        logger.info("skip existing persisted model '%s'", model_id)
        return
    logger.info("loading model '%s'", model_id)

    model = model_generator()
    logger.info("loaded model class %s", str(model))

    logger.info("prepare training data")
    subject_order = unique_subject_order(dataset.subjects)
    train_dataset, test_dataset = scikit_kfold_train_test_split(0.9, dataset, random_state=random_state)
    train_incidence = subject_incidence_matrix_from_targets(train_dataset.subjects, subject_order)

    logger.info("train model %s", str(model))
    model.fit(train_dataset.documents, train_incidence)

    logger.info("evaluate model %s", str(model))
    test_dataset_f1_score = _evaluate_model(model, test_dataset, subject_order)
    logger.info("f1 score before persisting %f", test_dataset_f1_score)

    logger.info("save model with id '%s'", model_id)
    save_as_published_classification_model(
        directory=model_directory,
        model=model,
        subject_order=subject_order,
        model_info=PublishedClassificationModelInfo(
            model_id=model_id,
            model_type=model_type,
            model_version="v1",
            schema_id="rvk",
            creation_date=current_date_as_model_creation_date(),
            supported_languages=["de"],
            description=f"qucosa model trained for dataset variant '{dataset_name}' "
                      + f"with classifiation model '{model_type}'",
            tags=["qucosa", "only_titles"],
            slub_docsa_version=slub_docsa.__version__,
            statistics=PublishedClassificationModelStatistics(
                number_of_training_samples=len(train_dataset.subjects),
                number_of_test_samples=len(test_dataset.subjects),
                scores={
                    "f1_t=best": test_dataset_f1_score
                }
            )
        )
    )

    logger.info("load and evaluate persisted model")
    published_model = load_published_classification_model(model_directory, get_classic_classification_models_map())
    classify_with_limit_and_threshold(
        published_model.model,
        test_dataset.documents,
        limit=3
    )
    persisted_f1_score = _evaluate_model(published_model.model, test_dataset, subject_order)
    logger.info(
        "score after persisting is %.5f (vs %.5f) for model '%s'", persisted_f1_score, test_dataset_f1_score, model_id
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    _check_qucosa_download = False
    _dataset_name = "qucosa_de_titles_rvk"

    _named_datasets = filter_and_cache_named_datasets(
        qucosa_named_datasets_tuple_list(_check_qucosa_download), [_dataset_name]
    )
    _, _dataset, subject_hierarchy = next(_named_datasets)

    for _model_type, _model_generator in get_classic_classification_models_map().items():
        _publish_model(_model_generator, _model_type, _dataset, _dataset_name)
