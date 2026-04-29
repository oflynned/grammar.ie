import hashlib
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path

from langchain_core.language_models import BaseChatModel

import prompt

from dotenv import load_dotenv
from token_manager import TokenManager

load_dotenv()

BASE_DIR = "./assets/test"
INPUT_DIR = f"{BASE_DIR}/input"
OUTPUT_DIR = f"{BASE_DIR}/output"
STEP_1_DIR = f"{OUTPUT_DIR}/step_1"
STEP_2_DIR = f"{OUTPUT_DIR}/step_2"
STEP_3_DIR = f"{OUTPUT_DIR}/step_3"
STEP_4_DIR = f"{OUTPUT_DIR}/step_4"
LLM_CACHE_DIR = f"{OUTPUT_DIR}/llm_cache"
MANIFEST_PATH = f"{OUTPUT_DIR}/pipeline_manifest.json"
CONTENT_PLAN_PATH = f"{OUTPUT_DIR}/content_plan.json"
MANIFEST_VERSION = 1
CONTENT_PLAN_VERSION = 2
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASTRO_CONTENT_DIR = PROJECT_ROOT / "src" / "content" / "grammar"

GEMINI_MODELS = {
    "coding": "gemini-2.5-flash-lite",
    "general": "gemini-2.5-flash-lite",
    "ideator": "gemini-2.5-flash",
    "quality": "gemini-2.5-pro",
}

MODEL_PROFILES = {
    "economy": {
        "translator": ("general", 0.1),
        "planner": ("ideator", 0.2),
        "enricher": ("ideator", 0.25),
    },
    "quality": {
        "translator": ("ideator", 0.1),
        "planner": ("quality", 0.2),
        "enricher": ("quality", 0.25),
    },
}

PROMPT_VERSIONS = {
    "translation": "translation-v1",
    "content_plan": "content-plan-v4",
    "enrichment": "enrichment-v5",
}

STEP_1_BLOAT_MIN_BYTES = 1_000_000
STEP_1_BLOAT_RATIO = 20


def force_regenerate():
    return os.getenv("PIPELINE_FORCE_REGENERATE") == "1"


def force_content_plan():
    return os.getenv("PIPELINE_FORCE_CONTENT_PLAN") == "1"


def dry_run():
    return os.getenv("PIPELINE_DRY_RUN") == "1"


def organize_content():
    return os.getenv("PIPELINE_ORGANIZE_CONTENT") == "1"


def organize_only():
    return os.getenv("PIPELINE_ORGANIZE_ONLY") == "1"


def save_file(content: str, directory: str, filename: str):
    target_dir = os.path.join(directory)
    os.makedirs(target_dir, exist_ok=True)
    output_path = os.path.join(target_dir, filename)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Saved to {directory}/{filename}")
    except Exception as e:
        print(f"Error saving {filename}: {e}")


def slugify(value: str):
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "index"


def hash_text(value: str):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_file(file_path: str):
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text_file(file_path: str, encoding="utf-8"):
    with open(file_path, "r", encoding=encoding) as f:
        return f.read()


def file_size(file_path: str):
    return os.path.getsize(file_path) if os.path.isfile(file_path) else 0


def extract_json_object(value: str):
    value = value.strip()

    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", value):
        try:
            parsed, _end = decoder.raw_decode(value[match.start():])
            return parsed
        except json.JSONDecodeError:
            continue

    if "{" not in value:
        raise ValueError("LLM response did not contain a JSON object.")

    raise ValueError("LLM response did not contain a valid JSON object.")


def load_manifest():
    if not os.path.isfile(MANIFEST_PATH):
        return {"version": MANIFEST_VERSION, "files": {}}

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except json.JSONDecodeError:
        print("⚠️  Manifest could not be decoded. Rebuilding freshness state from existing outputs.")
        return {"version": MANIFEST_VERSION, "files": {}}

    if not isinstance(manifest, dict):
        return {"version": MANIFEST_VERSION, "files": {}}

    manifest.setdefault("version", MANIFEST_VERSION)
    manifest.setdefault("files", {})
    return manifest


def save_manifest(manifest):
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    manifest["version"] = MANIFEST_VERSION
    manifest.setdefault("files", {})

    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        f.write("\n")


def manifest_record(manifest, slug: str):
    return manifest.setdefault("files", {}).setdefault(slug, {})


def load_content_plan():
    if not os.path.isfile(CONTENT_PLAN_PATH):
        return None

    with open(CONTENT_PLAN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_content_plan(content_plan):
    os.makedirs(os.path.dirname(CONTENT_PLAN_PATH), exist_ok=True)
    temp_path = f"{CONTENT_PLAN_PATH}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(content_plan, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    os.replace(temp_path, CONTENT_PLAN_PATH)


def frontmatter_scalar(content: str, key: str):
    match = re.match(r"\A---\s*\n(?P<body>.*?)\n---\s*", content, re.DOTALL)
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


def page_slug_for_content(content: str, default_slug: str):
    return slugify(
        frontmatter_scalar(content, "slug")
        or frontmatter_scalar(content, "title")
        or default_slug
    )


def split_mdx_pages(content: str, default_slug: str):
    content = content.strip()

    if content.startswith("```"):
        content = re.sub(r"^```(?:mdx|markdown)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    marker_pattern = re.compile(r"^<!--\s*page:\s*([a-z0-9][a-z0-9-]*)\s*-->\s*$", re.MULTILINE)
    matches = list(marker_pattern.finditer(content))

    if not matches:
        return [(page_slug_for_content(content, default_slug), content)]

    pages = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        page_slug = slugify(match.group(1))
        page_content = content[start:end].strip()

        if page_content:
            pages.append((page_slug, page_content))

    return pages


def discover_targets():
    return [
        {
            "slug": os.path.splitext(file_name)[0],
            "html_file": file_name,
            "html_path": os.path.join(INPUT_DIR, file_name),
            "step_1_path": os.path.join(STEP_1_DIR, f"{os.path.splitext(file_name)[0]}.md"),
            "step_3_path": os.path.join(STEP_3_DIR, f"{os.path.splitext(file_name)[0]}.md"),
            "source_html_hash": hash_file(os.path.join(INPUT_DIR, file_name)),
        }
        for file_name in sorted(os.listdir(INPUT_DIR))
        if file_name.endswith(".html")
    ]


def relative_step_4_path(file_path: str):
    return os.path.relpath(file_path, STEP_4_DIR)


def discover_step_4_outputs(slug: str):
    outputs = []
    single_output = os.path.join(STEP_4_DIR, f"{slug}.mdx")
    multi_output = os.path.join(STEP_4_DIR, slug)

    if os.path.isfile(single_output):
        outputs.append(relative_step_4_path(single_output))

    if os.path.isdir(multi_output):
        for root, _dirs, file_names in os.walk(multi_output):
            for file_name in sorted(file_names):
                if file_name.endswith(".mdx"):
                    outputs.append(relative_step_4_path(os.path.join(root, file_name)))

    return sorted(outputs)


def step_4_output_paths_exist(output_paths):
    return bool(output_paths) and all(
        os.path.isfile(os.path.join(STEP_4_DIR, output_path))
        for output_path in output_paths
    )


def step_4_output_hashes(output_paths):
    return {
        output_path: hash_file(os.path.join(STEP_4_DIR, output_path))
        for output_path in output_paths
        if os.path.isfile(os.path.join(STEP_4_DIR, output_path))
    }


def cleanup_step_4_outputs(slug: str):
    single_output = os.path.join(STEP_4_DIR, f"{slug}.mdx")
    multi_output = os.path.join(STEP_4_DIR, slug)

    if os.path.isfile(single_output):
        os.remove(single_output)
    if os.path.isdir(multi_output):
        shutil.rmtree(multi_output)


def discover_all_step_4_outputs():
    if not os.path.isdir(STEP_4_DIR):
        return []

    outputs = []
    for root, _dirs, file_names in os.walk(STEP_4_DIR):
        for file_name in sorted(file_names):
            if file_name.endswith(".mdx"):
                outputs.append(relative_step_4_path(os.path.join(root, file_name)))

    return sorted(outputs)


def parse_frontmatter(content: str):
    match = re.match(r"\A---\s*\n(?P<body>.*?)\n---\s*", content, re.DOTALL)
    if not match:
        return {}

    metadata = {}
    for line in match.group("body").splitlines():
        key, separator, raw_value = line.partition(":")
        if not separator:
            continue

        value = raw_value.strip()
        if value.startswith("[") and value.endswith("]"):
            metadata[key.strip()] = [
                item.strip().strip('"').strip("'")
                for item in value[1:-1].split(",")
                if item.strip()
            ]
        else:
            metadata[key.strip()] = value.strip('"').strip("'")

    return metadata


def optional_slug(value):
    return slugify(value) if value else ""


OPAQUE_LEGACY_ROUTE_SEGMENTS = {
    "0dekl",
    "1dekl",
    "2dekl",
    "3dekl",
    "4dekl",
    "5dekl",
    "adjekt1",
    "adjekt2",
    "adjekt3",
    "adjekt4",
    "adjekt5",
    "bi1",
    "defekt",
    "dekl",
    "fuer",
    "kopul1",
    "kopul2",
    "kopul3",
    "kopul4",
    "kopul5",
    "kopul6",
    "part",
    "typ1",
    "typ1ail",
    "typ1igh",
    "typ2",
    "verb1",
    "verb2",
    "verbadj",
    "verben",
    "verbend",
    "verbnom",
    "verbnom1",
    "zeitform",
}

PLAN_REQUIRED_STRING_FIELDS = [
    "sourceSlug",
    "title",
    "slug",
    "navTitle",
    "description",
    "category",
    "difficulty",
    "expectedLayout",
    "pagePurpose",
]
PLAN_REQUIRED_LIST_FIELDS = [
    "sourceRefs",
    "sourceSlugs",
    "tags",
    "prerequisiteTopics",
    "relatedTopics",
    "canonicalExamples",
]
ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced", "reference"}
HASH_LIKE_ROUTE_SEGMENT_PATTERN = re.compile(r"(?:^|-)[0-9a-f]{8,}(?:$|-)")
SECTION_SLUG_REWRITES = {
    ("verbs", "irregular-verbs"): ("Irregular", "irregular"),
    ("verbs", "defective-verbs"): ("Defective", "defective"),
    ("prepositions", "simple"): ("Conjugated", "conjugated"),
    ("prepositions", "compound-prepositions"): ("Compound", "compound"),
    ("prepositions", "genitive-prepositions"): ("Genitive", "genitive"),
    ("prepositions", "unconjugated-prepositions"): ("Unconjugated", "unconjugated"),
}
TOPIC_SLUG_REWRITES = {
    ("pronouns", "possessive-particles"): ("Possessive", "possessive"),
    ("pronouns", "personal-pronouns"): ("Personal", "personal"),
    ("pronouns", "possessive-pronouns"): ("Possessive", "possessive"),
    ("pronouns", "other-pronouns-particles"): ("Other pronouns", "other"),
}
OTHER_CATEGORY_REWRITES = [
    ({"pronouns", "personal-pronouns", "possessive-pronouns", "other-pronouns-particles", "possessive-particles"}, "Pronouns"),
    ({"pronunciation", "phonology", "orthography", "sound-changes", "internal-sound-changes"}, "Pronunciation"),
    ({"numbers", "fractions", "ordinal-numbers", "cardinal-numbers"}, "Numbers"),
    ({"definite-article", "article"}, "Articles"),
    ({"adverbs"}, "Adverbs"),
    ({"conjunctions"}, "Syntax"),
]
ANY_CATEGORY_REWRITES = [
    ({"pronouns", "personal-pronouns", "possessive-pronouns", "other-pronouns", "other-pronouns-particles", "possessive-particles"}, "Pronouns"),
]


def hash_like_route_segments(segments):
    return [
        segment
        for segment in segments
        if HASH_LIKE_ROUTE_SEGMENT_PATTERN.search(segment)
    ]


def redundant_route_segments(segments):
    redundant = []
    for parent, child in zip(segments, segments[1:]):
        parent_singular = parent[:-1] if parent.endswith("s") else parent
        if child == parent or child == parent_singular:
            redundant.append(child)
        elif child.endswith(f"-{parent}") or child.endswith(f"-{parent_singular}"):
            redundant.append(child)

    return redundant


def content_route_segments(metadata: dict):
    category = metadata.get("category") or "uncategorized"
    category_slug = slugify(category)
    page_slug = slugify(
        metadata.get("slug")
        or metadata.get("navTitle")
        or metadata.get("title")
        or "overview"
    )
    section_slug = optional_slug(metadata.get("sectionSlug") or metadata.get("section"))
    topic_slug = optional_slug(metadata.get("topicSlug") or metadata.get("topic"))
    segments = [category_slug]

    for segment in [section_slug, topic_slug]:
        if segment and segment not in segments:
            segments.append(segment)

    if page_slug not in segments:
        segments.append(page_slug)

    if len(segments) == 1:
        segments.append("overview")

    return segments


def content_route_path(metadata: dict):
    return "/".join(content_route_segments(metadata))


def organized_content_segments(_relative_path: str, content: str):
    return content_route_segments(parse_frontmatter(content))


def content_plan_pages_for_source(content_plan, source_slug: str):
    return [
        page
        for page in content_plan.get("pages", [])
        if source_slug in page.get("sourceSlugs", [])
    ]


def source_unit_id(index: int, heading: str):
    return f"u{index:03d}-{slugify(heading)[:60]}"


def source_units_from_markdown(markdown: str):
    heading_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    matches = list(heading_pattern.finditer(markdown))
    excerpt_chars = _content_plan_unit_excerpt_chars()

    if not matches:
        content = markdown.strip()
        return [{
            "unitId": "u001-source",
            "heading": "Source",
            "level": 1,
            "content": content,
            "excerpt": content[:excerpt_chars].strip(),
            "contentHash": hash_text(content),
        }]

    units = []
    for index, match in enumerate(matches, start=1):
        start = match.start()
        end = matches[index].start() if index < len(matches) else len(markdown)
        content = markdown[start:end].strip()
        heading = match.group(2).strip()
        units.append({
            "unitId": source_unit_id(index, heading),
            "heading": heading,
            "level": len(match.group(1)),
            "content": content,
            "excerpt": content[:excerpt_chars].strip(),
            "contentHash": hash_text(content),
        })

    return units


def source_units_for_target(target, include_content=True):
    units = source_units_from_markdown(read_text_file(target["step_3_path"]))
    if include_content:
        return units

    return [
        {key: value for key, value in unit.items() if key != "content"}
        for unit in units
    ]


def source_unit_index(targets):
    index = {}
    for target in targets:
        if os.path.isfile(target.get("step_3_path", "")):
            index[target["slug"]] = {
                unit["unitId"]: unit
                for unit in source_units_for_target(target)
            }
        else:
            index[target["slug"]] = {
                "u001-source": {
                    "unitId": "u001-source",
                    "heading": "Source",
                    "level": 1,
                    "content": "",
                    "excerpt": "",
                    "contentHash": "",
                }
            }

    return index


def validate_content_plan(content_plan, targets):
    errors = []
    target_slugs = {target["slug"] for target in targets}
    units_by_source = source_unit_index(targets)
    covered_units = set()
    duplicate_units = set()
    seen_routes = {}

    if not isinstance(content_plan, dict):
        raise ValueError("Content plan must be a JSON object.")
    if content_plan.get("version") != CONTENT_PLAN_VERSION:
        errors.append(f"Content plan version must be {CONTENT_PLAN_VERSION}.")

    pages = content_plan.get("pages")
    if not isinstance(pages, list) or not pages:
        errors.append("Content plan must contain a non-empty pages array.")
        pages = []

    for index, page in enumerate(pages):
        label = f"pages[{index}]"
        if not isinstance(page, dict):
            errors.append(f"{label} must be an object.")
            continue

        for field in PLAN_REQUIRED_STRING_FIELDS:
            if not isinstance(page.get(field), str) or not page.get(field).strip():
                errors.append(f"{label}.{field} must be a non-empty string.")

        for field in PLAN_REQUIRED_LIST_FIELDS:
            if not isinstance(page.get(field), list):
                errors.append(f"{label}.{field} must be an array.")

        if not isinstance(page.get("order"), int):
            errors.append(f"{label}.order must be an integer.")
        if page.get("difficulty") not in ALLOWED_DIFFICULTIES:
            errors.append(f"{label}.difficulty must be one of {sorted(ALLOWED_DIFFICULTIES)}.")

        source_slug = page.get("sourceSlug")
        source_slugs = page.get("sourceSlugs") if isinstance(page.get("sourceSlugs"), list) else []
        if source_slug not in target_slugs:
            errors.append(f"{label}.sourceSlug '{source_slug}' is not a known source.")
        if source_slug and source_slug not in source_slugs:
            errors.append(f"{label}.sourceSlugs must include sourceSlug '{source_slug}'.")
        for slug in source_slugs:
            if slug not in target_slugs:
                errors.append(f"{label}.sourceSlugs contains unknown source '{slug}'.")

        source_refs = page.get("sourceRefs") if isinstance(page.get("sourceRefs"), list) else []
        ref_source_slugs = set()
        for ref_index, source_ref in enumerate(source_refs):
            ref_label = f"{label}.sourceRefs[{ref_index}]"
            if not isinstance(source_ref, dict):
                errors.append(f"{ref_label} must be an object.")
                continue

            ref_source_slug = source_ref.get("sourceSlug")
            ref_unit_ids = source_ref.get("unitIds")
            ref_source_slugs.add(ref_source_slug)
            if ref_source_slug not in target_slugs:
                errors.append(f"{ref_label}.sourceSlug '{ref_source_slug}' is not a known source.")
                continue
            if ref_source_slug not in source_slugs:
                errors.append(f"{ref_label}.sourceSlug must also appear in {label}.sourceSlugs.")
            if not isinstance(ref_unit_ids, list) or not ref_unit_ids:
                errors.append(f"{ref_label}.unitIds must be a non-empty array.")
                continue

            known_units = units_by_source.get(ref_source_slug, {})
            for unit_id in ref_unit_ids:
                unit_key = (ref_source_slug, unit_id)
                if unit_id not in known_units:
                    errors.append(f"{ref_label}.unitIds contains unknown unit '{unit_id}'.")
                elif unit_key in covered_units:
                    duplicate_units.add(unit_key)
                else:
                    covered_units.add(unit_key)

        missing_ref_slugs = sorted(set(source_slugs) - ref_source_slugs)
        if missing_ref_slugs:
            errors.append(f"{label}.sourceRefs must include every sourceSlug: {', '.join(missing_ref_slugs)}.")

        route = content_route_path(page)
        if route in seen_routes:
            errors.append(f"{label} duplicates route '{route}' from {seen_routes[route]}.")
        else:
            seen_routes[route] = label

        legacy_segments = set(route.split("/")) & OPAQUE_LEGACY_ROUTE_SEGMENTS
        if legacy_segments:
            errors.append(f"{label} route '{route}' contains legacy source segment(s): {sorted(legacy_segments)}.")
        hash_segments = hash_like_route_segments(route.split("/"))
        if hash_segments:
            errors.append(f"{label} route '{route}' contains hash-like segment(s): {hash_segments}.")
        redundant_segments = redundant_route_segments(route.split("/"))
        if redundant_segments:
            errors.append(f"{label} route '{route}' contains redundant segment(s): {redundant_segments}.")

    all_units = {
        (source_slug, unit_id)
        for source_slug, units in units_by_source.items()
        for unit_id in units
    }
    covered_source_slugs = {
        source_slug
        for source_slug, _unit_id in covered_units
    }
    missing_sources = sorted(target_slugs - covered_source_slugs)
    if missing_sources:
        errors.append(f"Content plan does not cover source(s): {', '.join(missing_sources)}.")

    missing_units = sorted(all_units - covered_units)
    if missing_units:
        formatted_units = ", ".join(f"{source_slug}:{unit_id}" for source_slug, unit_id in missing_units)
        errors.append(f"Content plan does not cover source unit(s): {formatted_units}.")
    if duplicate_units:
        formatted_units = ", ".join(f"{source_slug}:{unit_id}" for source_slug, unit_id in sorted(duplicate_units))
        errors.append(f"Content plan assigns source unit(s) more than once: {formatted_units}.")

    if errors:
        raise ValueError("Invalid content plan:\n- " + "\n- ".join(errors))

    return content_plan


def _unit_source_lookup(units_by_source):
    lookup = {}
    for source_slug, units in units_by_source.items():
        for unit_id in units:
            lookup.setdefault(unit_id, []).append(source_slug)

    return lookup


def _source_ref_map(page, units_by_source, unit_sources, seen_units):
    refs_by_source = {}

    for source_ref in page.get("sourceRefs", []):
        if not isinstance(source_ref, dict):
            continue

        source_slug = source_ref.get("sourceSlug")
        unit_ids = source_ref.get("unitIds")
        if not isinstance(unit_ids, list):
            continue

        for unit_id in unit_ids:
            actual_source_slug = None
            if unit_id in units_by_source.get(source_slug, {}):
                actual_source_slug = source_slug
            else:
                possible_sources = unit_sources.get(unit_id, [])
                if len(possible_sources) == 1:
                    actual_source_slug = possible_sources[0]

            if not actual_source_slug:
                continue

            unit_key = (actual_source_slug, unit_id)
            if unit_key in seen_units:
                continue

            seen_units.add(unit_key)
            refs_by_source.setdefault(actual_source_slug, []).append(unit_id)

    return refs_by_source


def _normalise_page_source_refs(page, refs_by_source):
    source_slugs = sorted(refs_by_source)
    page["sourceSlugs"] = source_slugs
    page["sourceRefs"] = [
        {"sourceSlug": source_slug, "unitIds": unit_ids}
        for source_slug, unit_ids in refs_by_source.items()
    ]

    if source_slugs and page.get("sourceSlug") not in source_slugs:
        page["sourceSlug"] = source_slugs[0]


def _fallback_page_for_missing_units(source_slug, missing_unit_ids, units_by_source, index):
    first_unit = units_by_source[source_slug][missing_unit_ids[0]]
    topic = first_unit.get("heading") or "Additional reference notes"

    return {
        "sourceSlug": source_slug,
        "sourceSlugs": [source_slug],
        "sourceRefs": [{"sourceSlug": source_slug, "unitIds": missing_unit_ids}],
        "title": f"{topic}: Additional Reference Notes",
        "slug": "additional-notes",
        "navTitle": "Additional notes",
        "description": "Reference material preserved from the source plan repair pass for review and integration.",
        "category": "Other",
        "section": "Coverage review",
        "sectionSlug": "coverage-review",
        "topic": topic,
        "topicSlug": slugify(topic),
        "difficulty": "reference",
        "order": 9000 + index,
        "tags": ["coverage", "reference"],
        "prerequisiteTopics": [],
        "relatedTopics": [],
        "canonicalExamples": [],
        "expectedLayout": "advanced notes",
        "pagePurpose": "Preserve assigned source units that were not placed by the initial content plan.",
    }


def _route_text(page):
    return " ".join(
        str(page.get(field, ""))
        for field in ["category", "section", "sectionSlug", "topic", "topicSlug", "title", "slug", "navTitle"]
    ).lower()


def _category_from_route_hints(page, rewrites):
    route_tokens = set(re.split(r"[^a-z0-9]+", _route_text(page)))
    route_slug_text = " ".join(content_route_segments(page))
    route_slug_tokens = set(re.split(r"[^a-z0-9]+", route_slug_text))
    tokens = route_tokens | route_slug_tokens | set(page.get("tags", []))

    for hints, category in rewrites:
        if tokens & hints:
            return category

    return None


def _normalise_category(page):
    promoted_category = _category_from_route_hints(page, ANY_CATEGORY_REWRITES)
    if promoted_category:
        page["category"] = promoted_category
        return

    if slugify(page.get("category", "")) == "other":
        promoted_category = _category_from_route_hints(page, OTHER_CATEGORY_REWRITES)
        if promoted_category:
            page["category"] = promoted_category


def _normalise_section_slug(page):
    category_slug = slugify(page.get("category") or "")
    section_slug = optional_slug(page.get("sectionSlug") or page.get("section"))
    rewrite = SECTION_SLUG_REWRITES.get((category_slug, section_slug))

    if rewrite:
        section, rewritten_slug = rewrite
        page["section"] = section
        page["sectionSlug"] = rewritten_slug
        return

    if category_slug and category_slug in section_slug.split("-"):
        page["section"] = ""
        page["sectionSlug"] = ""
        return

    for suffix in [f"-{category_slug}", f"-{category_slug[:-1]}"]:
        if category_slug and section_slug.endswith(suffix):
            page["sectionSlug"] = section_slug[: -len(suffix)]
            return


def _normalise_topic_slug(page):
    category_slug = slugify(page.get("category") or "")
    topic_slug = optional_slug(page.get("topicSlug") or page.get("topic"))
    rewrite = TOPIC_SLUG_REWRITES.get((category_slug, topic_slug))

    if rewrite:
        topic, rewritten_slug = rewrite
        page["topic"] = topic
        page["topicSlug"] = rewritten_slug
        return

    if category_slug and topic_slug in {category_slug, category_slug[:-1]}:
        page["topic"] = ""
        page["topicSlug"] = ""
        return

    for suffix in [f"-{category_slug}", f"-{category_slug[:-1]}", "-particles"]:
        if topic_slug.endswith(suffix):
            page["topicSlug"] = topic_slug[: -len(suffix)]
            return


def _normalise_page_slug(page):
    section_slug = optional_slug(page.get("sectionSlug") or page.get("section"))
    topic_slug = optional_slug(page.get("topicSlug") or page.get("topic"))
    page_slug = optional_slug(page.get("slug") or page.get("navTitle") or page.get("title"))

    category_slug = optional_slug(page.get("category"))

    for parent_slug in [topic_slug, section_slug, category_slug, category_slug[:-1]]:
        if parent_slug and page_slug.startswith(f"{parent_slug}-"):
            page["slug"] = page_slug[len(parent_slug) + 1:]
            return
        if parent_slug and page_slug.endswith(f"-{parent_slug}"):
            page["slug"] = page_slug[: -len(parent_slug) - 1]
            return


def normalise_public_route_metadata(content_plan):
    for page in content_plan.get("pages", []):
        if not isinstance(page, dict):
            continue

        for _iteration in range(3):
            _normalise_category(page)
            _normalise_section_slug(page)
            _normalise_topic_slug(page)
            _normalise_page_slug(page)


def _dedupe_content_plan_routes(content_plan):
    seen_routes = set()
    for index, page in enumerate(content_plan.get("pages", []), start=1):
        route = content_route_path(page)
        if route not in seen_routes:
            seen_routes.add(route)
            continue

        page["slug"] = f"{slugify(page.get('slug') or 'page')}-{index}"
        seen_routes.add(content_route_path(page))


def repair_content_plan_coverage(content_plan, targets):
    content_plan = json.loads(json.dumps(content_plan))
    content_plan["version"] = CONTENT_PLAN_VERSION
    content_plan.setdefault("audience", "advanced-reference")
    pages = content_plan.get("pages") if isinstance(content_plan.get("pages"), list) else []
    units_by_source = source_unit_index(targets)
    unit_sources = _unit_source_lookup(units_by_source)
    seen_units = set()
    repaired_pages = []

    for page in pages:
        if not isinstance(page, dict):
            continue

        refs_by_source = _source_ref_map(page, units_by_source, unit_sources, seen_units)
        if not refs_by_source:
            continue

        _normalise_page_source_refs(page, refs_by_source)
        repaired_pages.append(page)

    content_plan["pages"] = repaired_pages

    fallback_index = 0
    for source_slug, units in units_by_source.items():
        missing_unit_ids = [
            unit_id
            for unit_id in units
            if (source_slug, unit_id) not in seen_units
        ]
        if not missing_unit_ids:
            continue

        fallback_index += 1
        content_plan["pages"].append(
            _fallback_page_for_missing_units(source_slug, missing_unit_ids, units_by_source, fallback_index)
        )
        seen_units.update((source_slug, unit_id) for unit_id in missing_unit_ids)

    normalise_public_route_metadata(content_plan)
    _dedupe_content_plan_routes(content_plan)
    return content_plan


MIXED_ITALIC_CODE_PATTERN = re.compile(r"(?<!\*)\*`[^`\n]+`\*(?!\*)|(?<!_)_`[^`\n]+`_(?!_)")


def lint_mdx_content(relative_path: str, content: str, content_plan=None):
    errors = []
    warnings = []
    metadata = parse_frontmatter(content)

    for field in ["title", "slug", "navTitle", "description", "category", "difficulty"]:
        if not metadata.get(field):
            errors.append(f"{relative_path}: missing required frontmatter field '{field}'.")

    for field in ["tags", "prerequisiteTopics", "relatedTopics", "canonicalExamples"]:
        if field not in metadata:
            errors.append(f"{relative_path}: missing required frontmatter field '{field}'.")

    if MIXED_ITALIC_CODE_PATTERN.search(content):
        errors.append(f"{relative_path}: contains mixed italic/code styling such as *`example`*.")

    route_segments = content_route_segments(metadata)
    legacy_segments = set(route_segments) & OPAQUE_LEGACY_ROUTE_SEGMENTS
    if legacy_segments:
        errors.append(f"{relative_path}: route contains legacy source segment(s): {sorted(legacy_segments)}.")
    hash_segments = hash_like_route_segments(route_segments)
    if hash_segments:
        errors.append(f"{relative_path}: route contains hash-like segment(s): {hash_segments}.")
    redundant_segments = redundant_route_segments(route_segments)
    if redundant_segments:
        errors.append(f"{relative_path}: route contains redundant segment(s): {redundant_segments}.")

    if re.search(r"(?ms)^##\s+Prepositional Pronouns\b(?:(?!^##\s).)*^###\s+", content):
        if not re.search(r"(?ms)^##\s+Prepositional Pronouns\b(?:(?!^##\s).)*^\|.+\|", content):
            warnings.append(f"{relative_path}: prepositional pronoun paradigm may be clearer as a compact table.")

    return errors, warnings


def unique_relative_path(relative_path: Path, used_paths):
    if relative_path not in used_paths:
        used_paths.add(relative_path)
        return relative_path

    raise ValueError(f"Duplicate organised path: {relative_path}")


def rewrite_component_imports(content: str, target_relative_path: Path):
    parent_depth = len(target_relative_path.parent.parts)
    component_prefix = "/".join([".."] * (parent_depth + 2) + ["components"])

    return re.sub(
        r"from\s+(['\"])(?:\.\./)+components/",
        rf"from \1{component_prefix}/",
        content,
    )


def publish_organized_content():
    outputs = discover_all_step_4_outputs()
    if not outputs:
        print("\n📚 No step_4 MDX files found to organise.")
        return

    content_plan = load_content_plan()
    expected_routes = set()
    if content_plan:
        validate_content_plan(content_plan, discover_targets())
        expected_routes = {
            content_route_path(page)
            for page in content_plan.get("pages", [])
        }

    target_dir = Path(os.getenv("PIPELINE_ASTRO_CONTENT_DIR", str(ASTRO_CONTENT_DIR))).resolve()
    project_content_dir = (PROJECT_ROOT / "src" / "content").resolve()
    if project_content_dir not in target_dir.parents:
        raise ValueError(f"Refusing to write outside src/content: {target_dir}")

    used_paths = set()
    generated_routes = set()
    lint_errors = []
    lint_warnings = []
    planned_writes = []
    for output_path in outputs:
        source_path = Path(STEP_4_DIR) / output_path
        content = read_text_file(str(source_path))
        metadata = parse_frontmatter(content)
        route = content_route_path(metadata)
        errors, warnings = lint_mdx_content(output_path, content, content_plan)
        lint_errors.extend(errors)
        lint_warnings.extend(warnings)

        if expected_routes and route not in expected_routes:
            lint_errors.append(f"{output_path}: route '{route}' is not present in the content plan.")

        generated_routes.add(route)
        target_relative_path = unique_relative_path(
            Path(*organized_content_segments(output_path, content)).with_suffix(".mdx"),
            used_paths,
        )
        planned_writes.append((target_relative_path, content))

    missing_routes = sorted(expected_routes - generated_routes)
    if missing_routes:
        lint_errors.append("Planned page route(s) missing generated MDX: " + ", ".join(missing_routes))

    for warning in lint_warnings:
        print(f"⚠️  {warning}")

    if lint_errors:
        raise ValueError("Content validation failed:\n- " + "\n- ".join(lint_errors))

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    copied_paths = []
    for target_relative_path, content in planned_writes:
        target_path = target_dir / target_relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(
            rewrite_component_imports(content, target_relative_path),
            encoding="utf-8",
        )
        copied_paths.append(target_relative_path.as_posix())

    print(f"\n📚 Organised {len(copied_paths)} MDX files into {target_dir}")


def model_config(model_type: str, temperature: float):
    if model_type not in GEMINI_MODELS:
        raise ValueError(f"Invalid model type: {model_type}. Must be one of {list(GEMINI_MODELS.keys())}")

    return {
        "model_type": model_type,
        "model_id": GEMINI_MODELS[model_type],
        "temperature": temperature,
    }


def get_pipeline_model_configs(profile_name="economy"):
    if profile_name not in MODEL_PROFILES:
        raise ValueError(f"Invalid model profile: {profile_name}. Must be one of {list(MODEL_PROFILES.keys())}")

    profile = MODEL_PROFILES[profile_name]
    translator_type, translator_temperature = profile["translator"]
    planner_type, planner_temperature = profile["planner"]
    enricher_type, enricher_temperature = profile["enricher"]

    return {
        "profile": profile_name,
        "translator": model_config(translator_type, translator_temperature),
        "planner": model_config(planner_type, planner_temperature),
        "enricher": model_config(enricher_type, enricher_temperature),
    }


def prompt_metadata():
    return {
        "translation": {
            "version": PROMPT_VERSIONS["translation"],
            "hash": hash_text(prompt.TRANSLATE_SYSTEM_PROMPT),
        },
        "content_plan": {
            "version": PROMPT_VERSIONS["content_plan"],
            "hash": hash_text(prompt.CONTENT_PLAN_SYSTEM_PROMPT),
        },
        "enrichment": {
            "version": PROMPT_VERSIONS["enrichment"],
            "hash": hash_text(prompt.IMPROVE_UX_SYSTEM_PROMPT),
        },
    }


def stage_config_changed(stage_record, stage_config, stage_prompt):
    return any([
        stage_record.get("model_type") != stage_config["model_type"],
        stage_record.get("model_id") != stage_config["model_id"],
        stage_record.get("temperature") != stage_config["temperature"],
        stage_record.get("prompt_version") != stage_prompt["version"],
        stage_record.get("prompt_hash") != stage_prompt["hash"],
    ])


def parsed_markdown_is_suspiciously_large(target):
    source_size = file_size(target["html_path"])
    step_1_size = file_size(target["step_1_path"])

    return all([
        source_size > 0,
        step_1_size >= STEP_1_BLOAT_MIN_BYTES,
        step_1_size > source_size * STEP_1_BLOAT_RATIO,
    ])


def translation_changed(record, target, stage_config, stage_prompt):
    translation_record = record.get("translation")
    if not translation_record:
        return False

    step_1_hash = hash_file(target["step_1_path"]) if os.path.isfile(target["step_1_path"]) else None
    step_3_hash = hash_file(target["step_3_path"]) if os.path.isfile(target["step_3_path"]) else None

    return any([
        translation_record.get("input_hash") != step_1_hash,
        translation_record.get("output_hash") != step_3_hash,
        stage_config_changed(translation_record, stage_config, stage_prompt),
    ])


def translated_input_hashes(targets):
    return {
        target["slug"]: hash_file(target["step_3_path"])
        for target in targets
        if os.path.isfile(target["step_3_path"])
    }


def content_plan_changed(manifest, targets, stage_config, stage_prompt):
    plan_record = manifest.get("content_plan")
    if not plan_record or not os.path.isfile(CONTENT_PLAN_PATH):
        return True

    try:
        validate_content_plan(load_content_plan(), targets)
    except (json.JSONDecodeError, ValueError, TypeError) as error:
        print(f"⚠️  Existing content plan is invalid: {error}")
        return True

    return any([
        plan_record.get("input_hashes") != translated_input_hashes(targets),
        stage_config_changed(plan_record, stage_config, stage_prompt),
    ])


def current_content_plan_hash():
    return hash_file(CONTENT_PLAN_PATH) if os.path.isfile(CONTENT_PLAN_PATH) else None


def enrichment_changed(record, target, stage_config, stage_prompt):
    enrichment_record = record.get("enrichment")
    if not enrichment_record:
        return False

    output_paths = (
        enrichment_record.get("output_paths")
        or record.get("step_4_output_paths")
        or []
    )
    recorded_hashes = enrichment_record.get("output_hashes") or {}
    current_hashes = step_4_output_hashes(output_paths)
    step_3_hash = hash_file(target["step_3_path"]) if os.path.isfile(target["step_3_path"]) else None
    content_plan_hash = current_content_plan_hash()

    return any([
        enrichment_record.get("input_hash") != step_3_hash,
        content_plan_hash and enrichment_record.get("content_plan_hash") != content_plan_hash,
        not step_4_output_paths_exist(output_paths),
        recorded_hashes != current_hashes,
        stage_config_changed(enrichment_record, stage_config, stage_prompt),
    ])


def planned_page_output_path(page):
    return os.path.join(STEP_4_DIR, f"{content_route_path(page)}.mdx")


def planned_page_output_relative_path(page):
    return os.path.relpath(planned_page_output_path(page), STEP_4_DIR)


def page_enrichment_record(manifest, page):
    route = content_route_path(page)
    return manifest.setdefault("pages", {}).get(route, {})


def page_enrichment_changed(manifest, page, stage_config, stage_prompt):
    record = page_enrichment_record(manifest, page)
    output_path = planned_page_output_path(page)
    output_hash = hash_file(output_path) if os.path.isfile(output_path) else None

    if not record:
        return True

    return any([
        not os.path.isfile(output_path),
        record.get("output_hash") != output_hash,
        record.get("content_plan_hash") != current_content_plan_hash(),
        stage_config_changed(record, stage_config, stage_prompt),
    ])


def update_page_enrichment_record(manifest, page, stage_config, stage_prompt):
    output_path = planned_page_output_path(page)
    if not os.path.isfile(output_path):
        return

    route = content_route_path(page)
    manifest.setdefault("pages", {})[route] = {
        "output_path": planned_page_output_relative_path(page),
        "output_hash": hash_file(output_path),
        "content_plan_hash": current_content_plan_hash(),
        "prompt_hash": stage_prompt["hash"],
        "prompt_version": stage_prompt["version"],
        "model_type": stage_config["model_type"],
        "model_id": stage_config["model_id"],
        "temperature": stage_config["temperature"],
    }


def build_pipeline_plan(targets, manifest, configs, prompts, force_content_plan_stage=None):
    if force_content_plan_stage is None:
        force_content_plan_stage = force_content_plan()

    plan = {
        "parse": [],
        "translate": [],
        "content_plan": False,
        "enrich": [],
    }
    translate_pending_slugs = set()

    for target in targets:
        slug = target["slug"]
        record = manifest.get("files", {}).get(slug, {})
        source_changed = (
            record.get("source_html_hash") is not None
            and record.get("source_html_hash") != target["source_html_hash"]
        )
        step_1_exists = os.path.isfile(target["step_1_path"])
        step_3_exists = os.path.isfile(target["step_3_path"])

        parse_pending = any([
            force_regenerate(),
            not step_1_exists,
            source_changed,
            parsed_markdown_is_suspiciously_large(target),
        ])
        translate_pending = any([
            force_regenerate(),
            parse_pending,
            not step_3_exists,
            translation_changed(record, target, configs["translator"], prompts["translation"]),
        ])

        if parse_pending:
            plan["parse"].append(target)
        if translate_pending:
            plan["translate"].append(target)
            translate_pending_slugs.add(slug)

    all_translations_ready = all(os.path.isfile(target["step_3_path"]) for target in targets)
    content_plan_pending = (
        all_translations_ready
        and not translate_pending_slugs
        and any([
            force_regenerate(),
            force_content_plan_stage,
            content_plan_changed(manifest, targets, configs["planner"], prompts["content_plan"]),
        ])
    )
    plan["content_plan"] = content_plan_pending

    if all_translations_ready and not translate_pending_slugs and not content_plan_pending:
        try:
            content_plan = validate_content_plan(load_content_plan(), targets)
        except (json.JSONDecodeError, ValueError, TypeError):
            content_plan = None

        if content_plan:
            for page in content_plan.get("pages", []):
                if any([
                    force_regenerate(),
                    page_enrichment_changed(manifest, page, configs["enricher"], prompts["enrichment"]),
                ]):
                    plan["enrich"].append(page)

    return plan


def format_slugs(targets):
    if not targets:
        return "(none)"
    return ", ".join(content_route_path(target) if "category" in target else target["slug"] for target in targets)


def print_run_summary(title, plan):
    print(f"\n📋 {title}")
    print(f"Parse pending: {len(plan['parse'])} — {format_slugs(plan['parse'])}")
    print(f"Translate pending: {len(plan['translate'])} — {format_slugs(plan['translate'])}")
    print(f"Content plan pending: {'yes' if plan['content_plan'] else 'no'}")
    print(f"Enrich pending: {len(plan['enrich'])} — {format_slugs(plan['enrich'])}")


def llm_timeout_seconds():
    try:
        return float(os.getenv("PIPELINE_LLM_TIMEOUT_SECONDS", 600))
    except ValueError:
        return 600.0


def llm_cache_dir():
    return os.getenv("PIPELINE_LLM_CACHE_DIR", LLM_CACHE_DIR)


def llm_cache_namespace(stage_name: str, slug: str, stage_config, stage_prompt):
    return "-".join([
        stage_name,
        slug,
        stage_config["model_id"],
        str(stage_config["temperature"]),
        stage_prompt["hash"][:16],
    ])


def get_gemini_llm(model_type="coding", temperature=0.1):
    from langchain_openai import ChatOpenAI

    if model_type not in GEMINI_MODELS:
        raise ValueError(f"Invalid model type: {model_type}. Must be one of {list(GEMINI_MODELS.keys())}")

    print(f"🔌 Connected to {model_type.upper()} ({GEMINI_MODELS[model_type]})")

    return ChatOpenAI(
        model=GEMINI_MODELS[model_type],
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        temperature=temperature,
        timeout=llm_timeout_seconds(),
        max_retries=2,
    )


def update_parse_record(manifest, target):
    if not os.path.isfile(target["step_1_path"]):
        return

    record = manifest_record(manifest, target["slug"])
    record["source_html_hash"] = target["source_html_hash"]
    record["step_1_markdown_hash"] = hash_file(target["step_1_path"])


def update_translation_record(manifest, target, stage_config, stage_prompt):
    if not os.path.isfile(target["step_1_path"]) or not os.path.isfile(target["step_3_path"]):
        return

    record = manifest_record(manifest, target["slug"])
    update_parse_record(manifest, target)

    step_3_hash = hash_file(target["step_3_path"])
    record["step_3_translation_hash"] = step_3_hash
    record["translation"] = {
        "input_hash": hash_file(target["step_1_path"]),
        "output_hash": step_3_hash,
        "prompt_hash": stage_prompt["hash"],
        "prompt_version": stage_prompt["version"],
        "model_type": stage_config["model_type"],
        "model_id": stage_config["model_id"],
        "temperature": stage_config["temperature"],
    }


def markdown_headings(markdown: str, limit=30):
    return [
        match.group(2).strip()
        for match in re.finditer(r"^(#{1,4})\s+(.+)$", markdown, re.MULTILINE)
    ][:limit]


def source_brief_for_target(target):
    markdown = read_text_file(target["step_3_path"])
    headings = markdown_headings(markdown)
    title = headings[0] if headings else target["slug"]
    units = source_units_for_target(target, include_content=False)

    return {
        "sourceSlug": target["slug"],
        "title": title,
        "headings": headings,
        "units": units,
        "excerpt": markdown[:_content_plan_excerpt_chars()].strip(),
        "contentHash": hash_file(target["step_3_path"]),
    }


def _content_plan_excerpt_chars():
    try:
        return int(os.getenv("PIPELINE_CONTENT_PLAN_EXCERPT_CHARS", 3000))
    except ValueError:
        return 3000


def _content_plan_unit_excerpt_chars():
    try:
        return int(os.getenv("PIPELINE_CONTENT_PLAN_UNIT_EXCERPT_CHARS", 700))
    except ValueError:
        return 700


def build_source_briefs(targets):
    return {
        "version": CONTENT_PLAN_VERSION,
        "audience": "advanced-reference",
        "sources": [source_brief_for_target(target) for target in targets],
    }


def update_content_plan_record(manifest, targets, stage_config, stage_prompt):
    if not os.path.isfile(CONTENT_PLAN_PATH):
        return

    content_plan = validate_content_plan(load_content_plan(), targets)
    manifest["content_plan"] = {
        "content_plan_hash": hash_file(CONTENT_PLAN_PATH),
        "input_hashes": translated_input_hashes(targets),
        "page_count": len(content_plan.get("pages", [])),
        "prompt_hash": stage_prompt["hash"],
        "prompt_version": stage_prompt["version"],
        "model_type": stage_config["model_type"],
        "model_id": stage_config["model_id"],
        "temperature": stage_config["temperature"],
    }


def update_enrichment_record(manifest, target, stage_config, stage_prompt):
    if not os.path.isfile(target["step_3_path"]):
        return

    output_paths = discover_step_4_outputs(target["slug"])
    if not output_paths:
        return

    record = manifest_record(manifest, target["slug"])
    record["step_4_output_paths"] = output_paths
    record["enrichment"] = {
        "input_hash": hash_file(target["step_3_path"]),
        "content_plan_hash": current_content_plan_hash(),
        "output_paths": output_paths,
        "output_hashes": step_4_output_hashes(output_paths),
        "prompt_hash": stage_prompt["hash"],
        "prompt_version": stage_prompt["version"],
        "model_type": stage_config["model_type"],
        "model_id": stage_config["model_id"],
        "temperature": stage_config["temperature"],
    }


def adopt_completed_outputs(targets, manifest, configs, prompts, plan):
    pending_parse = {target["slug"] for target in plan["parse"]}
    pending_translate = {target["slug"] for target in plan["translate"]}
    pending_enrich = {target["slug"] for target in plan["enrich"]}

    for target in targets:
        slug = target["slug"]
        if slug not in pending_parse:
            update_parse_record(manifest, target)
        if slug not in pending_translate:
            update_translation_record(manifest, target, configs["translator"], prompts["translation"])
        if slug not in pending_enrich:
            update_enrichment_record(manifest, target, configs["enricher"], prompts["enrichment"])

    if not plan["content_plan"] and os.path.isfile(CONTENT_PLAN_PATH):
        update_content_plan_record(manifest, targets, configs["planner"], prompts["content_plan"])


def parse_from_html(targets, manifest):
    os.makedirs(STEP_1_DIR, exist_ok=True)

    for target in targets:
        print(f"📄 Parsing: {target['html_file']}")
        raw_html_content = read_text_file(target["html_path"], encoding="iso-8859-1")
        content = prompt.parse_content_to_markdown(raw_html_content)
        save_file(content, STEP_1_DIR, f"{target['slug']}.md")
        update_parse_record(manifest, target)
        save_manifest(manifest)


def tokenise(llm: BaseChatModel, _token_manager: TokenManager):
    os.makedirs(STEP_2_DIR, exist_ok=True)
    file_names = [f for f in os.listdir(STEP_1_DIR) if f.endswith(".md")]

    for file_name in file_names:
        print(f"📄 Tokenising: {file_name}")

        file_path = os.path.join(STEP_1_DIR, file_name)
        markdown_content = read_text_file(file_path)

        # Legacy inactive stage. The active pipeline translates directly from step_1.
        content = prompt.tokenise_irish_content(llm, markdown_content)
        save_file(content, STEP_2_DIR, file_name)


def translate(llm: BaseChatModel, targets, manifest, stage_config, stage_prompt):
    os.makedirs(STEP_3_DIR, exist_ok=True)

    for target in targets:
        print(f"📄 Translating: {target['slug']}.md")
        markdown_content = read_text_file(target["step_1_path"])
        content = prompt.translate_to_english(
            llm,
            markdown_content,
            cache_dir=llm_cache_dir(),
            cache_namespace=llm_cache_namespace("translation", target["slug"], stage_config, stage_prompt),
        )
        save_file(content, STEP_3_DIR, f"{target['slug']}.md")
        update_translation_record(manifest, target, stage_config, stage_prompt)
        save_manifest(manifest)


def plan_content(llm: BaseChatModel, targets, manifest, stage_config, stage_prompt):
    print("🧭 Planning content architecture")
    source_briefs = build_source_briefs(targets)
    raw_plan = prompt.generate_content_plan(
        llm,
        source_briefs,
        cache_dir=llm_cache_dir(),
        cache_namespace=llm_cache_namespace("content-plan", "all-sources", stage_config, stage_prompt),
    )
    initial_plan = extract_json_object(raw_plan)
    content_plan = repair_content_plan_coverage(initial_plan, targets)
    repaired_count = len(content_plan.get("pages", [])) - len(initial_plan.get("pages", []))
    if repaired_count:
        print(f"🧭 Added {repaired_count} coverage repair page(s).")
    validate_content_plan(content_plan, targets)
    save_content_plan(content_plan)
    update_content_plan_record(manifest, targets, stage_config, stage_prompt)
    save_manifest(manifest)
    print(f"🧭 Planned {len(content_plan.get('pages', []))} content pages.")


def page_source_markdown(page, targets):
    units_by_source = source_unit_index(targets)
    sections = []

    for source_ref in page.get("sourceRefs", []):
        source_slug = source_ref["sourceSlug"]
        unit_ids = source_ref["unitIds"]
        sections.append(f"# Source: {source_slug}")

        for unit_id in unit_ids:
            unit = units_by_source[source_slug][unit_id]
            sections.append(f"<!-- source-unit: {source_slug}:{unit_id} -->\n{unit['content']}")

    return "\n\n".join(sections).strip()


def write_planned_page(page, page_content: str):
    output_path = Path(planned_page_output_path(page))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page_content, encoding="utf-8")
    print(f"Saved to {output_path}")


def enrich(llm: BaseChatModel, pages, manifest, stage_config, stage_prompt, content_plan, targets):
    os.makedirs(STEP_4_DIR, exist_ok=True)
    validate_content_plan(content_plan, targets)

    for page in pages:
        route = content_route_path(page)
        print(f"📄 Enriching: {route}")
        markdown_content = page_source_markdown(page, targets)
        content = prompt.improve_ux(
            llm,
            markdown_content,
            source_slug=route,
            planned_pages=[page],
            cache_dir=llm_cache_dir(),
            cache_namespace=llm_cache_namespace("enrichment", route, stage_config, stage_prompt),
        )
        generated_pages = split_mdx_pages(content, page["slug"])
        actual_slugs = [page_slug for page_slug, _page_content in generated_pages]
        if actual_slugs != [page["slug"]]:
            raise ValueError(
                f"Generated page slug for {route} does not match content plan. "
                f"Expected {[page['slug']]}, got {actual_slugs}."
            )

        write_planned_page(page, generated_pages[0][1])
        update_page_enrichment_record(manifest, page, stage_config, stage_prompt)
        save_manifest(manifest)


if __name__ == "__main__":
    if organize_only():
        publish_organized_content()
        print("\n✅ Content organisation finished.")
        raise SystemExit(0)

    profile_name = os.getenv("PIPELINE_MODEL_PROFILE", "economy")
    configs = get_pipeline_model_configs(profile_name)
    prompts = prompt_metadata()
    manifest = load_manifest()
    targets = discover_targets()

    print("🚀 Planning pipeline...")
    print(f"📊 Model profile: {profile_name}")
    if force_regenerate():
        print("♻️  Force regenerate enabled.")
    if force_content_plan():
        print("🧭 Force content plan enabled.")

    force_content_plan_pending = force_content_plan()
    plan = build_pipeline_plan(
        targets,
        manifest,
        configs,
        prompts,
        force_content_plan_stage=force_content_plan_pending,
    )
    print_run_summary("Pipeline plan", plan)

    if dry_run():
        print("\n🧪 Dry run enabled. Exiting before deterministic writes or paid LLM calls.")
        raise SystemExit(0)

    adopt_completed_outputs(targets, manifest, configs, prompts, plan)
    save_manifest(manifest)

    if plan["parse"]:
        parse_from_html(plan["parse"], manifest)
        targets = discover_targets()
        plan = build_pipeline_plan(
            targets,
            manifest,
            configs,
            prompts,
            force_content_plan_stage=force_content_plan_pending,
        )
        adopt_completed_outputs(targets, manifest, configs, prompts, plan)
        save_manifest(manifest)
        print_run_summary("Paid-stage plan after parsing", plan)

    if plan["translate"]:
        translator_config = configs["translator"]
        llm_translator = get_gemini_llm(
            translator_config["model_type"],
            translator_config["temperature"],
        )
        translate(llm_translator, plan["translate"], manifest, translator_config, prompts["translation"])

        targets = discover_targets()
        plan = build_pipeline_plan(
            targets,
            manifest,
            configs,
            prompts,
            force_content_plan_stage=force_content_plan_pending,
        )
        adopt_completed_outputs(targets, manifest, configs, prompts, plan)
        save_manifest(manifest)
        print_run_summary("Enrichment plan after translation", plan)

    if plan["content_plan"]:
        planner_config = configs["planner"]
        llm_planner = get_gemini_llm(
            planner_config["model_type"],
            planner_config["temperature"],
        )
        plan_content(llm_planner, targets, manifest, planner_config, prompts["content_plan"])

        force_content_plan_pending = False
        plan = build_pipeline_plan(
            targets,
            manifest,
            configs,
            prompts,
            force_content_plan_stage=force_content_plan_pending,
        )
        adopt_completed_outputs(targets, manifest, configs, prompts, plan)
        save_manifest(manifest)
        print_run_summary("Enrichment plan after content planning", plan)

    if plan["enrich"]:
        content_plan = load_content_plan()
        if not content_plan:
            raise ValueError("Content plan is required before enrichment.")

        enricher_config = configs["enricher"]
        llm_enricher = get_gemini_llm(
            enricher_config["model_type"],
            enricher_config["temperature"],
        )
        enrich(llm_enricher, plan["enrich"], manifest, enricher_config, prompts["enrichment"], content_plan, targets)

    if organize_content():
        publish_organized_content()

    print("\n✅ All jobs finished.")
