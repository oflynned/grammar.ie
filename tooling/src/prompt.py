import hashlib
import html
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
import sys

sys.setrecursionlimit(10_000)

_last_llm_call_at = 0.0
BLOCK_BOUNDARY_TAGS = {
    "article",
    "blockquote",
    "center",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "ol",
    "p",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


def _env_int(name: str, default: int):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _env_float(name: str, default: float):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _is_rate_limit_error(error: Exception):
    error_name = error.__class__.__name__.lower()
    error_text = str(error).lower()

    return any([
        "ratelimit" in error_name,
        "rate limit" in error_text,
        "resource_exhausted" in error_text,
        "quota exceeded" in error_text,
    ])


def _is_retryable_llm_error(error: Exception):
    error_name = error.__class__.__name__.lower()
    error_text = str(error).lower()

    return any([
        _is_rate_limit_error(error),
        "timeout" in error_name,
        "timed out" in error_text,
        "read operation timed out" in error_text,
        "connection" in error_name,
        "connection" in error_text,
        "temporarily unavailable" in error_text,
        "server error" in error_text,
        "502" in error_text,
        "503" in error_text,
        "504" in error_text,
    ])


def _retry_delay_seconds(error: Exception, attempt: int):
    error_text = str(error)
    patterns = [
        r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s",
        r"retryDelay['\"]?\s*:\s*\{[^}]*seconds['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)",
        r"retry in (\d+(?:\.\d+)?)s",
    ]

    for pattern in patterns:
        match = re.search(pattern, error_text, flags=re.IGNORECASE)
        if match:
            return float(match.group(1)) + _env_float("PIPELINE_RATE_LIMIT_BUFFER_SECONDS", 3.0)

    return min(60.0, 5.0 * (2 ** attempt))


def _pause_between_llm_calls():
    global _last_llm_call_at

    min_pause = _env_float("PIPELINE_LLM_MIN_SECONDS_BETWEEN_CALLS", 0.0)
    if min_pause <= 0:
        return

    elapsed = time.monotonic() - _last_llm_call_at
    if elapsed < min_pause:
        wait_seconds = min_pause - elapsed
        print(f"⏳ Waiting {wait_seconds:.1f}s before next LLM call.")
        time.sleep(wait_seconds)


def _chunk_max_chars():
    return _env_int("PIPELINE_LLM_CHUNK_MAX_CHARS", 60_000)


def _hash_text(value: str):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_cache_segment(value: str):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    return value.strip("-") or "cache"


def _llm_cache_path(cache_dir, stage_name: str, cache_namespace: str, index: int, system_prompt: str, content: str):
    if not cache_dir or not cache_namespace:
        return None

    cache_key = _hash_text(f"{system_prompt}\0{content}")[:24]
    return (
        Path(cache_dir)
        / _safe_cache_segment(stage_name)
        / _safe_cache_segment(cache_namespace)
        / f"{index:04d}-{cache_key}.txt"
    )


def _read_cached_llm_output(cache_path):
    if cache_path and cache_path.is_file():
        print(f"💾 Reusing cached LLM output_copy: {cache_path}")
        return cache_path.read_text(encoding="utf-8")

    return None


def _read_valid_cached_llm_output(cache_path, output_validator=None):
    cached_output = _read_cached_llm_output(cache_path)
    if cached_output is None:
        return None

    if not output_validator or output_validator(cached_output):
        return cached_output

    print(f"⚠️  Cached LLM output_copy is incomplete or invalid. Discarding: {cache_path}")
    cache_path.unlink(missing_ok=True)
    return None


def _write_cached_llm_output(cache_path, content: str):
    if not cache_path:
        return

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(cache_path)


def _contains_valid_json_object(value: str):
    value = value.strip()

    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", value):
        try:
            decoder.raw_decode(value[match.start():])
            return True
        except json.JSONDecodeError:
            continue

    return False


def _split_long_block(block: str, max_chars: int):
    chunks = []
    remaining = block.strip()

    while len(remaining) > max_chars:
        cut = remaining.rfind("\n\n", 0, max_chars)
        if cut < max_chars // 2:
            cut = remaining.rfind(". ", 0, max_chars)
        if cut < max_chars // 2:
            cut = remaining.rfind(" ", 0, max_chars)
        if cut < max_chars // 2:
            cut = max_chars

        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _split_markdown_chunks(markdown: str, max_chars: int):
    markdown = markdown.strip()
    if max_chars <= 0 or len(markdown) <= max_chars:
        return [markdown]

    sections = [
        section.strip()
        for section in re.split(r"(?m)(?=^#{1,6}\s+)", markdown)
        if section.strip()
    ]

    chunks = []
    current = ""

    for section in sections:
        if len(section) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_block(section, max_chars))
            continue

        separator = "\n\n" if current else ""
        candidate = f"{current}{separator}{section}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = section

    if current:
        chunks.append(current.strip())

    return chunks


def _invoke_chunked_llm(
    llm: BaseChatModel,
    system_prompt: str,
    markdown: str,
    stage_name: str,
    cache_dir=None,
    cache_namespace=None,
):
    chunks = _split_markdown_chunks(markdown, _chunk_max_chars())
    if len(chunks) == 1:
        return _invoke_llm(
            llm,
            system_prompt,
            markdown,
            cache_path=_llm_cache_path(cache_dir, stage_name, cache_namespace, 1, system_prompt, markdown),
        )

    outputs = []
    print(f"✂️  Splitting {stage_name} into {len(chunks)} LLM calls.")

    for index, chunk in enumerate(chunks, start=1):
        chunk_prompt = f"""
{system_prompt}

Chunking context:
- This is chunk {index} of {len(chunks)} from one source page.
- Process only this chunk.
- Preserve headings and facts from this chunk.
- Do not add summaries of missing chunks.
        """
        print(f"📄 {stage_name.capitalize()} chunk {index}/{len(chunks)}")
        outputs.append(_invoke_llm(
            llm,
            chunk_prompt,
            chunk,
            cache_path=_llm_cache_path(cache_dir, stage_name, cache_namespace, index, chunk_prompt, chunk),
        ))

    return "\n\n".join(output.strip() for output in outputs if output.strip())


def _slugify(value: str):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "index"


def _frontmatter_scalar(content: str, key: str):
    match = re.match(r"\A---\s*\n(?P<body>.*?)\n---\s*", content.strip(), re.DOTALL)
    if not match:
        return None

    for line in match.group("body").splitlines():
        frontmatter_key, separator, raw_value = line.partition(":")
        if separator and frontmatter_key.strip() == key:
            value = raw_value.strip()
            if value.startswith("[") and value.endswith("]"):
                return None
            return value.strip('"').strip("'")

    return None


def _page_slug_from_content(content: str, fallback_slug: str):
    return _slugify(
        _frontmatter_scalar(content, "slug")
        or _frontmatter_scalar(content, "title")
        or fallback_slug
    )


def _ensure_page_marker(content: str, page_slug: str):
    if re.search(r"^<!--\s*page:\s*[a-z0-9][a-z0-9-]*\s*-->\s*$", content, re.MULTILINE):
        return content

    return f"<!-- page: {_page_slug_from_content(content, page_slug)} -->\n{content.strip()}"


def _source_context(source_slug: str):
    return f"""

Legacy source context:
- The input came from a legacy German-source file named "{source_slug}".
- Use that only as a private hint if it helps identify the topic.
- Do not use opaque legacy names such as "0dekl", "verb1", "verbnom1", "typ1igh", "defekt", or "{source_slug}" as public titles, folders, slugs, or headings.
    """


def _response_text(response):
    if hasattr(response, "text"):
        text = response.text
        return text() if callable(text) else text

    if hasattr(response, "content"):
        response_content = response.content
        if isinstance(response_content, str):
            return response_content

        if isinstance(response_content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in response_content
            )

    return str(response)


def _literal_prompt_text(value: str):
    return value.replace("{", "{{").replace("}", "}}")


def _invoke_llm(llm: BaseChatModel, system_prompt: str, content: str, cache_path=None, output_validator=None):
    cached_output = _read_valid_cached_llm_output(cache_path, output_validator=output_validator)
    if cached_output is not None:
        return cached_output

    prompt = ChatPromptTemplate.from_messages([
        ("system", _literal_prompt_text(system_prompt)),
        ("human", "{content}")
    ])

    max_attempts = max(1, _env_int("PIPELINE_LLM_MAX_ATTEMPTS", 6))

    output = None
    for attempt in range(max_attempts):
        try:
            _pause_between_llm_calls()
            response = (prompt | llm).invoke({"content": content})
            globals()["_last_llm_call_at"] = time.monotonic()
            output = _response_text(response)
            if not output_validator or output_validator(output):
                break

            if attempt == max_attempts - 1:
                break

            wait_seconds = _retry_delay_seconds(Exception("invalid LLM output_copy"), attempt)
            print(f"⏳ LLM returned incomplete or invalid output_copy. Retrying in {wait_seconds:.1f}s ({attempt + 2}/{max_attempts}).")
            time.sleep(wait_seconds)
        except Exception as error:
            globals()["_last_llm_call_at"] = time.monotonic()
            if not _is_retryable_llm_error(error) or attempt == max_attempts - 1:
                raise

            wait_seconds = _retry_delay_seconds(error, attempt)
            reason = "quota reached" if _is_rate_limit_error(error) else error.__class__.__name__
            print(f"⏳ LLM {reason}. Retrying in {wait_seconds:.1f}s ({attempt + 2}/{max_attempts}).")
            time.sleep(wait_seconds)

    if output is None:
        output = _response_text(response)

    if not output_validator or output_validator(output):
        _write_cached_llm_output(cache_path, output)
        return output

    if cache_path:
        print(f"⚠️  LLM output_copy for {cache_path.parent.name} was incomplete or invalid, so it was not cached.")
    return output


def _preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    page_title = None
    if soup.title:
        page_title = soup.title.get_text().strip()

    for tag in soup(["script", "style", "link", "meta"]):
        tag.decompose()

    for anchor in soup.find_all('a', href=re.compile(r'(index|gramadac|links)\.html?', re.IGNORECASE)):
        anchor.decompose()

    footer_link = soup.find('a', href=re.compile(r'index\.html?', re.IGNORECASE))
    if footer_link:
        parent = footer_link.parent
        if parent:
            for sibling in parent.previous_siblings:
                if sibling.name == 'hr':
                    sibling.decompose()
                    break
                if sibling.name in ['a', 'br', 'center', 'p']:
                    sibling.decompose()
            parent.decompose()

    return str(soup), page_title


def _normalise_space(text: str):
    return re.sub(r'\s+', ' ', text).strip()


def _inline_markdown(node, stop_at_blocks=False):
    if isinstance(node, NavigableString):
        return str(node)

    if not isinstance(node, Tag):
        return ""

    if stop_at_blocks and node.name in BLOCK_BOUNDARY_TAGS:
        return ""

    if node.name in ["script", "style", "meta", "link"]:
        return ""

    if node.name == "br":
        return " "

    children = "".join(
        _inline_markdown(child, stop_at_blocks=stop_at_blocks)
        for child in node.children
    )
    text = _normalise_space(children)

    if not text:
        return ""

    if node.name in ["b", "strong"]:
        return f"**{text}**"

    if node.name in ["i", "em"]:
        return f"_{text}_"

    return text


def _block_text(node, stop_at_blocks=False):
    return _normalise_space(
        "".join(
            _inline_markdown(child, stop_at_blocks=stop_at_blocks)
            for child in node.children
        )
    )


def _table_to_markdown(table):
    rows = []

    for row in table.find_all("tr", recursive=True):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            continue

        rendered = [_block_text(cell).replace("\n", " ") for cell in cells]
        if any(cell for cell in rendered):
            rows.append(rendered)

    if len(rows) < 2:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    header = rows[0]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])

    return "\n".join(lines)


def _list_to_markdown(list_node, indent=0):
    lines = []

    for item in list_node.find_all("li", recursive=False):
        nested_lists = item.find_all(["ul", "ol"], recursive=False)
        text = _normalise_space(
            "".join(
                _inline_markdown(child, stop_at_blocks=True)
                for child in item.children
                if child not in nested_lists
            )
        )
        if text:
            lines.append(f"{'  ' * indent}- {text}")

        for nested in nested_lists:
            nested_output = _list_to_markdown(nested, indent + 1)
            if nested_output:
                lines.append(nested_output)

    return "\n".join(lines)


def html_to_markdown(raw_html_content: str):
    escaped_html_content = html.unescape(raw_html_content)
    clean_html, detected_page_title = _preprocess_html(escaped_html_content)
    soup = BeautifulSoup(clean_html, 'html.parser')
    body = soup.body or soup
    output = []

    if detected_page_title:
        output.append(f"# {detected_page_title}")

    for node in body.find_all(["h1", "h2", "h3", "h4", "p", "ul", "ol", "table"], recursive=True):
        is_heading = node.name in ["h1", "h2", "h3", "h4"]
        is_nested_block = any(
            parent.name in ["ul", "ol", "table"]
            for parent in node.parents
            if parent is not body
        )
        if not is_heading and is_nested_block:
            continue

        if is_heading:
            text = _block_text(node, stop_at_blocks=True)
            if not text or (detected_page_title and (node.name == "h1" or text == detected_page_title)):
                continue

            level = {"h1": "#", "h2": "##", "h3": "###", "h4": "####"}[node.name]
            output.append(f"{level} {text}")
            continue

        if node.name == "p":
            text = _block_text(node, stop_at_blocks=True)
            if text:
                output.append(text)
            continue

        if node.name in ["ul", "ol"]:
            rendered_list = _list_to_markdown(node)
            if rendered_list:
                output.append(rendered_list)
            continue

        if node.name == "table":
            if node.find(["h1", "h2", "h3", "h4"]):
                continue

            table = _table_to_markdown(node)
            if table:
                output.append(table)

    return "\n\n".join(output).strip() + "\n"


def parse_content_to_markdown(raw_html_content: str):
    return html_to_markdown(raw_html_content)


PARSE_HTML_SYSTEM_PROMPT = """
        Convert legacy German HTML about Irish grammar into structured German Markdown.

        Rules:
        Convert HTML headings, paragraphs, lists, and tables to Markdown.
        Strip navigation, home links, copyright footers, styles, scripts, and hyperlinks.
        Preserve all German prose and Irish examples exactly.
        Join hard-wrapped lines inside one sentence or list item.
        Remove all hyperlinks.

        Output raw Markdown only. No code fence. No commentary.
        """


def parse_content_to_markdown_with_llm(llm: BaseChatModel, raw_html_content: str):
    escaped_html_content = html.unescape(raw_html_content)
    clean_html, _detected_page_title = _preprocess_html(escaped_html_content)

    return _invoke_llm(llm, PARSE_HTML_SYSTEM_PROMPT, clean_html)


TRANSLATE_SYSTEM_PROMPT = """
        You translate German source notes about Irish grammar into precise English Markdown.

        Requirements:
        - Translate German prose to natural British English.
        - Use standard linguistic terminology: dative, lenition, eclipsis, agent, progressive aspect, autonomous form, verbal noun, verbal adjective.
        - Preserve the Markdown structure, table columns, row order, and empty table cells.
        - Wrap every Irish word, Irish phrase, Irish sentence, and Irish formula in <ga>...</ga>.
        - Do not wrap English translations, German source words, punctuation-only text, grammatical labels, or Markdown syntax in <ga> tags.
        - If an Irish example is followed by a translation after "=" or in parentheses, only the Irish side goes inside <ga>.
        - Do not use __IRISH_*__ placeholders.
        - Output raw Markdown only. No code fence. No commentary.
        """


def translate_to_english(llm: BaseChatModel, markdown: str, cache_dir=None, cache_namespace=None):
    return _invoke_chunked_llm(
        llm,
        TRANSLATE_SYSTEM_PROMPT,
        markdown,
        "translation",
        cache_dir=cache_dir,
        cache_namespace=cache_namespace,
    )


def tokenise_irish_content(llm: BaseChatModel, markdown: str):
    system_prompt = """
        Tag Irish content in this Markdown with <ga>...</ga>.

        Rules:
        - Preserve all non-Irish text exactly.
        - Wrap Irish words, phrases, examples, and formulae only.
        - If an example contains an English or German translation after "=" or in parentheses, leave the translation outside <ga>.
        - Preserve Markdown structure.
        - Output raw Markdown only. No code fence. No commentary.
        """

    return _invoke_llm(llm, system_prompt, markdown)


CONTENT_PLAN_SYSTEM_PROMPT = """
        Source-preserving content plans are generated deterministically by the pipeline.

        The source page order, source page boundaries, source-unit coverage, and legacy internal link graph
        are canonical. The LLM must not invent a new taxonomy, merge unrelated source pages, or move units
        between pages. This text is kept only as a versioned contract for cache invalidation and manifest
        freshness; content planning no longer calls an LLM.
    """


def generate_content_plan(llm: BaseChatModel, source_briefs, cache_dir=None, cache_namespace=None):
    content = json.dumps(source_briefs, ensure_ascii=False, indent=2)
    return _invoke_llm(
        llm,
        CONTENT_PLAN_SYSTEM_PROMPT,
        content,
        cache_path=_llm_cache_path(cache_dir, "content-plan", cache_namespace, 1, CONTENT_PLAN_SYSTEM_PROMPT, content),
        output_validator=_contains_valid_json_object,
    )


IMPROVE_UX_SYSTEM_PROMPT = """
        Refine translated Markdown about Irish grammar into polished MDX for learners.
        Preserve every source fact, table entry, form, exception, dialect note, and example. Do not invent grammar.

        Output contract:
        - Output exactly the page requested by the supplied source-preserving content plan.
        - Do not split, merge, reorder across source pages, or create extra pages.
        - Every page, including a single-page output_copy, must start with an HTML comment marker:
          <!-- page: concise-kebab-case-slug -->
        - After the page marker, every page must start with frontmatter exactly in this shape:
          ---
          title: "<Irish word or English concept>"
          slug: "<concise-kebab-case-page-slug>"
          navTitle: "<short label for folder listings>"
          description: "<1-2 sentence British English summary>"
          category: "<Prepositions | Verbs | Nouns | Adjectives | Initial Mutations | Syntax | Other>"
          section: "<learner-facing folder name, e.g. Irregular verbs, Verb tenses, Prepositional pronouns>"
          sectionSlug: "<concise-kebab-case folder slug, e.g. conjugated, irregular-verbs, verbal-noun>"
          topic: "<parent topic or empty string, e.g. ar, ag, bí, first conjugation>"
          topicSlug: "<parent-topic-slug or empty string, e.g. ar, ag, bi, first-conjugation>"
          difficulty: "<beginner | intermediate | advanced | reference>"
          order: <integer>
          tags: ["<3-5 lowercase tags>"]
          prerequisiteTopics: ["<topic>"]
          relatedTopics: ["<topic>"]
          canonicalExamples: ["<short Irish example or formula>"]
          expectedLayout: "<layout hint from the content plan>"
          pagePurpose: "<purpose from the content plan>"
          ---
        - Output raw MDX only. No code fence. No commentary.
        - The page marker slug and frontmatter slug must match.

        Structure:
        - Build pages for reference use while preserving the old page's content order and source boundary.
        - Use categories, sections, titles, slugs, and page splits from the supplied content plan.
        - Use human section names that would make sense in navigation: "Irregular verbs", "Verb conjugation", "Verb tenses", "Verbal nouns", "Conjugated prepositions", "Relative clauses", "Numbers", and similar.
        - Use sectionSlug to decide the actual URL folder. This is where you may use shorter context labels like "conjugated" for the displayed section "Conjugated prepositions".
        - Use stable page slugs based on the page's role within its URL context, not on the source filename.
        - Avoid repeating parent context in slugs and nav labels. Prefer "overview", "forms", "usage", "grammar", "mutation rules", or "dialect forms" over "ar-usage", "preposition-ag", or "the-preposition-le-with".
        - Use topic and topicSlug for the parent item when a page belongs under a specific Irish word or grammar family, e.g. category "Prepositions", section "Conjugated prepositions", sectionSlug "conjugated", topic "ar", topicSlug "ar", slug "usage".
        - Leave topic and topicSlug empty only when the page should sit directly inside its section or category.
        - Use navTitle for compact cards and breadcrumbs. Prefer "bí", "Present tense", "Lenition after particles", "Forms", or "Usage" over long page titles.
        - Use order to place beginner/core overview pages first, common practical forms next, and advanced/dialectal reference pages later. Use gaps of 10 so future pages can slot in.
        - Capitalise learner-facing titles and navTitle as page labels, but keep the Irish preposition `i` lowercase when it stands alone so it is not confused with the English pronoun "I".
        - Keep page and section headings concise. Do not append Irish names in backticks when the English heading already identifies the concept.
        - Keep the source order. Within each source unit, preserve the order of rules, examples, exceptions, dialectal notes, and tables.
        - Convert numbered source lists into meaningful H2/H3 sections.
        - Do not number headings. Do not put Markdown styling inside headings.
        - Do not omit source-unit comments. Keep each <!-- source-unit: source:unit --> marker immediately before the refined content for that unit.

        Table and dense-reference rules:
        - Prefer tables for compact paradigms with short repeated forms and a small fixed number of columns.
        - For prepositional pronoun paradigms, use a table whenever possible:
          Person | Standard form | Emphatic form | Meaning
        - Do not turn a short conjugated-preposition paradigm into repeated H3 sections unless the forms need substantial notes.
        - Do not preserve wide source tables by default.
        - Avoid tables with more than 4 columns.
        - Avoid table cells that contain long phrases, multiple alternatives, or explanatory notes.
        - For large paradigms, create one compact overview table with only the highest-value columns, then move full detail into H3 entries.
        - If a source table is too wide, keep every row and cell by converting it into grouped subsections or mobile-friendly entry lists.
        - If a compact summary table is added, it must be in addition to the complete source detail, not a replacement.
        - For noun or verb reference entries with several notes per item, prefer repeated entry sections:
          ### `Irish form` (English meaning)
          - Gender/class: ...
          - Genitive: ...
          - Dative: ...
          - Plural: ...
          - Notes: ...
        - For short comparison data, use two-column tables: Feature | Form, Context | Example, or Concept | Detail.
        - The page must be comfortable on mobile without relying on horizontal scrolling for the main learning path.

        Irish text styling:
        - Convert <ga>text</ga> to plain backticks when it is an isolated word, form, short phrase, or formula inside prose or a table cell.
        - Convert full Irish example sentences to italic text, not backticks.
        - Never combine italic and code styling. Sentence examples should be italic sentence text, not italic text wrapped around backticks.
        - Remove the <ga> tags in the final MDX.
        - Keep English translations outside Irish styling.
        - Inside backticks use plain text only, never bold or italic Markdown.

        Components:
        - Use <MutationCard /> only for explicit mutation formulae.
        - <MutationCard /> requires title, before, after, and rule props. No children.
        - Props must be plain text, with no Markdown.
        - If and only if MutationCard is used, import it immediately after frontmatter:
          import MutationCard from '@components/MutationCard.astro';

        Style:
        - British spelling.
        - Clear learner-facing prose, but keep linguistic precision.
        - Prefer short paragraphs and compact bullets for examples.
        - No em dashes.
        - Remove references that only make sense for a German source reader.
    """


DIRECT_ENRICHMENT_SYSTEM_PROMPT = """
        Refine translated Markdown about Irish grammar into polished MDX for learners.
        Preserve every source fact, table entry, form, exception, dialect note, and example. Do not invent grammar.
        
        ## Output contract
        
        - Output exactly the page requested by the supplied content source.
        - Do not split, merge, reorder across source pages, or create extra pages.
        - After the page marker, every page must start with frontmatter in exactly this shape:
        
        ```
        ---
        enTitle: "<English language concept>"
        gaTitle: "<Irish language concept>"
        description: "<1-2 sentence British English summary>"
        tags: ["<3-5 lowercase tags>"]
        ---
        ```
        
        - Output raw MDX only. No code fence. No commentary.
        - The page marker slug and frontmatter slug must match.
        
        ---
        
        ## Structure
        
        - Build pages for reference use while preserving the source content order and source boundary.
        - Use categories, sections, titles, slugs, and page splits from the supplied content plan.
        - Use human section names that would make sense in navigation: "Irregular verbs", "Verb conjugation", "Verb tenses", "Verbal nouns", "Conjugated prepositions", "Relative clauses", "Numbers", and similar.
        - Use `sectionSlug` to decide the actual URL folder. Shorter context labels are fine: "conjugated" for "Conjugated prepositions".
        - Use stable page slugs based on the page's role within its URL context. Prefer "overview", "forms", "usage", "grammar", "mutations", or "dialect-forms" over "ar-usage", "preposition-ag", or "the-preposition-le-with".
        - Avoid repeating parent context in slugs and nav labels.
        - Use `topic` and `topicSlug` for the parent item when a page belongs under a specific Irish word or grammar family. Leave them empty only when the page sits directly inside its section or category.
        - Use `navTitle` for compact cards and breadcrumbs. Prefer "Bí", "Present tense", "Lenition after particles", "Forms", or "Usage" over long titles.
        - Use `order` to place beginner/core overview pages first, common practical forms next, and advanced or dialectal reference pages later. Use gaps of 10 so future pages can slot in.
        - Capitalise learner-facing titles and `navTitle` as page labels, but keep the Irish preposition `i` lowercase when it stands alone so it is not confused with the English pronoun "I".
        - Keep page and section headings concise. Do not append Irish names in backticks when the English heading already identifies the concept.
        - Keep the source order. Within each source unit, preserve the order of rules, examples, exceptions, dialectal notes, and tables.
        - Convert numbered source lists into meaningful H2/H3 sections.
        - Do not number headings. Do not put Markdown styling inside headings.
        
        ---
        
        ## Pedagogical enrichment
        
        These rules govern how content is framed for learning, not just reference.
        
        ### Opening orientation
        
        Every page must open with 1-3 sentences of plain-English orientation before any rules or tables. This should answer: *what is this, why does it matter, and when will a learner encounter it?* Do not begin a page with a heading, a table, or a rule list.
        
        Good example:
        > `ar` is one of the most common Irish prepositions, meaning "on" or "on top of". It changes its form depending on whether it is followed by a noun or a pronoun, and it triggers lenition on following nouns. You will encounter it constantly in everyday phrases.
        
        ### Canonical examples
        
        Each major rule or paradigm must be followed immediately by at least one concrete Irish example with an interlinear gloss and a natural English translation. Place examples close to the rule they illustrate, not gathered at the end.
        
        Format:
        > *Tá leabhar ar an mbord* - There is a book on the table
        
        Do not separate the Irish sentence, the gloss, and the translation onto distant lines or bury them in a footnote.
        
        ### Learner callouts
        
        Use the following callout components where they genuinely help. Do not use them decoratively or repeat information already in the body text.
        
        - **`<Tip>`** — a shortcut, memory aid, or useful pattern that saves learners effort.
        - **`<Note>`** — a practical qualification or nuance a learner needs when producing or recognising the form: irregular variants, which form to prefer in speech, or a form that looks wrong but is correct.
        - **`<Warning>`** — a common error or false friend that frequently causes mistakes.
        - **`<Dialect>`** — a dialectal variation (Connacht, Munster, Ulster) that differs meaningfully from the standard form.
        
        Callout syntax:
        
        ```mdx
        <Tip>
          A quick way to remember this: ...
        </Tip>
        
        <Warning>
          Learners often confuse X with Y because ...
        </Warning>
        
        <Dialect region="Munster">
          In Munster Irish, the form ... is used instead of ...
        </Dialect>
        ```
        
        If and only if any callout component is used, import all needed components immediately after the frontmatter block:
        
        ```mdx
        import Tip from '@components/Tip.astro';
        import Note from '@components/Note.astro';
        import Warning from '@components/Warning.astro';
        import Dialect from '@components/Dialect.astro';
        ```
        
        Only import components that appear on the page.
        
        ### Distinguishing practical notes from historical notes
        
        `<Note>` is for practical content only: irregular genitive variants, which form to prefer in speech, or a form that looks wrong but is correct.
        
        Historical, etymological, or comparative-linguistic content (cognates with other languages, Indo-European roots, old orthography, sound-change explanations) is advanced reference material. Move it into a `<Details>` block with a clear summary label, placed after all practical content for that entry. Do not let it dominate or replace the `<Note>` callout.
        
        `<Details>` syntax:
        
        ```mdx
        <Details summary="Historical note">
          The form `deirfiúr` derives from the prefix `deirbh-` ...
        </Details>
        ```
        
        Only import `Details` if it appears on the page:
        
        ```mdx
        import Details from '@components/Details.astro';
        ```
        
        ### Callout spacing
        
        Do not place two callout components (`<Note>`, `<Tip>`, `<Warning>`, `<Dialect>`, `<Details>`) consecutively without at least one sentence of prose between them. If two callouts belong together, merge them into a single callout or separate them with a bridging sentence.
        
        ### Mutation cards
        
        Use `<MutationCard />` only for explicit mutation formulae. It requires `title`, `before`, `after`, and `rule` props. No children. Props must be plain text with no Markdown. Import it if and only if it is used:
        
        ```mdx
        import MutationCard from '@components/MutationCard.astro';
        ```
        
        ### Progressive disclosure
        
        Order content from most essential to most detailed:
        
        1. Core rule or meaning (what every learner needs)
        2. Canonical example immediately after the rule
        3. Paradigm table or full form list
        4. Exceptions and qualifications
        5. Dialectal variation
        6. Advanced or historical notes
        
        Do not front-load caveats and exceptions before the learner has seen the basic pattern.
        
        ### Common errors and confusables
        
        Where the source material implies or states that learners frequently make a particular mistake, make it explicit with a `<Warning>` callout. If two forms are easily confused, place them side by side in a small two-column table:
        
        | Avoid | Prefer |
        |---|---|
        | incorrect form | correct form |
        
        ### Memory aids
        
        Where a mnemonic, pattern, or analogy genuinely helps retention, add it in a `<Tip>` callout. Keep it short and concrete. Do not invent dubious mnemonics: only include one if it is natural and genuinely useful.
        
        ---
        
        ## Table and dense-reference rules
        
        - Prefer tables for compact paradigms with short repeated forms and a small fixed number of columns.
        - Avoid tables with more than 4 columns.
        - Avoid table cells that contain long phrases, multiple alternatives, or explanatory notes.
        
        ### Prepositional pronoun tables
        
        For prepositional pronoun paradigms, use a table whenever possible:
        
        | Person | Standard form | Emphatic form | Meaning |
        |---|---|---|---|
        
        Do not turn a short conjugated-preposition paradigm into repeated H3 sections unless the forms need substantial notes.
        
        ### Noun paradigm tables
        
        For noun case paradigm tables, include at most four columns. The recommended column set is: **Nom. Sg. | Gen. Sg. | Nom. Pl. | Translation**. Omit Dat. Sg. and Gen. Pl. from the overview table; move them into the H3 detail entry for that noun if they are irregular or notable. Do not create a single wide table covering every case for every noun on one page.
        
        ### Large paradigms
        
        For large paradigms, create one compact overview table with only the highest-value columns, then move full detail into H3 entries. If a source table is too wide, keep every row and cell by converting it into grouped subsections or mobile-friendly entry lists. If a compact summary table is added, it must supplement the complete source detail, not replace it.
        
        ### Noun and verb detail entries
        
        For noun or verb reference entries with several notes per item, prefer repeated entry sections:
        
        ```
        ### `Irish form` (English meaning)
        - Gender/class: ...
        - Genitive: ...
        - Dative: ...
        - Plural: ...
        - Notes: ...
        ```
        
        After each H3 noun or verb entry, include at least one example sentence before any callout components. This prevents entries from becoming a stack of callouts with no readable prose.
        
        ### Comparison tables
        
        For short comparison data, use two-column tables: Feature | Form, Context | Example, or Concept | Detail.
        
        ### Mobile readability
        
        Pages must be comfortable on mobile without relying on horizontal scrolling for the main learning path.
        
        ---
        
        ## Irish text styling
        
        - Convert `<ga>text</ga>` to plain backticks for isolated words, forms, short phrases, or formulae inside prose or table cells.
        - Convert full Irish example sentences to italic text, not backticks.
        - Never combine italic and code styling. Sentence examples must be italic sentence text, not italic text wrapping backticks.
        - Remove all `<ga>` tags in the final MDX.
        - Keep English translations outside Irish styling.
        - Inside backticks use plain text only, never bold or italic Markdown.
        - When a sentence example has a gloss, format it consistently as: italic Irish sentence on line one, gloss in parentheses on line two, quoted English translation on line three.
        
        ---
        
        ## Style
        
        - British spelling throughout.
        - Clear, learner-facing prose with linguistic precision. Avoid jargon without explanation.
        - Prefer short paragraphs and compact bullets for examples.
        - No em dashes.
        - Remove references that only make sense for a German source reader.
        - Do not use passive constructions when plain active prose is clearer ("lenition adds an `h`" not "an `h` is added by lenition").
    """


def improve_direct_page(
    llm: BaseChatModel,
    english_md: str,
    source_slug: str,
    cache_dir=None,
    cache_namespace=None,
):
    system_prompt = DIRECT_ENRICHMENT_SYSTEM_PROMPT.format(source_slug=source_slug)
    return _invoke_llm(
        llm,
        system_prompt,
        english_md,
        cache_path=_llm_cache_path(cache_dir, "direct-enrichment", cache_namespace, 1, system_prompt, english_md),
    )


def improve_ux(
    llm: BaseChatModel,
    english_md: str,
    source_slug="source",
    planned_pages=None,
    cache_dir=None,
    cache_namespace=None,
):
    plan_context = ""
    if planned_pages:
        plan_context = f"""

Content plan contract:
- Generate exactly one MDX page for the planned page below.
- Every page marker must equal that planned page's slug.
- Every frontmatter value must match the planned page for:
  title, slug, navTitle, description, category, section, sectionSlug, topic, topicSlug,
  difficulty, order, tags, prerequisiteTopics, relatedTopics, canonicalExamples,
  expectedLayout, and pagePurpose.
- Use pagePurpose and expectedLayout to decide structure and tables.
- Use every supplied source unit in the generated page. The sourceRefs list is the coverage contract.
- Preserve source-unit comments, source order, and complete detail. Do not move content into unrelated topics.

{json.dumps(planned_pages, ensure_ascii=False, indent=2)}
        """

    final_prompt = f"{IMPROVE_UX_SYSTEM_PROMPT}{_source_context(source_slug)}{plan_context}"

    if planned_pages:
        return _invoke_llm(
            llm,
            final_prompt,
            english_md,
            cache_path=_llm_cache_path(cache_dir, "enrichment", cache_namespace, 1, final_prompt, english_md),
        )

    chunks = _split_markdown_chunks(english_md, _chunk_max_chars())
    if len(chunks) == 1:
        return _invoke_llm(
            llm,
            final_prompt,
            english_md,
            cache_path=_llm_cache_path(cache_dir, "enrichment", cache_namespace, 1, final_prompt, english_md),
        )

    outputs = []
    print(f"✂️  Splitting enrichment into {len(chunks)} LLM calls.")

    for index, chunk in enumerate(chunks, start=1):
        chunk_slug = f"{source_slug}-part-{index:02d}"
        chunk_prompt = f"""
{final_prompt}

Chunking context:
- This is chunk {index} of {len(chunks)} from one large source page.
- Build a coherent learner-facing MDX page for this chunk only.
- Start the output_copy with a page marker based on this chunk's learner-facing topic, not the source filename:
  <!-- page: concise-kebab-case-topic-slug -->
- The page marker slug and frontmatter slug must match.
- Do not add summaries of missing chunks.
        """
        print(f"📄 Enrichment chunk {index}/{len(chunks)}")
        content = _invoke_llm(
            llm,
            chunk_prompt,
            chunk,
            cache_path=_llm_cache_path(cache_dir, "enrichment", cache_namespace, index, chunk_prompt, chunk),
        )
        outputs.append(_ensure_page_marker(content, chunk_slug))

    return "\n\n".join(outputs)
