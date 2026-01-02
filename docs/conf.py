"""
Configuration file for the Sphinx documentation builder.

For the full list of built-in configuration values, see the documentation:
https://www.sphinx-doc.org/en/master/usage/configuration.html

-- Project information -----------------------------------------------------
https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
"""

from typing import Any


import sys
from pathlib import Path

project = "Prereq"
copyright = "2025, Nathan Zilora"  # noqa: A001
author = "Nathan Zilora"
release = "0.1.0"

sys.path.insert(0, str(Path("../src").resolve()))

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx_wagtail_theme",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_wagtail_theme"
html_static_path = ["_static"]
master_doc = "contents"

html_theme_options: dict[str, str | int | list[str]] = {
    "project_name": "Prereq",
    "logo": "favicon.svg",
    "logo_alt": "Prereq",
    "logo_height": 43,
    "logo_url": "/",
    "logo_width": 43,
    "github_url": "https://github.com/Zwork101/prereq/tree/main/docs/",
    "header_links": "Project Repo|https://github.com/Zwork101/prereq, PyPi Page|#",
    "footer_links": [],
}

html_show_copyright = True
html_last_updated_fmt = "%b %d, %Y"
html_show_sphinx = False
