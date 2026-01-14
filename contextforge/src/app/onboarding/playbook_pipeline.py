from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import PlaybookExtraction


class PlaybookPipeline(OnboardingPipeline[PlaybookExtraction]):
    node_type = "PLAYBOOK"
    extraction_model = PlaybookExtraction
    prompt_name = "onboarding_playbook_extraction"

    def to_node_content(self, extraction: PlaybookExtraction) -> dict:
        return {
            "description": extraction.description,
            "prerequisites": extraction.prerequisites,
            "steps": [
                {
                    "order": step.order,
                    "action": step.action,
                    "details": step.details,
                }
                for step in extraction.steps
            ],
        }

    def get_title(self, extraction: PlaybookExtraction) -> str:
        return extraction.title

    def get_tags(self, extraction: PlaybookExtraction) -> list[str]:
        return extraction.tags
