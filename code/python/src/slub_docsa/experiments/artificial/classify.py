"""Experiments based on artifical data that was randomly generated."""

# pylint: disable=invalid-name

import logging
import os

from slub_docsa.common.paths import FIGURES_DIR
from slub_docsa.experiments.artificial.datasets import default_named_artificial_datasets
from slub_docsa.experiments.common import do_default_score_matrix_evaluation, get_split_function_by_name
from slub_docsa.experiments.common import write_default_plots

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    random_state = 123
    dataset_subset = [
        "random_no_correlations",
        "random_easy_to_predict",
        "random_hierarchical"
    ]
    subject_hierarchy = None
    split_function_name = "random"  # either: random, stratified
    n_token = 1000
    n_docs = 10000
    n_subjects = 10
    n_splits = 10
    min_samples = 10
    model_name_subset = [
        "oracle",
        "nihilistic",
        # "random",
        "knn k=1",
        # "knn k=3",
        # "mlp",
        # "rforest",
        # "annif tfidf",
        # "annif omikuji",
        # "annif vw_multi",
        # "annif fasttext",
        # "annif mllm",
        # "annif yake",
        # "annif stwfsa"
    ]

    filename_suffix = f"split={split_function_name}"

    named_datasets = default_named_artificial_datasets(n_token, n_docs, n_subjects, min_samples)

    evaluation_result = do_default_score_matrix_evaluation(
        named_datasets=named_datasets,
        split_function=get_split_function_by_name(split_function_name, n_splits, random_state),
        language="english",
        model_name_subset=model_name_subset,
    )

    write_default_plots(evaluation_result, os.path.join(FIGURES_DIR, "artificial"), filename_suffix)