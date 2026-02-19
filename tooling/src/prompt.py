import html
import re
from bs4 import BeautifulSoup
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
import sys

sys.setrecursionlimit(10_000)


def _preprocess_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    page_title = None
    if soup.title:
        page_title = soup.title.get_text().strip()

    for tag in soup(["script", "style", "link", "meta"]):
        tag.decompose()

    for table in soup.find_all("table"):
        if "Gramadach" in table.get_text():
            table.decompose()

    footer_link = soup.find('a', href=re.compile(r'index\.html'))
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


def parse_content_to_markdown(llm: BaseChatModel, raw_html_content: str):
    escaped_html_content = html.unescape(raw_html_content)
    clean_html, detected_page_title = _preprocess_html(escaped_html_content)

    system_prompt = """
        Role: You are a linguistic data engineer. Your task is to convert legacy German HTML into structured German Markdown.

        ### STRUCTURAL RULES
        Layout & Cleanup: - Convert HTML headings to Markdown.
        Strip all "Navigation", "Home", and "Copyright" footers.
        Remove all hyperlinks.
        Text Normalization: Legacy HTML often uses hard line breaks (<br> or \n) in the middle of sentences. You must join these split lines so that each bullet point or paragraph is a single, continuous line of text.

        Table Rules:
        - No Spacers: The table must start immediately with the header row. No empty rows or &nbsp; rows above it.
        - Header: The first cell of the header must be empty. Format: | | **Header 1** | **Header 2** |
        - Separator: The separator line | --- | --- | --- | must follow the header row immediately.

        ### OUTPUT CONSTRAINTS
        No Code Blocks: Do not use ```markdown or ``` backticks.
        Start Immediately: Your response must start with the very first character of the content (e.g., the first # of the title).
        Raw Text: Provide only the raw Markdown text. No introductory remarks or "Here is the conversion" text.
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{content}")
    ])

    return (prompt | llm).invoke({"content": clean_html}).text()


def translate_to_english(llm: BaseChatModel, markdown: str):
    system_prompt = """
        Role: You are a Senior Academic Linguist specializing in Celtic Studies and Morphosyntax.
        Context: You are translating a in-depth content in relation to Irish grammar from German to English. The target audience is academic linguists and advanced students.

        ### INSTRUCTIONS
        Translation: Translate the German prose into English, using standard linguistic terminology (e.g., Dative, Lenition, Eclipsis, Agent, Progressive Aspect). Use appropriate word casing.
        Preservation: Do not touch any __IRISH_*__ placeholders or <ga> tag references. 
        Format Integrity: Do not alter the Markdown structure. If a table cell is empty, leave it empty.
        No Wrappers: Provide the raw Markdown text only. Do not use code blocks (```) or any introductory text.
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{content}")
    ])

    return (prompt | llm).invoke({"content": markdown}).text()


def tokenise_irish_content(llm: BaseChatModel, markdown: str):
    system_prompt = """
        Role: You are a Senior Linguistic Engineer. Your task is to tag all Irish content with <ga> tags and to keep the Irish text within them exactly as they appear.
        Context: You will tag all possible Irish content, and exclude any English/German content from the <ga> tags.

        ### INSTRUCTIONS
        Format Integrity: Do not alter the Markdown structure. Parse the content.
        No Wrappers: Provide the raw Markdown text only. Do not use code blocks (```) or any introductory text.
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{content}")
    ])

    return (prompt | llm).invoke({"content": markdown}).text()


def improve_ux(llm: BaseChatModel, english_md: str):
    system_prompt = """
        Role: You are a Senior Technical Content Engineer. Your task is a high-fidelity structural transformation of linguistic data into MDX. You do not summarize; you re-architect.
        You process information catered towards Irish learners, preferring simplicity over difficult linguistic topics.
        You provide rigour in accordance with all the source material, but ensure it can be digested by readers for a good UX.

        ### METADATA
        Ensure all text provided to any props (excluding children) of either component is plain text. Do not include markdown styling. Ensure the top of every file starts with this frontmatter block at the top of the MDX file:

        ---

        title: "<The Irish word or concept [in English] being discussed (e.g., "De", "Bí", "Eclipsis")>"
        description: "<A 1-2 sentence English summary. Define the core function and list primary use cases (e.g., "Primarily used to indicate possession and state...").>"
        category: "<The broad grammatical class in English (e.g., "Prepositions", "Verbs", "Nouns", "Adjectives", "Initial Mutations").>"
        tags: [<3–5 English lowercase strings representing the grammar class, operation, and case (e.g., ["preposition", "conjugated", "dative"])>]

        ---

        ### PAGE STRUCTURE
        Increase content complexity as the user traverses the page.
        Background, tables and any "must know" reference grammar should appear at the start. In-depth usage can appear under this, and dialectal/advanced info should appear at the bottom.
        The sections should roughly follow the following format:
            - Overview
            - Historical notes
            - Case
            - Question forms
            - Conjugation tables
            - Mutation formulae with examples
            - Usage and functions, divided into different sections based on domain

        ### MANDATORY FORMATTING RULES
        Preservation: Do not touch any __IRISH_*__ placeholders or <ga> tag references. 
        Text styling: Relevant <ga>text</ga> instance must be converted to backticks if occurring isolated within a sentence. Examples should be italicised and not contain backticks for clarity. Prefer plain text over styled Markdown text. No em-dashes. Do not sound like an LLM.
        Internal text styling: Within the backticks, use only plain text. Content wrapped with backticks should not have any markdown formatting passed in, ie `text` and not `*text*`.
        No Code Wrappers: Your output must begin with --- (frontmatter). Do not use triple backticks (` ` `) to wrap your response.
        MDX Components: You must use <MutationCard /> for mutations. Ensure that no English examples are provided, focus only on Irish formulae (eg `ag + an + fear` -> `ag an bhfear`)

        ### COMPONENT PROPS
        <MutationCard />: Requires title, before, after, and rule. This component does not have a children prop. Ensure before is a logic-based derivation (e.g., ag + fear). No prop accepts markdown text formatting.

        If using a mdx component, ensure it is imported at the top of file, below the metadata, like so:
        import MutationCard from '../../components/MutationCard.astro';

        Ensure all text provided to any props (excluding children) of either component is plain text. Do not include markdown styling. If an import is not used, remove it.

        ### ARCHITECTURAL SYNTHESIS
        Do not reproduce the 1-12 list. You must categorize that data into H2/H3 structures. No titles should be enumerated nor should they contain any text formatting, including backticks. The following are creative examples:

        ## Overview (Forms table, Interrogatives)
        ## Core Functions (Spatial, Temporal, Possession, Continuous Aspect)
        ## Agency & Cause (Agent marking, Cause of state, Opinion)
        ## Social & Dialectal (Partitives, Substitutes, Dialectal variations)

        ### MICRO-COPY
        Use a Markdown table for idiomatic verb formulas: Concept | Formula | Example | Translation (Literal).
        Keep descriptions under 2 lines. Use bullet points for examples.
        Use British spelling for any English language text.
        Ensure that any references to German are either removed or changed to appropriate relevance to English.
    """

    # We inject the title/slug into the prompt instructions
    final_prompt = system_prompt.format()

    prompt = ChatPromptTemplate.from_messages([
        ("system", final_prompt),
        ("human", "{content}")
    ])

    return (prompt | llm).invoke({"content": english_md}).text()
