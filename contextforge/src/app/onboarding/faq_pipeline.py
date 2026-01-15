from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import FAQExtraction


class FAQPipeline(OnboardingPipeline[FAQExtraction]):
    node_type = "FAQ"
    extraction_model = FAQExtraction
    prompt_name = "onboarding_faq_extraction"

    def to_node_content(self, extraction: FAQExtraction) -> dict:
        return {
            "answer": extraction.answer,
        }

    def get_title(self, extraction: FAQExtraction) -> str:
        return extraction.question

    def get_tags(self, extraction: FAQExtraction) -> list[str]:
        return extraction.tags
