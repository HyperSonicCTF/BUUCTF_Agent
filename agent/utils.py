import litellm
import re
import json
from config import Config


def fix_json_with_llm(json_str: str, err_content: str) -> str:
    """
    Repair malformed JSON by asking the configured LLM to rewrite it.
    :param json_str: The malformed JSON string.
    :param err_content: The parsing error message.
    :return: A corrected JSON string.
    """
    config: dict = Config.load_config()
    litellm.enable_json_schema_validation = True
    prompt = (
        "The following string is invalid JSON. Repair it so that it becomes valid JSON.\n"
        "Return only the corrected JSON—do not add any extra narration.\n"
        "Preserve every original key and value without altering their meaning.\n\n"
        f"Malformed JSON: {json_str}\n"
        f"Error message: {err_content}"
    )
    llm_config = config["llm"]["pre_processor"]

    while True:
        response = litellm.completion(
            model=llm_config["model"],
            api_key=llm_config["api_key"],
            api_base=llm_config["api_base"],
            messages=[{"role": "user", "content": prompt}],
        )
        fixed_json = response.choices[0].message.content
        try:
            json.loads(fixed_json)
            return fixed_json
        except:
            continue


def optimize_text(text: str) -> str:
    # Collapse runs of two or more spaces to a temporary marker
    text = re.sub(r" {2,}", "\x00", text)  # \x00 is unlikely to appear in content
    # Restore the marker to a single space
    text = text.replace("\x00", " ")
    text = re.sub(r"\n+", "\n", text)
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines)
