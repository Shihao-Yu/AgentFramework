from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import ConceptExtraction


class ConceptPipeline(OnboardingPipeline[ConceptExtraction]):
    node_type = "CONCEPT"
    extraction_model = ConceptExtraction
    prompt_name = "onboarding_concept_extraction"

    def to_node_content(self, extraction: ConceptExtraction) -> dict:
        return {
            "term": extraction.term,
            "definition": extraction.definition,
            "aliases": extraction.aliases,
            "examples": extraction.examples,
        }

    def get_title(self, extraction: ConceptExtraction) -> str:
        return extraction.term

    def get_tags(self, extraction: ConceptExtraction) -> list[str]:
        return extraction.tags
