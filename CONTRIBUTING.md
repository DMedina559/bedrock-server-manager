<div style="text-align: center;">
    <img src="https://raw.githubusercontent.com/DMedina559/bsm-frontend/main/frontend/public/image/icon/web-app-manifest-512x512.png" alt="ICON" width="200" height="200">
</div>

# Bedrock Server Manager - Contributing

First off, thank you for considering contributing to Bedrock Server Manager! We value your time and effort. These guidelines are designed to make the contribution process as clear and straightforward as possible.

We welcome all contributions, including bug reports, feature requests, documentation improvements, and code enhancements.

## Table of Contents

1.  [Code of Conduct](#code-of-conduct)
2.  [Getting Started](#getting-started)
    *   [Forking the Repository](#forking-the-repository)
    *   [Setting Up Your Environment](#setting-up-your-environment)
3.  [Development Workflow](#development-workflow)
    *   [Branching Strategy](#branching-strategy)
    *   [Making Changes](#making-changes)
    *   [Keeping Your Fork Synced](#keeping-your-fork-synced)
4.  [Coding Standards](#coding-standards)
    *   [Code Formatting (Black)](#code-formatting-black)
    *   [Docstrings (Native Sphinx Format)](#docstrings-native-sphinx-format)
    *   [Understanding Existing Code](#understanding-existing-code)
    *   [Explaining Your Code](#explaining-your-code)
5.  [Project Architecture (UI > API > Core)](#project-architecture-ui--api--core)
6.  [CLI and Web UI/API Compatibility](#cli-and-web-uiapi-compatibility)
7.  [Testing](#testing)
8.  [Submitting Your Contribution (Pull Requests)](#submitting-your-contribution-pull-requests)
    *   [Preparing Your Pull Request](#preparing-your-pull-request)
    *   [The Review Process](#the-review-process)
9.  [Reporting Bugs or Requesting Features](#reporting-bugs-or-requesting-features)
10. [Questions?](#questions)


## Getting Started

### Forking the Repository

1.  **Fork the repository:** Click the "Fork" button on the top right of the [Bedrock Server Manager](https://github.com/dmedina559/bedrock-server-manager). This creates a copy of the repository in your personal GitHub account.
2.  **Clone your fork:**
    ```bash
    git clone https://github.com/dmedina559/bedrock-server-manager.git
    cd bedrock-server-manager
    ```
3.  **Add the upstream remote:** This allows you to fetch changes from the original repository.
    ```bash
    git remote add upstream https://github.com/dmedina559/bedrock-server-manager.git
    ```

### Setting Up Your Environment

We recommend using a virtual environment for development.

1.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```
2.  **Install dependencies:**

    ```bash
    python -m pip install -e '.[dev,docs,cli]'
    ```

    See [contributor setup and validation](docs/source/developer/development.md)
    for focused checks, documentation builds and generated contract maintenance.

3.  **Install Pre-commit Hooks:**
    To ensure code quality and prevent failing commits, install the pre-commit hooks. This will automatically run checks (linting, formatting) before every commit.
    ```bash
    pre-commit install
    ```


## Development Workflow

### Branching Strategy

All contributions should be made via Pull Requests from a feature branch in your fork.

1.  **Ensure your `dev` branch is up-to-date with upstream:**
    ```bash
    git checkout dev
    git pull upstream dev
    ```
2.  **Create a new feature branch:** Base your new branch off the `dev` branch. Choose a descriptive branch name (e.g., `feature/add-user-authentication`, `fix/login-bug-123`).
    ```bash
    git checkout -b feature/your-descriptive-branch-name dev
    ```
    Or, if it's a bug fix:
    ```bash
    git checkout -b fix/issue-description-or-number dev
    ```

### Making Changes

1.  Make your code changes, write tests, and update documentation as needed.
2.  Commit your changes with clear and concise commit messages. We strongly encourage [Conventional Commits](https://www.conventionalcommits.org/) but it's not enirely enforced.
    ```bash
    git add .
    git commit -m "feat: add multi user support"
    ```
    Or for a fix:
    ```bash
    git commit -m "fix: web server start args"
    ```

### Keeping Your Fork Synced

Periodically, and especially before submitting a Pull Request, ensure your feature branch is up-to-date with the upstream `dev` branch to avoid merge conflicts.

1.  Fetch the latest changes from upstream:
    ```bash
    git fetch upstream
    ```
2.  Rebase your feature branch onto the upstream `dev` branch:
    ```bash
    git checkout feature/your-descriptive-branch-name
    git rebase upstream/dev
    ```
    This helps keep the commit history clean. Resolve any conflicts that arise during the rebase.

## Coding Standards

### Code Formatting (Black)

We use [Black](https://github.com/psf/black) for uncompromising Python code formatting.

1.  **Install Black:**
    ```bash
    pip install black
    ```
2.  **Format your code before committing:**
    ```bash
    black .
    ```
    You can also set up Black to run as a pre-commit hook to automatically format files before each commit. (See Black's documentation for pre-commit setup).

### Docstrings (Native Sphinx Format)

Keep docstrings short and written in native Sphinx/reStructuredText. Public modules,
classes, functions and methods should explain their purpose in one summary
sentence. Add a short paragraph only for behavior a caller cannot infer from the
signature: units, ownership, side effects, cancellation, atomicity or failure
semantics.

Use native `:param name:`, `:returns:`, `:yields:` and `:raises Error:`
fields when they clarify a contract. Use `:ivar name:` for public attributes. Do not repeat annotated types, model field lists, defaults,
implementation steps or the same validation boilerplate on every API method.
Use double backticks for literals and Sphinx roles such as `:class:` and
`:meth:` for references. Keep destructive effects and important error conditions
explicit. Put extended examples and architectural explanations in the developer
or plugin guides.

Typed plugin data APIs use `@api_method(...)`, request/response models and
`@validate_contract`; generated references describe those contracts directly.
Update generated API/event references when their descriptions change.

```python
async def import_world(archive: Path) -> str:
    """Replace the active world from a validated archive and return its name.

    Extraction failure preserves the existing world.
    """
```

### Test cost and isolation

Test distinct behavior rather than adding a separate application startup for
each input value. Pure contract tables can scan all models without runtime
fixtures; integration tests should exercise real storage, processes and transports.
Consolidate repeated setup when one lifecycle can verify the same assertions.

The database fixture migrates an empty template once, then gives each test an
independent file, engine and event-loop resources. Migration tests create their
own databases and exercise upgrade/reopen paths directly. Never share mutable
application state or live SQLAlchemy sessions between tests.

Inspect `pytest --durations=25` before changing deadlines or removing tests.
Retain distinct failure and concurrency coverage. CI tests the minimum and maximum
supported Python versions only, on Linux and Windows.

### Understanding Existing Code

If you are modifying existing Python classes (`PyClasses`) or modules, please take the time to:

*   Understand their purpose and responsibility within the project.
*   Observe how they interact with other components.
*   Familiarize yourself with existing patterns and conventions used in those classes.

This helps maintain consistency and reduces the chances of introducing unintended side effects.

### Explaining Your Code

Be prepared to explain any piece of code you've written or modified during the Pull Request review process. Clear, well-documented code is preferred, but reviewers may ask for clarification on complex logic or design choices.

## Project Architecture (UI > API > Core)

Our project follows a layered architecture to promote separation of concerns and maintainability:

*   **UI (User Interface):** This layer is responsible for presentation and user interaction. It includes the Web UI and the Command Line Interface (CLI). The UI should interact with the system primarily through the API layer.
*   **API (Application Programming Interface):** This layer provides a well-defined interface for the UI and potentially other external services to interact with the core functionalities. It handles request validation, data transformation, and orchestrates calls to the Core layer.
*   **Core:** This layer contains the business logic, data models, and core functionalities of the application. It should be independent of the UI and API layers.

When making contributions:

*   **Respect the layers:** UI changes should ideally go through the API. API changes should utilize the Core logic. Avoid direct calls from UI to Core.
*   **Encapsulate logic:** New business logic should generally reside in the Core layer.
*   **API design:** If adding or modifying API endpoints, consider RESTful principles and clear, consistent naming.

## CLI and Web UI/API Compatibility

A key requirement is that contributions affecting shared logic must work consistently across both the Command Line Interface (CLI) and the Web UI/API.

*   **Test on both interfaces:** If your changes affect core functionality or the API, ensure you test the impact on both the CLI and the Web UI.
*   **Shared logic:** New features or modifications to the Core or API layers should be designed with both interfaces in mind.
*   **Consider exposure:** If you add a new Core feature, think about how it will be exposed via the API and subsequently consumed by both the UI and CLI.

## Testing

Pytest are used as the testing system for Bedrock Server Manager, with both unit tests and integration tests.

Test are automatically run on every commit and pull request via GitHub Actions. To run tests locally, you can use the following command:

```bash
pytest
```

## Submitting Your Contribution (Pull Requests)

### Preparing Your Pull Request

1.  Ensure your code is formatted with Black.
2.  Ensure your code includes appropriate docstrings.
3.  Ensure all tests pass.
4.  Ensure your branch is rebased on the latest `upstream/dev`.
5.  Push your feature branch to your fork:
    ```bash
    git push origin feature/your-descriptive-branch-name
    ```
6.  Go to the [Bedrock Server Manager](https://github.com/dmedina559/bedrock-server-manager) and click the "Compare & pull request" button for your recently pushed branch.
    *   **Target Branch:** Set the base branch to `dev` in the upstream repository.
    *   **Title:** Write a clear and concise title (e.g., "feat: Add user profile editing" or "fix: Correct calculation in summary report").
    *   **Description:**
        *   Provide a detailed description of the changes.
        *   Explain the "why" behind your changes (the problem you're solving).
        *   Summarize the "what" (how you solved it).
        *   If your PR addresses an existing issue, link to it (e.g., "Closes #123").
        *   Mention any specific areas you'd like reviewers to focus on.
        *   Confirm that your changes work for both CLI and Web UI/API where applicable.

### The Review Process

1.  Once your Pull Request is submitted, project maintainers will review it.
2.  Reviewers may ask questions, request changes, or provide feedback. Please respond to comments and make necessary updates.
3.  To update your PR, make changes locally, commit them, and push to your feature branch on your fork. The PR will update automatically.
4.  Once the PR is approved and all checks pass, a maintainer will merge it into the `dev` branch.

## Reporting Bugs or Requesting Features

To ensure Bedrock Server Manager is maintained effectively, we have an updated issue reporting policy.

**Important:** Any issue or feature request that does not use the provided templates will be closed without review.

### 1. Use the Correct Template

*   🐛 **Bug Report:** Use this for issues with the server manager itself.
*   ✨ **Feature Request:** Use this for proposing new ideas or enhancements.
*   **Unsure?** Open a [Discussion](https://github.com/DMedina559/bedrock-server-manager/discussions) instead.

### 2. Fill Out All Required Fields

*   **Environment Details & Logs:** We cannot debug issues without your Environment Details (OS, BSM Version) and Logs.
*   **Do Not Delete Sections:** Do not delete sections from the template. If a section isn't relevant, mark it as "N/A" rather than removing it.

### 3. Check Before Posting

*   **CLI Issues:** If your issue is related to the CLI, please post it in the [bsm-api-client repository](https://github.com/DMedina559/bsm-api-client/issues).
*   **Search First:** Always search existing issues and read the [Troubleshooting Docs](https://bedrock-server-manager.readthedocs.io/en/latest/general/troubleshooting.html) before posting.

## Questions?

If you have any questions about the contribution process, feel free to open a [discussions thread](https://github.com/DMedina559/bedrock-server-manager/discussions).

Thank you for contributing to Bedrock Server Manager!

### Documentation validation

Regenerate references with `python scripts/generate_plugin_docs.py`; use
`--check` to detect drift without writing files. Build all pages with
`python -m sphinx -W --keep-going -b html docs/source /tmp/bsm-docs`.
The Sphinx changelog extension fetches release history. Set `GITHUB_TOKEN` or
`SPHINX_GITHUB_CHANGELOG_TOKEN` when building the complete documentation.
Offline checks should exclude the network-backed changelog in a temporary
validation copy; keep the published changelog integration enabled.
Runnable plugin examples belong in
`plugins/`; fault injection and recursive-operation diagnostics belong in tests.
