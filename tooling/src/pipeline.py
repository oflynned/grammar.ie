import os

from langchain_core.language_models import BaseChatModel

import prompt
import verification

from dotenv import load_dotenv
from langchain_mistralai import ChatMistralAI
from langchain_google_genai import ChatGoogleGenerativeAI
from token_manager import TokenManager

load_dotenv()

BASE_DIR = "./assets/test"
INPUT_DIR = "./assets/test_input"
OUTPUT_ROOT = "./assets/output"


def save_file(content: str, directory: str, filename: str):
    target_dir = os.path.join(directory)
    os.makedirs(target_dir, exist_ok=True)
    output_path = os.path.join(target_dir, filename)

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Saved to {directory}/{filename}")
    except Exception as e:
        print(f"Error saving {filename}: {e}")


def get_mistral_llm(model_type: str, temperature=0):
    models = {
        "coding": "devstral-medium-latest",
        "general": "mistral-medium-latest",
        "ideator": "mistral-large-latest",
    }

    if model_type not in models:
        raise ValueError(f"Invalid model type: {model_type}. Must be one of {list(models.keys())}")

    print(f"🔌 Connected to {model_type.upper()} ({models[model_type]})")

    return ChatMistralAI(
        model=models[model_type],
        api_key=os.getenv("MISTRAL_API_KEY"),
        temperature=temperature,
        top_p=1,
    )


def get_gemini_llm(model_type, temperature=0.1):
    models = {
        "coding": "gemini-2.5-flash",
        "general": "gemini-2.5-pro",
        "ideator": "gemini-2.5-pro",
    }

    if model_type not in models:
        raise ValueError(f"Invalid model type: {model_type}. Must be one of {list(models.keys())}")

    print(f"🔌 Connected to {model_type.upper()} ({models[model_type]})")

    return ChatGoogleGenerativeAI(
        model=models[model_type],
        api_key=os.getenv("GEMINI_API_KEY"),
        temperature=temperature,
    )


def parse_from_html(llm: BaseChatModel):
    directory = f"{BASE_DIR}/input"
    output_directory = f"{BASE_DIR}/output/step_1"

    existing_output_file_names = [f.replace(".md", ".html") for f in os.listdir(output_directory) if f.endswith('.md')]
    file_names = [f for f in os.listdir(directory) if f.endswith('.html') and f not in existing_output_file_names]

    print(existing_output_file_names)
    print(file_names)

    for file_name in file_names:
        print(f"📄 Parsing: {file_name}")

        file_slug = file_name.replace('.html', '')
        file_path = os.path.join(directory, file_name)

        with open(file_path, 'r', encoding='iso-8859-1') as f:
            raw_html_content = f.read()

        content = prompt.parse_content_to_markdown(llm, raw_html_content)
        save_file(content, output_directory, f"{file_slug}.md")


def tokenise(llm: BaseChatModel, _token_manager: TokenManager):
    directory = f"{BASE_DIR}/output/step_1"
    file_names = [f for f in os.listdir(directory) if f.endswith('.md')]

    for file_name in file_names:
        print(f"📄 Tokenising: {file_name}")

        file_path = os.path.join(directory, file_name)

        with open(file_path, 'r') as f:
            markdown_content = f.read()

        # wrap it in <ga> tags
        content = prompt.tokenise_irish_content(llm, markdown_content)

        # replace the tags with __IRISH_REF__
#         tokenised_content = token_manager.tokenise(content)
        save_file(content, f"{BASE_DIR}/output/step_2", file_name)


def translate(llm: BaseChatModel):
    directory = f"{BASE_DIR}/output/step_2"
    file_names = [f for f in os.listdir(directory) if f.endswith('.md')]

    for file_name in file_names:
        print(f"📄 Translating: {file_name}")

        file_path = os.path.join(directory, file_name)

        with open(file_path, 'r') as f:
            markdown_content = f.read()

        content = prompt.translate_to_english(llm, markdown_content)
        save_file(content, f"{BASE_DIR}/output/step_3", file_name)


def enrich(llm: BaseChatModel, _token_manager: TokenManager):
    directory = f"{BASE_DIR}/output/step_3"
    file_names = [f for f in os.listdir(directory) if f.endswith('.md')]

    for file_name in file_names:
        print(f"📄 Enriching: {file_name}")

        file_slug = file_name.replace('.md', '')
        file_path = os.path.join(directory, file_name)

        with open(file_path, 'r') as f:
            markdown_content = f.read()

        content = prompt.improve_ux(llm, markdown_content)
        # restored_content = token_manager.restore(content)
        save_file(content, f"{BASE_DIR}/output/step_4", f"{file_slug}.mdx")


if __name__ == "__main__":
    print(f"🚀 Connecting to LLMs...")

    llm_parser = get_gemini_llm("coding")
    llm_translator = get_gemini_llm("general", 0.2)
    llm_enricher = get_gemini_llm("ideator", 0.5)

    parse_from_html(llm_parser)

    token_manager = TokenManager()
    tokenise(llm_parser, token_manager)

    translate(llm_translator)
    enrich(llm_enricher, token_manager)

    print("\n✅ All jobs finished.")
