# `html2md.py` - Documentation Downloader & HTML to Markdown Converter

In modern software development, especially when working with Large Language Models (LLMs), having relevant documentation directly within your codebase can be invaluable. This allows the LLM to access specific, up-to-date context, leading to more accurate and relevant responses. This script, `html2md.py`, is designed to help you download documentation from GitBook-style websites or convert local HTML files into clean Markdown format, making them easily consumable by both humans and LLMs.

## Features

*   **Crawl GitBook Websites**: Downloads an entire GitBook site, converting each page to Markdown.
*   **Convert Local HTML**: Converts a directory of local HTML files to Markdown.
*   **Automatic Linking**: Attempts to preserve and update links to be relative within the downloaded/converted structure.
*   **Clean Output**: Uses `html2text` for robust HTML-to-Markdown conversion.
*   **Customizable**: Offers options for output directory, verbosity, and dry runs.

## Recommended Setup: A Central `tools` Directory

For managing this and other similar utility scripts, it's recommended to create a central `tools` directory in your home folder (e.g., `~/tools`). Each script can then reside in its own subdirectory.

For this script, you would place `html2md.py` at: `~/tools/html2md/html2md.py`

This organization keeps your utilities tidy and makes them easy to manage and alias.

## Running with `uv`

This script is intended to be run using `uv`, an extremely fast Python package installer and resolver, written in Rust.

**Why `uv`?**

*   **Speed**: `uv` is significantly faster than traditional Python package managers.
*   **`uv run`**: The `uv run <script_path>` command allows you to execute Python scripts directly. It uses an available Python interpreter and its environment, without needing you to manually activate a virtual environment.

### 1. Install `uv`

The recommended way to install `uv` is via their official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
This script will detect your operating system and architecture and install the appropriate `uv` binary. Follow any instructions provided by the installer, which might include adding `uv` to your system's PATH.

## Usage

The script provides two main commands: `gitbook` for crawling websites and `local` for converting local HTML files.

**To run the script (assuming it's at `~/tools/html2md/html2md.py`):**

```bash
# General help
uv run ~/tools/html2md/html2md.py --help

# GitBook crawler help
uv run ~/tools/html2md/html2md.py gitbook --help

# Local converter help
uv run ~/tools/html2md/html2md.py local --help
```

### Crawling a GitBook Website

```bash
uv run ~/tools/html2md/html2md.py gitbook <BASE_URL> [OPTIONS]
```

**Arguments:**

*   `BASE_URL`: The base URL of the GitBook site to crawl (e.g., `https://docs.example.com/`).

**Options:**

*   `-o, --output-folder TEXT`: Folder to save markdown files. If not provided, a name is derived from the URL and created in the current working directory.
*   `-v, --verbose`: Enable verbose logging.
*   `-s, --skip-existing`: Skip crawling pages if the output markdown file already exists.
*   `-d, --dry-run`: Simulate crawling and conversion without writing files.
*   `--help`: Show help message.

**Example:**

```bash
uv run ~/tools/html2md/html2md.py gitbook https://docs.astral.sh/uv/ -o astral_uv_docs --verbose
```
This will crawl the `uv` documentation and save it into a folder named `astral_uv_docs` in your current working directory.

### Converting a Local HTML Directory

```bash
uv run ~/tools/html2md/html2md.py local <FOLDER_PATH> [OPTIONS]
```

**Arguments:**

*   `FOLDER_PATH`: Path to the local folder containing HTML files.

**Options:**

*   `-s, --skip-existing`: Skip conversion if the output markdown file already exists.
*   `-d, --dry-run`: Simulate conversion without writing files.
*   `-v, --verbose`: Enable verbose logging.
*   `--help`: Show help message.

**Example:**

```bash
uv run ~/tools/html2md/html2md.py local ./my_local_html_docs --verbose
```
This will convert HTML files in `./my_local_html_docs` and save the Markdown output in `./my_local_html_docs_md`.

## Setting up a Shell Alias for Easy Access

To run the script from any directory without typing `uv run ~/tools/html2md/html2md.py` every time, you can set up a shell alias. This assumes your script is located at `~/tools/html2md/html2md.py`.

*   **For Zsh (edit `~/.zshrc`):**
    ```bash
    alias html2md="uv run ~/tools/html2md/html2md.py"
    ```

*   **For Bash (edit `~/.bashrc` or `~/.bash_profile`):**
    ```bash
    alias html2md="uv run ~/tools/html2md/html2md.py"
    ```

**After adding the alias:**

1.  Save the shell configuration file (`.zshrc`, `.bashrc`, etc.).
2.  Apply the changes by sourcing the file (e.g., `source ~/.zshrc` or `source ~/.bashrc`) or by opening a new terminal session.

Now you can simply type `html2md gitbook <URL>` or `html2md local <PATH>` from any directory. The script will run, and the output will be created relative to your current working directory.
