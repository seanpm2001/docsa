"""Publish a model trained on artifical data."""

# pylint: disable=invalid-name

import logging
import os

from sklearn.metrics import f1_score
from slub_docsa.common.model import PersistableClassificationModel
from slub_docsa.common.paths import get_serve_dir

from slub_docsa.evaluation.incidence import subject_incidence_matrix_from_targets, unique_subject_order
from slub_docsa.evaluation.score import scikit_metric_for_best_threshold_based_on_f1score
from slub_docsa.evaluation.split import scikit_kfold_train_test_split
from slub_docsa.experiments.artificial.datasets import default_named_artificial_datasets
from slub_docsa.experiments.artificial.models import default_artificial_named_classification_model_list
from slub_docsa.experiments.common.models import initialize_classification_models_from_tuple_list
from slub_docsa.serve.rest.service.models import classify_with_limit_and_threshold
from slub_docsa.serve.store.models import PublishedClassificationModelInfo, load_published_classification_model
from slub_docsa.serve.models.classification.classic import get_classic_classification_models_map
from slub_docsa.serve.store.models import save_as_published_classification_model


logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    random_state = 123
    load_cached_predictions = False
    split_function_name = "random"
    n_token = 1000
    n_docs = 10000
    n_subjects = 10
    n_splits = 10
    min_samples = 10
    dataset_subset = [
        f"random_hierarchical_t={n_token}_d={n_docs}_s={n_subjects}_min={min_samples}"
    ]
    model_id = "test_model_id"
    model_type = "tfidf_10k_knn_k=1"

    filename_suffix = f"split={split_function_name}"

    named_datasets = default_named_artificial_datasets(n_token, n_docs, n_subjects, min_samples, dataset_subset)
    _, dataset, subject_hierarchy = next(named_datasets)

    def _get_model() -> PersistableClassificationModel:
        named_models = initialize_classification_models_from_tuple_list(
            default_artificial_named_classification_model_list(), [model_type]
        )
        m = named_models.classes[0]
        if not isinstance(m, PersistableClassificationModel):
            raise RuntimeError("model is not persistable")
        return m

    model = _get_model()
    logger.debug("loaded model %s", str(model))

    subject_order = unique_subject_order(dataset.subjects)

    train_dataset, test_dataset = scikit_kfold_train_test_split(0.9, dataset, random_state=random_state)
    train_incidence = subject_incidence_matrix_from_targets(train_dataset.subjects, subject_order)
    test_incidence = subject_incidence_matrix_from_targets(test_dataset.subjects, subject_order)

    model.fit(train_dataset.documents, train_incidence, test_dataset.documents, test_incidence)

    def _evaluate_model(m):
        predicted_probabilities = m.predict_proba(test_dataset.documents)

        score = scikit_metric_for_best_threshold_based_on_f1score(
            f1_score, average="micro", zero_division=0
        )(test_incidence, predicted_probabilities)

        return score

    logger.debug("score before persisting %f", _evaluate_model(model))

    logger.debug("save model")
    models_directory = os.path.join(get_serve_dir(), "classification_models")
    model_directory = os.path.join(models_directory, model_id)
    save_as_published_classification_model(
        directory=model_directory,
        model=model,
        subject_order=subject_order,
        model_info=PublishedClassificationModelInfo(
            model_id=model_id,
            model_type=model_type,
            schema_id="rvk",
            creation_date="datetime",
            supported_languages=["de"],
            description="random artificial",
            tags=["artificial", "random"],
        )
    )

    published_model = load_published_classification_model(model_directory, get_classic_classification_models_map())
    results = classify_with_limit_and_threshold(
        published_model.model,
        published_model.subject_order,
        test_dataset.documents,
        limit=3
    )
    import json
    print(json.dumps(results))
