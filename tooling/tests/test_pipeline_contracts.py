import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

langchain_core = types.ModuleType("langchain_core")
language_models = types.ModuleType("langchain_core.language_models")
prompts = types.ModuleType("langchain_core.prompts")
bs4 = types.ModuleType("bs4")
dotenv = types.ModuleType("dotenv")
language_models.BaseChatModel = object
prompts.ChatPromptTemplate = object
bs4.BeautifulSoup = object
bs4.NavigableString = str
bs4.Tag = object
dotenv.load_dotenv = lambda *args, **kwargs: None
sys.modules.setdefault("langchain_core", langchain_core)
sys.modules.setdefault("langchain_core.language_models", language_models)
sys.modules.setdefault("langchain_core.prompts", prompts)
sys.modules.setdefault("bs4", bs4)
sys.modules.setdefault("dotenv", dotenv)

import pipeline


def target(slug):
    return {"slug": slug}


def page(**overrides):
    base = {
        "sourceSlug": "ar",
        "sourceSlugs": ["ar"],
        "sourceRefs": [{"sourceSlug": "ar", "unitIds": ["u001-source"]}],
        "title": "Usage",
        "slug": "usage",
        "navTitle": "Usage",
        "description": "Reference usage for ar.",
        "category": "Prepositions",
        "section": "Conjugated prepositions",
        "sectionSlug": "conjugated",
        "topic": "ar",
        "topicSlug": "ar",
        "difficulty": "reference",
        "order": 10,
        "tags": ["prepositions"],
        "prerequisiteTopics": [],
        "relatedTopics": [],
        "canonicalExamples": [],
        "expectedLayout": "usage guide",
        "pagePurpose": "Explain the reference uses of ar.",
    }
    base.update(overrides)
    return base


class PipelineContractTests(unittest.TestCase):
    def test_route_uses_llm_metadata(self):
        self.assertEqual(
            pipeline.content_route_path(page()),
            "prepositions/conjugated/ar/usage",
        )

    def test_extract_json_object_ignores_trailing_extra_data(self):
        parsed = pipeline.extract_json_object('{"version": 2, "pages": []}\n{"extra": true}')

        self.assertEqual(parsed["version"], 2)

    def test_cached_content_plan_fragment_is_discarded(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "content-plan.txt"
            cache_path.write_text('{"version": 2, "pages": [{"tags"', encoding="utf-8")

            cached = pipeline.prompt._read_valid_cached_llm_output(
                cache_path,
                output_validator=pipeline.prompt._contains_valid_json_object,
            )

            self.assertIsNone(cached)
            self.assertFalse(cache_path.exists())

    def test_representative_routes(self):
        routes = [
            pipeline.content_route_path(page(sourceSlug="i", sourceSlugs=["i"], sourceRefs=[{"sourceSlug": "i", "unitIds": ["u001-source"]}], topic="i", topicSlug="i", slug="overview")),
            pipeline.content_route_path(page(sourceSlug="bi", sourceSlugs=["bi"], sourceRefs=[{"sourceSlug": "bi", "unitIds": ["u001-source"]}], category="Verbs", section="Irregular verbs", sectionSlug="irregular-verbs", topic="bí", topicSlug="bi", slug="forms")),
        ]

        self.assertEqual(routes, [
            "prepositions/conjugated/i/overview",
            "verbs/irregular-verbs/bi/forms",
        ])

    def test_route_normalisation_removes_redundant_category_words(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [
                page(category="Verbs", section="Irregular verbs", sectionSlug="irregular-verbs", topic="teigh", topicSlug="teigh", slug="overview"),
                page(category="Prepositions", section="Simple", sectionSlug="simple", topic="faoi", topicSlug="faoi", slug="overview"),
                page(category="Other", section="Pronouns", sectionSlug="pronouns", topic="Possessive particles", topicSlug="possessive-particles", slug="overview", tags=["pronouns"]),
            ],
        }

        pipeline.normalise_public_route_metadata(content_plan)

        self.assertEqual(
            [pipeline.content_route_path(planned_page) for planned_page in content_plan["pages"]],
            [
                "verbs/irregular/teigh/overview",
                "prepositions/conjugated/faoi/overview",
                "pronouns/possessive/overview",
            ],
        )

    def test_route_normalisation_repairs_planner_repetition(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [
                page(category="Nouns", section="Nouns and pronouns", sectionSlug="nouns-pronouns", topic="Pronouns", topicSlug="pronouns", slug="personal-pronouns", tags=["pronouns"]),
                page(category="Nouns", section="Nouns and pronouns", sectionSlug="nouns-pronouns", topic="Pronouns", topicSlug="pronouns", slug="possessive-pronouns", tags=["pronouns"]),
                page(category="Nouns", section="Nouns and pronouns", sectionSlug="nouns-pronouns", topic="Pronouns", topicSlug="pronouns", slug="other-pronouns", tags=["pronouns"]),
                page(category="Prepositions", section="", sectionSlug="", topic="", topicSlug="", slug="compound-prepositions"),
                page(category="Prepositions", section="", sectionSlug="", topic="", topicSlug="", slug="genitive-prepositions"),
                page(category="Prepositions", section="", sectionSlug="", topic="", topicSlug="", slug="unconjugated-prepositions"),
                page(category="Syntax", section="Sentence structure", sectionSlug="sentence-structure", topic="", topicSlug="", slug="basic-sentence-structure"),
            ],
        }

        pipeline.normalise_public_route_metadata(content_plan)

        self.assertEqual(
            [pipeline.content_route_path(planned_page) for planned_page in content_plan["pages"]],
            [
                "pronouns/personal",
                "pronouns/possessive",
                "pronouns/other",
                "prepositions/compound",
                "prepositions/genitive",
                "prepositions/unconjugated",
                "syntax/sentence-structure/basic",
            ],
        )

    def test_content_plan_rejects_duplicate_routes(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [page(), page(sourceSlug="ag", sourceSlugs=["ag"], sourceRefs=[{"sourceSlug": "ag", "unitIds": ["u001-source"]}])],
        }

        with self.assertRaisesRegex(ValueError, "duplicates route"):
            pipeline.validate_content_plan(content_plan, [target("ar"), target("ag")])

    def test_content_plan_rejects_legacy_route_segments(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [page(sectionSlug="verb1", sourceSlugs=["ar"])],
        }

        with self.assertRaisesRegex(ValueError, "legacy source segment"):
            pipeline.validate_content_plan(content_plan, [target("ar")])

    def test_content_plan_rejects_hash_like_route_segments(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [page(topicSlug="progressive-aspect-example-4ab05060")],
        }

        with self.assertRaisesRegex(ValueError, "hash-like segment"):
            pipeline.validate_content_plan(content_plan, [target("ar")])

    def test_content_plan_rejects_redundant_route_segments(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [page(category="Verbs", sectionSlug="irregular-verbs", topicSlug="teigh")],
        }

        with self.assertRaisesRegex(ValueError, "redundant segment"):
            pipeline.validate_content_plan(content_plan, [target("ar")])

    def test_source_coverage_requires_primary_page(self):
        content_plan = {
            "version": pipeline.CONTENT_PLAN_VERSION,
            "pages": [page(sourceSlug="ar", sourceSlugs=["ar"], sourceRefs=[{"sourceSlug": "ar", "unitIds": ["u001-source"]}])],
        }

        with self.assertRaisesRegex(ValueError, "does not cover source"):
            pipeline.validate_content_plan(content_plan, [target("ar"), target("ag")])

    def test_content_plan_rejects_missing_source_units(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            step_3_path = Path(temp_dir) / "satz1.md"
            step_3_path.write_text("# Clauses\n\nOverview.\n\n## Word order\n\nDetail.", encoding="utf-8")
            targets = [{"slug": "satz1", "step_3_path": str(step_3_path)}]
            units = pipeline.source_units_for_target(targets[0], include_content=False)
            content_plan = {
                "version": pipeline.CONTENT_PLAN_VERSION,
                "pages": [
                    page(
                        sourceSlug="satz1",
                        sourceSlugs=["satz1"],
                        sourceRefs=[{"sourceSlug": "satz1", "unitIds": [units[0]["unitId"]]}],
                    )
                ],
            }

            with self.assertRaisesRegex(ValueError, "does not cover source unit"):
                pipeline.validate_content_plan(content_plan, targets)

    def test_page_source_markdown_can_combine_multiple_sources(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "satz1.md"
            second_path = Path(temp_dir) / "satz2.md"
            first_path.write_text("# Clauses\n\nFirst source.", encoding="utf-8")
            second_path.write_text("# Word order\n\nSecond source.", encoding="utf-8")
            targets = [
                {"slug": "satz1", "step_3_path": str(first_path)},
                {"slug": "satz2", "step_3_path": str(second_path)},
            ]
            first_unit = pipeline.source_units_for_target(targets[0], include_content=False)[0]["unitId"]
            second_unit = pipeline.source_units_for_target(targets[1], include_content=False)[0]["unitId"]
            planned_page = page(
                sourceSlug="satz1",
                sourceSlugs=["satz1", "satz2"],
                sourceRefs=[
                    {"sourceSlug": "satz1", "unitIds": [first_unit]},
                    {"sourceSlug": "satz2", "unitIds": [second_unit]},
                ],
            )

            markdown = pipeline.page_source_markdown(planned_page, targets)

            self.assertIn("First source.", markdown)
            self.assertIn("Second source.", markdown)

    def test_source_coverage_counts_units_on_cross_source_page(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "satz1.md"
            second_path = Path(temp_dir) / "satz2.md"
            first_path.write_text("# Clauses\n\nFirst source.", encoding="utf-8")
            second_path.write_text("# Word order\n\nSecond source.", encoding="utf-8")
            targets = [
                {"slug": "satz1", "step_3_path": str(first_path)},
                {"slug": "satz2", "step_3_path": str(second_path)},
            ]
            first_unit = pipeline.source_units_for_target(targets[0], include_content=False)[0]["unitId"]
            second_unit = pipeline.source_units_for_target(targets[1], include_content=False)[0]["unitId"]
            content_plan = {
                "version": pipeline.CONTENT_PLAN_VERSION,
                "pages": [
                    page(
                        sourceSlug="satz1",
                        sourceSlugs=["satz1", "satz2"],
                        sourceRefs=[
                            {"sourceSlug": "satz1", "unitIds": [first_unit]},
                            {"sourceSlug": "satz2", "unitIds": [second_unit]},
                        ],
                    )
                ],
            }

            pipeline.validate_content_plan(content_plan, targets)

    def test_content_plan_repair_adds_missing_unit_pages(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            step_3_path = Path(temp_dir) / "verb1.md"
            step_3_path.write_text("# Overview\n\nOne.\n\n## Forms\n\nTwo.", encoding="utf-8")
            targets = [{"slug": "verb1", "step_3_path": str(step_3_path)}]
            first_unit = pipeline.source_units_for_target(targets[0], include_content=False)[0]["unitId"]
            content_plan = {
                "version": pipeline.CONTENT_PLAN_VERSION,
                "pages": [
                    page(
                        sourceSlug="verb1",
                        sourceSlugs=["verb1"],
                        sourceRefs=[{"sourceSlug": "verb1", "unitIds": [first_unit]}],
                    )
                ],
            }

            repaired = pipeline.repair_content_plan_coverage(content_plan, targets)

            pipeline.validate_content_plan(repaired, targets)
            self.assertGreater(len(repaired["pages"]), 1)
            self.assertFalse(any(
                pipeline.hash_like_route_segments(pipeline.content_route_segments(planned_page))
                for planned_page in repaired["pages"]
            ))

    def test_content_plan_repair_moves_unit_to_actual_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first_path = Path(temp_dir) / "clois.md"
            second_path = Path(temp_dir) / "cluin.md"
            first_path.write_text("# Clois\n\nOne.\n\n## Cluin\n\nTwo.", encoding="utf-8")
            second_path.write_text("# Other\n\nThree.", encoding="utf-8")
            targets = [
                {"slug": "clois", "step_3_path": str(first_path)},
                {"slug": "cluin", "step_3_path": str(second_path)},
            ]
            misplaced_unit = pipeline.source_units_for_target(targets[0], include_content=False)[1]["unitId"]
            content_plan = {
                "version": pipeline.CONTENT_PLAN_VERSION,
                "pages": [
                    page(
                        sourceSlug="cluin",
                        sourceSlugs=["cluin"],
                        sourceRefs=[{"sourceSlug": "cluin", "unitIds": [misplaced_unit]}],
                    )
                ],
            }

            repaired = pipeline.repair_content_plan_coverage(content_plan, targets)

            self.assertEqual(repaired["pages"][0]["sourceRefs"][0]["sourceSlug"], "clois")
            pipeline.validate_content_plan(repaired, targets)

    def test_mixed_italic_code_is_rejected(self):
        content = """---
title: "Usage"
slug: "usage"
navTitle: "Usage"
description: "Reference usage."
category: "Prepositions"
difficulty: "reference"
tags: []
prerequisiteTopics: []
relatedTopics: []
canonicalExamples: []
---

- *`D'ól mé uisce.`* - I drank water.
"""
        errors, _warnings = pipeline.lint_mdx_content("usage.mdx", content)

        self.assertTrue(any("mixed italic/code" in error for error in errors))

    def test_compact_paradigm_warning(self):
        content = """---
title: "ionsar"
slug: "overview"
navTitle: "Overview"
description: "Reference overview."
category: "Prepositions"
difficulty: "reference"
tags: []
prerequisiteTopics: []
relatedTopics: []
canonicalExamples: []
---

## Prepositional Pronouns

### `ionsorm`

To me.
"""
        _errors, warnings = pipeline.lint_mdx_content("ionsar.mdx", content)

        self.assertTrue(any("compact table" in warning for warning in warnings))

    def test_hash_like_frontmatter_route_is_rejected(self):
        content = """---
title: "Additional notes"
slug: "additional-notes"
navTitle: "Additional notes"
description: "Reference notes."
category: "Other"
sectionSlug: "coverage-review"
topicSlug: "echo-forms-092c79e8"
difficulty: "reference"
tags: []
prerequisiteTopics: []
relatedTopics: []
canonicalExamples: []
---

Body.
"""
        errors, _warnings = pipeline.lint_mdx_content("notes.mdx", content)

        self.assertTrue(any("hash-like segment" in error for error in errors))

    def test_enrichment_changes_when_content_plan_hash_changes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            original_step_4_dir = pipeline.STEP_4_DIR
            original_content_plan_path = pipeline.CONTENT_PLAN_PATH
            try:
                pipeline.STEP_4_DIR = str(temp_path / "step_4")
                pipeline.CONTENT_PLAN_PATH = str(temp_path / "content_plan.json")
                Path(pipeline.STEP_4_DIR).mkdir()
                output_path = Path(pipeline.STEP_4_DIR) / "ar.mdx"
                output_path.write_text("content", encoding="utf-8")
                step_3_path = temp_path / "ar.md"
                step_3_path.write_text("translation", encoding="utf-8")
                Path(pipeline.CONTENT_PLAN_PATH).write_text('{"version": 1}', encoding="utf-8")

                record = {
                    "enrichment": {
                        "input_hash": pipeline.hash_file(str(step_3_path)),
                        "content_plan_hash": "old-plan-hash",
                        "output_paths": ["ar.mdx"],
                        "output_hashes": {"ar.mdx": pipeline.hash_file(str(output_path))},
                        "prompt_hash": "prompt",
                        "prompt_version": "v1",
                        "model_type": "ideator",
                        "model_id": "model",
                        "temperature": 0.2,
                    }
                }
                stage_config = {"model_type": "ideator", "model_id": "model", "temperature": 0.2}
                stage_prompt = {"hash": "prompt", "version": "v1"}

                self.assertTrue(
                    pipeline.enrichment_changed(
                        record,
                        {"slug": "ar", "step_3_path": str(step_3_path)},
                        stage_config,
                        stage_prompt,
                    )
                )
            finally:
                pipeline.STEP_4_DIR = original_step_4_dir
                pipeline.CONTENT_PLAN_PATH = original_content_plan_path

    def test_force_content_plan_does_not_force_parse_or_translate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            html_path = temp_path / "ar.html"
            step_1_path = temp_path / "step_1" / "ar.md"
            step_3_path = temp_path / "step_3" / "ar.md"
            html_path.write_text("<h1>Ar</h1>", encoding="utf-8")
            step_1_path.parent.mkdir()
            step_3_path.parent.mkdir()
            step_1_path.write_text("# Ar", encoding="utf-8")
            step_3_path.write_text("# Ar", encoding="utf-8")

            targets = [{
                "slug": "ar",
                "html_path": str(html_path),
                "step_1_path": str(step_1_path),
                "step_3_path": str(step_3_path),
                "source_html_hash": pipeline.hash_file(str(html_path)),
            }]
            manifest = {"files": {"ar": {"source_html_hash": pipeline.hash_file(str(html_path))}}}
            configs = {
                "translator": {"model_type": "general", "model_id": "model", "temperature": 0.1},
                "planner": {"model_type": "ideator", "model_id": "model", "temperature": 0.2},
                "enricher": {"model_type": "ideator", "model_id": "model", "temperature": 0.25},
            }
            prompts = {
                "translation": {"hash": "translation", "version": "translation-v1"},
                "content_plan": {"hash": "content-plan", "version": "content-plan-v1"},
                "enrichment": {"hash": "enrichment", "version": "enrichment-v4"},
            }

            previous = os.environ.get("PIPELINE_FORCE_CONTENT_PLAN")
            try:
                os.environ["PIPELINE_FORCE_CONTENT_PLAN"] = "1"
                plan = pipeline.build_pipeline_plan(targets, manifest, configs, prompts)
            finally:
                if previous is None:
                    os.environ.pop("PIPELINE_FORCE_CONTENT_PLAN", None)
                else:
                    os.environ["PIPELINE_FORCE_CONTENT_PLAN"] = previous

            self.assertEqual(plan["parse"], [])
            self.assertEqual(plan["translate"], [])
            self.assertTrue(plan["content_plan"])

    def test_llm_timeouts_are_retryable(self):
        class APITimeoutError(Exception):
            pass

        self.assertTrue(pipeline.prompt._is_retryable_llm_error(APITimeoutError("Request timed out.")))

    def test_llm_timeout_seconds_can_be_configured(self):
        previous = os.environ.get("PIPELINE_LLM_TIMEOUT_SECONDS")
        try:
            os.environ["PIPELINE_LLM_TIMEOUT_SECONDS"] = "900"
            self.assertEqual(pipeline.llm_timeout_seconds(), 900.0)
        finally:
            if previous is None:
                os.environ.pop("PIPELINE_LLM_TIMEOUT_SECONDS", None)
            else:
                os.environ["PIPELINE_LLM_TIMEOUT_SECONDS"] = previous

    def test_system_prompt_json_examples_are_literal_text(self):
        escaped = pipeline.prompt._literal_prompt_text('{"version": 1}')

        self.assertEqual(escaped, '{{"version": 1}}')

    def test_chunked_llm_outputs_are_cached(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            calls = []
            original_invoke_llm = pipeline.prompt._invoke_llm
            previous_chunk_size = os.environ.get("PIPELINE_LLM_CHUNK_MAX_CHARS")

            def fake_invoke_llm(_llm, _system_prompt, content, cache_path=None):
                cached = pipeline.prompt._read_cached_llm_output(cache_path)
                if cached is not None:
                    return cached

                calls.append(content)
                output = f"cached-output-{len(calls)}"
                pipeline.prompt._write_cached_llm_output(cache_path, output)
                return output

            try:
                os.environ["PIPELINE_LLM_CHUNK_MAX_CHARS"] = "30"
                pipeline.prompt._invoke_llm = fake_invoke_llm
                markdown = "# First\n\nThis first section is long enough.\n\n# Second\n\nThis second section is long enough."

                first = pipeline.prompt._invoke_chunked_llm(
                    None,
                    "system",
                    markdown,
                    "translation",
                    cache_dir=temp_dir,
                    cache_namespace="ar-quality",
                )
                calls_after_first_run = len(calls)
                second = pipeline.prompt._invoke_chunked_llm(
                    None,
                    "system",
                    markdown,
                    "translation",
                    cache_dir=temp_dir,
                    cache_namespace="ar-quality",
                )
            finally:
                pipeline.prompt._invoke_llm = original_invoke_llm
                if previous_chunk_size is None:
                    os.environ.pop("PIPELINE_LLM_CHUNK_MAX_CHARS", None)
                else:
                    os.environ["PIPELINE_LLM_CHUNK_MAX_CHARS"] = previous_chunk_size

            self.assertEqual(first, second)
            self.assertGreater(calls_after_first_run, 1)
            self.assertEqual(len(calls), calls_after_first_run)


if __name__ == "__main__":
    unittest.main()
