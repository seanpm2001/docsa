"""Provides a basic evaluation pipeline for multiple models."""

# pylint: disable=fixme, too-many-locals, too-many-arguments

import logging
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

from slub_docsa.common.dataset import Dataset
from slub_docsa.common.document import Document
from slub_docsa.common.model import Model
from slub_docsa.common.score import MultiClassScoreFunctionType, BinaryClassScoreFunctionType
from slub_docsa.evaluation.condition import check_dataset_subject_distribution
from slub_docsa.evaluation.condition import check_dataset_subjects_have_minimum_samples
from slub_docsa.evaluation.incidence import subject_incidence_matrix_from_targets
from slub_docsa.evaluation.split import DatasetSplitFunction
from slub_docsa.models.dummy import OracleModel

logger = logging.getLogger(__name__)

FitModelAndPredictCallable = Callable[
    [Model, Sequence[Document], np.ndarray, Sequence[Document], Optional[Sequence[Document]], Optional[np.ndarray]],
    np.ndarray
]
"""Type alias for a function that does the basic fit and predict logic."""


def fit_model_and_predict_test_documents(
    model: Model,
    train_documents: Sequence[Document],
    train_incidence_matrix: np.ndarray,
    test_documents: Sequence[Document],
    validation_documents: Optional[Sequence[Document]] = None,
    validation_incidence_matrix: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Call fit and predict_proba method of a model in order to generated predictions.

    This is the default implementation of a fit and predict logic, which can be overwritten in order to, e.g., save
    predictions to a database, load predictions from a database, etc.

    Parameters
    ----------
    model: Model
        the initialized model that can be fitted and used for predictions afterwards
    train_documents: Sequence[Document]
        the sequence of training documents
    train_incidence_matrix: np.ndarray
        the subject incidence matrix for the training documents
    test_documents: Sequence[Document],
        the sequence of test documents
    validation_documents: Optional[Sequence[Document]] = None
        an optional sequence of validation documents
        (used by the torch ann model to generate evaluation scores during training)
    validation_incidence_matrix: Optional[np.ndarray] = None
        an optional subject incidence matrix for the validation documents
        (used by the torch ann model to generate evaluation scores during training)

    Returns
    -------
    numpy.ndarray
        the subject prediction probability matrix as returned by the `predict_proba` method of the model
    """
    logger.info("do training")
    model.fit(train_documents, train_incidence_matrix, validation_documents, validation_incidence_matrix)

    logger.info("do prediction")
    return model.predict_proba(test_documents)


def score_models_for_dataset(
    n_splits: int,
    dataset: Dataset,
    subject_order: Sequence[str],
    models: Sequence[Model],
    split_function: DatasetSplitFunction,
    overall_score_functions: Sequence[MultiClassScoreFunctionType],
    per_class_score_functions: Sequence[BinaryClassScoreFunctionType],
    fit_model_and_predict: FitModelAndPredictCallable = fit_model_and_predict_test_documents,
    stop_after_evaluating_split: int = None,
    use_test_data_as_validation_data: bool = False,
) -> Tuple[np.ndarray, np.ndarray]:
    """Evaluate a dataset using cross-validation for a number of models and score functions.

    Parameters
    ----------
    n_splits: int
        the number of splits of the cross-validation
    dataset: Dataset
        the full dataset that is then being split into training and test sets during evaluation
    subject_order: Sequence[str]
        a subject order list describing a unique order of subjects, which is used as index for incidence and
        probability matrices (column ordering)
    models: Sequence[Model]
        the list of models that are evaluated
    split_function: DatasetSplitFunction,
        the function that can be used to split the full dataset into `n_splits` different sets of training and test
        data sets, e.g., `slub_docsa.evaluation.split.scikit_base_folder_splitter`.
    overall_score_functions: Sequence[MultiClassScoreFunctionType]
        the list of score functions that are applied to the full probability matrices after predicting the full test
        data set
    per_class_score_functions: Sequence[BinaryClassScoreFunctionType],
        the list of score functions that are applied on a per subject basis (one vs. rest) in order to evaluate the
        prediction quality of every subject
    fit_model_and_predict: FitModelAndPredictCallable = fit_model_and_predict_test_documents,
        a function that allows to overwrite the basic fit and predict logic, e.g., by caching model predictions
    stop_after_evaluating_split: int = None,
        a flag that allows to stop the evaluation early, but still return the full score matrices (e.g. in order to
        test parameters settings without calculting all `n_splits` splits, which can take a long time)
    use_test_data_as_validation_data: bool = False
        a flag that if true provides the test data as validation data to the model's fit method, e.g., in order to
        evaluate the fitting behaviour of ann algorithms over multiple epochs of training

    Returns
    -------
    Tuple[np.ndarray, np.ndarray]
        A tuple of both score matrices, the overall score matrix and the per-subject score matrix.
        The overall score matrix will have a shape of `(len(models), len(overall_score_functions), n_splits)` and
        contains all score values calculated for every model over the test data of every split.
        The per subject score matrix will have shape of
        `(len(models), len(per_class_score_functions), n_splits, len(subject_order))` and contains score values for
        every subject calculated for every model, score function and split.

    """
    # check minimum requirements for cross-validation
    if not check_dataset_subjects_have_minimum_samples(dataset, n_splits):
        raise ValueError("dataset contains subjects with insufficient number of samples")

    overall_score_matrix = np.empty((len(models), len(overall_score_functions), n_splits))
    overall_score_matrix[:, :, :] = np.NaN

    per_class_score_matrix = np.empty((len(models), len(per_class_score_functions), n_splits, len(subject_order)))
    per_class_score_matrix[:, :, :, :] = np.NaN

    for i, split in enumerate(split_function(dataset)):
        logger.info("prepare %d-th cross validation split", i + 1)
        train_dataset, test_dataset = split
        check_dataset_subject_distribution(train_dataset, test_dataset, (0.5 / n_splits, 2.0 / n_splits))
        train_incidence_matrix = subject_incidence_matrix_from_targets(train_dataset.subjects, subject_order)
        test_incidence_matrix = subject_incidence_matrix_from_targets(test_dataset.subjects, subject_order)
        logger.info(
            "evaluate %d-th cross validation split with %d training and %d test samples",
            i + 1,
            len(train_dataset.subjects),
            len(test_dataset.subjects)
        )

        for j, model in enumerate(models):
            logger.info("evaluate model %s for %d-th split", str(model), i + 1)

            if isinstance(model, OracleModel):
                # provide predictions to oracle model
                model.set_test_targets(test_incidence_matrix)

            validation_documents: Optional[Sequence[Document]] = None
            validation_incidence: Optional[np.ndarray] = None
            if use_test_data_as_validation_data:
                validation_documents = test_dataset.documents
                validation_incidence = test_incidence_matrix

            # do predictions
            predicted_subject_probabilities = fit_model_and_predict(
                model,
                train_dataset.documents,
                train_incidence_matrix,
                test_dataset.documents,
                validation_documents,
                validation_incidence,
            )

            logger.info("do global scoring")
            for k, score_function in enumerate(overall_score_functions):
                overall_score_matrix[j, k, i] = score_function(test_incidence_matrix, predicted_subject_probabilities)

            logger.info("do per-subject scoring")
            for s_i in range(len(subject_order)):
                per_class_test_incidence_matrix = test_incidence_matrix[:, [s_i]]
                per_class_predicted_subject_probabilities = \
                    predicted_subject_probabilities[:, [s_i]]

                # calculate score for subset of documents that are annotated with a subject
                for k, score_function in enumerate(per_class_score_functions):
                    per_class_score_matrix[j, k, i, s_i] = score_function(
                        per_class_test_incidence_matrix,
                        per_class_predicted_subject_probabilities
                    )

            logger.info("overall scores are: %s", str(overall_score_matrix[j, :, i]))

        if stop_after_evaluating_split is not None and i >= stop_after_evaluating_split:
            break

    return overall_score_matrix, per_class_score_matrix
