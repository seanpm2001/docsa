"""Languages codes from loc.gov."""

import os
import logging
from typing import Mapping, NamedTuple

from slub_docsa.common.paths import get_resources_dir
from slub_docsa.data.load.common import download_file

LOC_GOV_ISO_639_URL = "https://www.loc.gov/standards/iso639-2/ISO-639-2_utf-8.txt"

logger = logging.getLogger(__name__)


class Language(NamedTuple):
    """Represents a language with its 3-letter, 2-letter codes and its name."""

    l3: str
    """3-letter language code"""

    l2: str
    """2-letter language code"""

    name: str
    """language name"""


class LanguageCodeTable(NamedTuple):
    """Stores language codes lookup dictionaries for 3-letter and 2-letter codes."""

    by_l3: Mapping[str, Language]
    """languages indexed by their 3-letter code"""

    by_l2: Mapping[str, Language]
    """languages indexed by their 2-letter code"""


def download_language_data(
    url: str = LOC_GOV_ISO_639_URL,
    filepath: str = None,
):
    """Download the language code table from loc.gov.

    Parameters
    ----------
    url : str, optional
        the url that is used to download the language code table, by default LOC_GOV_ISO_639_URL
    filepath : str, optional
        the filepath to store the language code table; if None, the filepath
        `SLUB_DOCSA_RESOURCES_DIR/loc_gov/iso-639-2.txt` is used
    """
    if filepath is None:
        filepath = os.path.join(get_resources_dir(), "loc_gov/iso-639-2.txt")
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    if not os.path.exists(filepath):
        logger.info("download language code table from loc.gov")
        download_file(url, filepath)


def load_language_codes(
    url: str = LOC_GOV_ISO_639_URL,
    filepath: str = None,
    download: bool = True,
) -> LanguageCodeTable:
    """Load language code table from file downloaded from loc.gov.

    Parameters
    ----------
    url : str, optional
        the url that is used to download the language code table, by default LOC_GOV_ISO_639_URL
    filepath : str, optional
        the filepath to store and load the language code table; if None, the filepath
        `SLUB_DOCSA_RESOURCES_DIR/loc_gov/iso-639-2.txt` is used
    download : bool, optional
        whether to download the file if it does not exist, by default True

    Returns
    -------
    LanguageCodeTable
        _description_
    """
    if filepath is None:
        filepath = os.path.join(get_resources_dir(), "loc_gov/iso-639-2.txt")

    if download:
        download_language_data(url, filepath)

    languages = []
    with open(filepath, "rt", encoding="utf8") as file:
        for line in file.readlines():
            l3_code, _, l2_code, name, _ = line.split("|")
            l2_code = l2_code if l2_code else None
            languages.append(Language(l2=l2_code, l3=l3_code, name=name))

    return LanguageCodeTable(
        by_l3={language.l3: language for language in languages},
        by_l2={language.l2: language for language in languages if language.l2 is not None}
    )


if __name__ == "__main__":

    logging.basicConfig(level=logging.DEBUG)

    for language in load_language_codes().by_l3.values():
        print(language.l3, "|", language.l2, "|", language.name)
