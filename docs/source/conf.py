# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

import sphinx_github_changelog
import sphinx_github_changelog.changelog

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Bedrock Server Manager"
copyright = "2025, DMedina559"
author = "DMedina559"
release = "3.7.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

sys.path.insert(0, os.path.abspath("../../src"))
sys.path.insert(0, os.path.abspath("."))

extensions = [
    "sphinx_click",
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
    "sphinx_github_changelog",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ["../sphinx_build/_static"]
html_favicon = "../sphinx_build/_static/favicon.ico"
html_logo = "../sphinx_build/_static/favicon-96x96.png"
html_css_files = ["css/custom_sphinx_styles.css"]

sphinx_github_changelog_token = os.environ.get(
    "SPHINX_GITHUB_CHANGELOG_TOKEN"
) or os.environ.get("GITHUB_TOKEN")

# MonkeyPatch sphinx_github_changelog to ignore pre-releases
original_extract_releases = sphinx_github_changelog.changelog.extract_releases


def extract_releases_with_prerelease(owner_repo, token, graphql_url=None):
    # Overriding to include isPrerelease in the query
    from sphinx_github_changelog.changelog import ChangelogError, github_call

    owner, repo = owner_repo.split("/")
    query = f"""
    query {{
        repository(owner: "{owner}", name: "{repo}") {{
            releases(orderBy: {{field: CREATED_AT, direction: DESC}}, first:100) {{
                nodes {{
                    name, descriptionHTML, url, tagName, publishedAt, isDraft, isPrerelease
                }}
            }}
        }}
    }}
    """
    full_query = {"query": query.replace("\n", "")}

    url = "https://api.github.com/graphql" if graphql_url is None else graphql_url

    result = github_call(url=url, query=full_query, token=token)
    if "errors" in result:
        raise ChangelogError(
            "GitHub API error response: \n"
            + "\n".join(e.get("message", str(e)) for e in result["errors"])
        )
    try:
        releases = result["data"]["repository"]["releases"]["nodes"]
        return [r for r in releases if r]
    except (KeyError, TypeError):
        raise ChangelogError(f"GitHub API error unexpected format:\n{result!r}")


sphinx_github_changelog.changelog.extract_releases = extract_releases_with_prerelease

original_node_for_release = sphinx_github_changelog.changelog.node_for_release


def node_for_release_ignore_prerelease(release, pypi_name=None):
    if release.get("isPrerelease", False):
        return None
    return original_node_for_release(release, pypi_name)


sphinx_github_changelog.changelog.node_for_release = node_for_release_ignore_prerelease
