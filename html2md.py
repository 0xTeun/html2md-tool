# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
#     "html2text",
#     "requests",
#     "beautifulsoup4",
# ]
# ///

import os
import re
import time
import click
import html2text
import requests
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup


class GitBookCrawler:
    def __init__(self, base_url, folder_name, verbose=False, dry_run=False):
        self.base_url_original = base_url
        self.output_dir = Path.cwd() / folder_name
        self.verbose = verbose
        self.dry_run = dry_run
        self.visited_urls = set()
        self.page_count = 0
        self.error_count = 0
        self.progress_started = False # For standard mode progress dots

        # Normalize self.base_url_for_startswith_check and self.normalized_base_url_path
        parsed_b_url = urlparse(base_url)
        temp_normalized_path = parsed_b_url.path
        temp_startswith_url = base_url

        # Ensure path starts with / for consistency if not empty
        if temp_normalized_path and not temp_normalized_path.startswith('/'):
            temp_normalized_path = '/' + temp_normalized_path
        if not temp_normalized_path: # Handle case like http://domain.com (no path)
            temp_normalized_path = '/'

        if temp_normalized_path == '/': # e.g. http://domain.com or http://domain.com/
            # Ensure base_url for startswith check ends with / if it's just the domain
            if not parsed_b_url.path or not parsed_b_url.path.endswith('/'):
                temp_startswith_url = urljoin(base_url, parsed_b_url.path + "/" if parsed_b_url.path else "/")
        else:
            # If path doesn't look like a file (no extension in last segment)
            # ensure it ends with a slash for both normalized_path and startswith_url
            path_segments = [s for s in temp_normalized_path.split('/') if s]
            if path_segments and '.' not in path_segments[-1]: # Not a file like path
                if not temp_normalized_path.endswith('/'):
                    temp_normalized_path += '/'
                if not temp_startswith_url.endswith('/'):
                     # Preserve query/fragment if original URL had them and was modified
                    if parsed_b_url.query or parsed_b_url.fragment:
                        temp_startswith_url = parsed_b_url._replace(path=temp_normalized_path).geturl()
                    else: # Simpler case, can just append or use urljoin
                        temp_startswith_url = urljoin(base_url, temp_normalized_path)
            # If it is a file-like path, normalized_base_url_path should represent its "directory"
            # For example, if base_url is .../stable/index.html, normalized_base_url_path should be .../stable/
            elif path_segments and '.' in path_segments[-1]:
                 temp_normalized_path = '/'.join(temp_normalized_path.split('/')[:-1]) + '/'
                 if not temp_startswith_url.endswith('/'): # startswith_url should also reflect this directory
                    temp_startswith_url = urljoin(base_url, temp_normalized_path)


        self.normalized_base_url_path = temp_normalized_path
        self.base_url_for_startswith_check = temp_startswith_url

        # Configure html2text
        self.converter = html2text.HTML2Text()
        self.converter.ignore_links = False
        self.converter.ignore_images = False # Images are linked, not embedded
        self.converter.ignore_tables = False
        self.converter.body_width = 0  # No wrapping
        self.converter.unicode_snob = True
        self.converter.mark_code = True

        if not dry_run and not self.output_dir.exists():
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def _log_verbose(self, message, **kwargs):
        if self.verbose:
            click.secho(message, **kwargs)

    def _log_standard_progress(self, char_code, final_newline=False):
        if not self.verbose:
            if not self.progress_started:
                prefix = "Dry-run: Processing pages (o = would save): " if self.dry_run else "Processing pages (. = saved): "
                click.echo(prefix, nl=False)
                self.progress_started = True
            click.echo(char_code, nl=False)
            if final_newline:
                click.echo() # Newline
                self.progress_started = False


    def _log_error(self, message):
        if not self.verbose and self.progress_started:
            click.echo() # Newline to separate error from progress dots
            self.progress_started = False # Reset for next potential progress line
        click.secho(message, fg="red", err=True)


    def clean_filename_component(self, filename_component):
        name = re.sub(r'[\\/*?:"<>|]', "_", filename_component)
        name = name.replace(" ", "_")
        name = name.strip()
        if not name:
            name = "unnamed_component"
        return name[:100]

    def get_page_title(self, soup):
        title_tag = soup.find('h1') or soup.find('title')
        if title_tag:
            title_text = title_tag.get_text().strip()
            title_text = re.sub(r'\s+', ' ', title_text)
            return title_text[:255] if title_text else "Unnamed Page"
        return "Unnamed Page"

    def extract_content(self, soup):
        main_content_selectors = [
            'main',
            'article',
            'div[role="main"]',
            'div.main-content',
            'div.content',
            'div.page-content',
            'div.DocSearch-content' # Common in Docusaurus/GitBook like
        ]
        main_content = None
        for selector in main_content_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break

        target_element = main_content if main_content else soup.body
        if not target_element: return str(soup)

        # Remove common unwanted elements
        unwanted_selectors = [
            "nav", "header", "footer", "aside", ".sidebar", ".toc",
            ".edit-page-link", "div.theme-doc-markdown header", ".navbar",
            "div[class*='breadcrumb']", "div[class*='pagination']",
            "button[aria-label='collapse']" # GitBook theme specific
        ]
        for selector in unwanted_selectors:
            for element in target_element.select(selector):
                element.decompose()

        return str(target_element)


    def determine_path_from_url(self, url):
        current_url_parsed = urlparse(url)
        current_url_path = current_url_parsed.path

        if current_url_path and not current_url_path.startswith('/'):
            current_url_path = '/' + current_url_path
        if not current_url_path:
            current_url_path = '/'

        relative_path_str = ""
        if current_url_path.startswith(self.normalized_base_url_path):
            relative_path_str = current_url_path[len(self.normalized_base_url_path):]
        else:
            relative_path_str = current_url_path.lstrip('/')
            self._log_verbose(f"Warning: URL {url} may be outside normalized base path {self.normalized_base_url_path}. Using path '{relative_path_str}'.", fg="yellow", err=True)

        relative_path_str = relative_path_str.strip('/')

        if not relative_path_str:
            return Path("index.md")

        path_segments = [ps for ps in relative_path_str.split('/') if ps]
        if not path_segments:
             return Path("index.md")

        last_segment = path_segments[-1]
        html_extensions = ('.html', '.htm', '.xhtml', '.php', '.asp', '.aspx')

        if any(last_segment.lower().endswith(ext) for ext in html_extensions):
            filename_stem = last_segment.rsplit('.', 1)[0]
            directories = path_segments[:-1]
        else:
            filename_stem = "index"
            directories = path_segments

        cleaned_filename = self.clean_filename_component(filename_stem) + ".md"
        cleaned_directories = [self.clean_filename_component(d) for d in directories]

        return Path(*cleaned_directories) / cleaned_filename

    def process_page(self, url_to_process):
        # Use a consistent, clean URL (no fragment/query) for visited checks
        parsed_url = urlparse(url_to_process)
        clean_url_for_visited = parsed_url._replace(fragment="", query="").geturl()

        if clean_url_for_visited in self.visited_urls:
            return []

        try:
            self._log_verbose(f"Fetching: {url_to_process}", fg="yellow")
            response = requests.get(url_to_process, timeout=15) # Increased timeout
            response.raise_for_status()

            final_url = response.url # URL after redirects
            parsed_final_url = urlparse(final_url)
            clean_final_url_for_visited = parsed_final_url._replace(fragment="", query="").geturl()

            if final_url != url_to_process:
                self._log_verbose(f"Redirected from {url_to_process} to {final_url}", fg="cyan")
                # Mark original as visited if it wasn't the clean version
                if clean_url_for_visited not in self.visited_urls:
                    self.visited_urls.add(clean_url_for_visited)
                # If the redirect target has already been visited (e.g. canonicalization)
                if clean_final_url_for_visited in self.visited_urls:
                    return []

            self.visited_urls.add(clean_final_url_for_visited) # Add final, clean URL

            soup = BeautifulSoup(response.text, 'html.parser')
            content_html = self.extract_content(soup)
            title = self.get_page_title(soup)
            markdown_content = self.converter.handle(content_html).strip()

            rel_path = self.determine_path_from_url(final_url) # Use final URL for path determination
            output_path = self.output_dir / rel_path

            if not self.dry_run:
                output_path.parent.mkdir(parents=True, exist_ok=True)

            if self.dry_run:
                self._log_verbose(f"Dry-run: Would save {final_url} -> {output_path}", fg="blue")
                self._log_standard_progress("o")
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    # Add title as H1 if not already present as the first non-whitespace content
                    if not markdown_content.startswith(f'# {title}') and not markdown_content.startswith('# '):
                        f.write(f"# {title}\n\n")
                    f.write(markdown_content + "\n") # Ensure newline at EOF
                self._log_verbose(f"Saved: {output_path}", fg="green")
                self._log_standard_progress(".")

            self.page_count += 1
            new_urls_to_visit = []
            for link_tag in soup.find_all('a', href=True):
                href_value = link_tag['href']
                if not href_value or href_value.startswith(('#', 'javascript:', 'mailto:')) or \
                   any(ext in href_value.lower() for ext in [
                       '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico',
                       '.pdf', '.zip', '.tar.gz', '.tgz', '.rar', '.7z',
                       '.css', '.js', '.json', '.xml', '.txt',
                       '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                       '.mp4', '.webm', '.ogg', '.mp3', '.wav', '.avi', '.mov',
                       '.woff', '.woff2', '.ttf', '.otf', '.eot'
                   ]):
                    continue

                abs_href = urljoin(final_url, href_value) # Resolve relative to the page's final URL
                parsed_abs_href = urlparse(abs_href)
                clean_abs_href = parsed_abs_href._replace(fragment="", query="").geturl()

                if clean_abs_href.startswith(self.base_url_for_startswith_check) and \
                   clean_abs_href not in self.visited_urls:
                    new_urls_to_visit.append(clean_abs_href) # Add clean URL to queue

            time.sleep(0.1) # Polite delay
            return new_urls_to_visit

        except requests.exceptions.RequestException as e:
            self._log_error(f"Request error processing {url_to_process}: {str(e)}")
            self.error_count += 1
            return []
        except Exception as e:
            self._log_error(f"Error processing {url_to_process}: {type(e).__name__} - {str(e)}")
            self.error_count += 1
            return []

    def crawl(self):
        click.secho(f"Starting crawl of: {self.base_url_original}", bold=True)
        self._log_verbose(f"Normalized base URL for link checking: {self.base_url_for_startswith_check}")
        self._log_verbose(f"Normalized base path for output structure: {self.normalized_base_url_path}")
        self._log_verbose(f"Output directory: {self.output_dir}")

        # Start queue with the URL used for startswith check
        queue = [self.base_url_for_startswith_check]

        # Use a set for faster `in` checks for items already added to queue
        # This complements self.visited_urls which tracks successfully processed/attempted pages.
        queued_urls = {self.base_url_for_startswith_check}

        while queue:
            current_url = queue.pop(0)
            queued_urls.remove(current_url) # Remove from set as it's now being processed

            # process_page handles the self.visited_urls check internally
            new_links = self.process_page(current_url)

            for new_link in new_links:
                if new_link not in self.visited_urls and new_link not in queued_urls:
                     queue.append(new_link)
                     queued_urls.add(new_link)

        self._log_standard_progress("", final_newline=True) # Ensure newline after dots

        click.secho(f"\nCrawl completed:", bold=True)
        click.secho(f"Pages processed: {self.page_count}")
        click.secho(f"Errors: {self.error_count}", fg="red" if self.error_count > 0 else None)


def convert_local_directory(folder_path_str, skip_existing=False, dry_run=False, verbose=False):
    folder_path = Path(folder_path_str).resolve()
    md_base_folder = folder_path.parent / f"{folder_path.name}_md"

    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.ignore_tables = False
    converter.body_width = 0
    converter.unicode_snob = True
    converter.mark_code = True

    total_files, html_files, converted_count, skipped_count, error_count = 0, 0, 0, 0, 0
    non_html_files = []

    click.secho(f"Scanning {folder_path} for HTML files...", bold=True)
    if verbose:
        click.secho(f"Markdown files will be saved to {md_base_folder}")

    if not dry_run and not md_base_folder.exists():
        md_base_folder.mkdir(parents=True, exist_ok=True)

    files_to_process = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            files_to_process.append(Path(root) / file)

    progress_started_local = False
    if not verbose:
        prefix = "Dry-run: Processing local files (o = would convert): " if dry_run else "Processing local files (. = converted): "
        click.echo(prefix, nl=False)
        progress_started_local = True

    for html_file_path in files_to_process:
        total_files += 1
        if html_file_path.suffix.lower() in (".html", ".htm"):
            html_files += 1
            rel_path = html_file_path.relative_to(folder_path)
            md_file = md_base_folder / rel_path.with_suffix(".md")

            if not dry_run:
                md_file.parent.mkdir(parents=True, exist_ok=True)

            if skip_existing and md_file.exists():
                if verbose: click.secho(f"Skipping (exists): {html_file_path} -> {md_file}", fg="cyan")
                skipped_count += 1
                continue

            if dry_run:
                if verbose: click.secho(f"Dry-run: Would convert: {html_file_path} -> {md_file}", fg="blue")
                if not verbose: click.echo("o", nl=False)
                converted_count +=1 # Count as "would convert" for summary
                continue

            try:
                if verbose: click.secho(f"Converting: {html_file_path} -> {md_file}", fg="yellow")
                with open(html_file_path, "r", encoding="utf-8") as f_in:
                    html_content = f_in.read()

                soup = BeautifulSoup(html_content, 'html.parser')
                title = GitBookCrawler.get_page_title(None, soup) # Use static method if possible

                # Simplified content extraction for local files; can be enhanced if needed
                body_content = soup.body if soup.body else soup
                if body_content:
                    for unwanted_selector in ["nav", "header", "footer", "aside"]:
                        for element in body_content.select(unwanted_selector): element.decompose()
                    html_to_convert = str(body_content)
                else:
                    html_to_convert = html_content

                markdown_content = converter.handle(html_to_convert).strip()

                with open(md_file, "w", encoding="utf-8") as f_out:
                    if not markdown_content.startswith(f'# {title}') and not markdown_content.startswith('# '):
                        f_out.write(f"# {title}\n\n")
                    f_out.write(markdown_content + "\n")

                if verbose: click.secho(f"Converted: {html_file_path} -> {md_file}", fg="green")
                if not verbose: click.echo(".", nl=False)
                converted_count += 1
            except Exception as e:
                if progress_started_local and not verbose: click.echo() # Newline for error
                click.secho(f"Error converting {html_file_path}: {type(e).__name__} - {str(e)}", fg="red", err=True)
                error_count += 1
                if progress_started_local and not verbose: # Restart prefix if needed
                    click.echo(prefix, nl=False)
        else:
            non_html_files.append(html_file_path)

    if progress_started_local and not verbose: click.echo() # Final newline for progress dots

    click.secho(f"\n{'Dry run' if dry_run else 'Local conversion'} completed:", bold=True)
    click.secho(f"Total files scanned: {total_files}")
    click.secho(f"HTML files found: {html_files}")
    if dry_run:
        click.secho(f"HTML files that would be converted: {converted_count}")
    else:
        click.secho(f"Files converted: {converted_count}")
    if skip_existing: click.secho(f"Files skipped (already exist): {skipped_count}")
    click.secho(f"Files with errors: {error_count}", fg="red" if error_count > 0 else None)
    click.secho(f"Non-HTML files skipped: {len(non_html_files)}")

    if verbose and non_html_files:
        click.secho("\nNon-HTML files (first 10 of each type):", bold=True)
        extensions = {}
        for f_path in non_html_files:
            ext = f_path.suffix.lower() or "(no extension)"
            extensions.setdefault(ext, []).append(f_path)
        for ext, f_list in sorted(extensions.items()):
            click.secho(f"{ext}: {len(f_list)} files", fg="magenta")
            for ex_file in f_list[:10]: click.secho(f"  - {ex_file.relative_to(folder_path.parent)}")


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Convert HTML to Markdown from local directories or GitBook URLs."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())

@cli.command("local")
@click.argument("directory", type=click.Path(exists=True, file_okay=False, dir_okay=True, resolve_path=True))
@click.option("--skip-existing", is_flag=True, help="Skip conversion if markdown file already exists.")
@click.option("--dry-run", is_flag=True, help="Print files that would be converted without actual conversion.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information about processed files.")
def local_command(directory, skip_existing, dry_run, verbose):
    """Convert HTML files from a local directory to Markdown."""
    convert_local_directory(directory, skip_existing, dry_run, verbose)

@cli.command("gitbook")
@click.argument("url")
@click.option("--folder", "-f", "folder_name", default="gitbook_md",
              help="Folder name in current location to save markdown files. Defaults to 'gitbook_md'.")
@click.option("--dry-run", is_flag=True, help="Print what would be done without actually doing it.")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information, including link processing.")
def gitbook_command(url, folder_name, dry_run, verbose):
    """Crawl a GitBook URL and convert pages to Markdown, maintaining relative subdirectories."""
    crawler = GitBookCrawler(url, folder_name, verbose, dry_run)
    crawler.crawl()

if __name__ == "__main__":
    cli()
