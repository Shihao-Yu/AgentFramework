from pathlib import Path
from typing import Optional
import json

from app.clients.langfuse_client import PromptConfig

PROMPTS_DIR = Path(__file__).parent


def load_prompt_config(prompt_name: str) -> Optional[PromptConfig]:
    config_path = PROMPTS_DIR / f"{prompt_name}.json"
    if not config_path.exists():
        return None
    
    with open(config_path) as f:
        data = json.load(f)
    
    return PromptConfig(
        model=data.get("config", {}).get("model", "gpt-4o-mini"),
        context_window=data.get("config", {}).get("context_window", 128000),
        max_output_tokens=data.get("config", {}).get("max_output_tokens", 4096),
        temperature=data.get("config", {}).get("temperature", 0.0),
    )


def load_prompt_template(prompt_name: str) -> Optional[str]:
    config_path = PROMPTS_DIR / f"{prompt_name}.json"
    if not config_path.exists():
        return None
    
    with open(config_path) as f:
        data = json.load(f)
    
    return data.get("prompt")


def list_prompts() -> list[str]:
    return [p.stem for p in PROMPTS_DIR.glob("*.json")]
