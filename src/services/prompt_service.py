from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"


class PromptService:
    def list_prompts(self) -> list[str]:
        return sorted(path.stem for path in PROMPT_DIR.glob("*.md"))

    def get(self, name: str) -> str:
        path = PROMPT_DIR / f"{name}.md"
        if not path.exists():
            raise KeyError(f"prompt not found: {name}")
        return path.read_text(encoding="utf-8")


prompt_service = PromptService()
