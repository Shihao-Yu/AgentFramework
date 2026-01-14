from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import EntityExtraction


class EntityPipeline(OnboardingPipeline[EntityExtraction]):
    node_type = "ENTITY"
    extraction_model = EntityExtraction
    prompt_name = "onboarding_entity_extraction"

    def to_node_content(self, extraction: EntityExtraction) -> dict:
        return {
            "name": extraction.name,
            "entity_type": extraction.entity_type,
            "attributes": extraction.attributes,
        }

    def get_title(self, extraction: EntityExtraction) -> str:
        return extraction.name

    def get_tags(self, extraction: EntityExtraction) -> list[str]:
        tags = extraction.tags.copy()
        entity_type_tag = extraction.entity_type.lower().replace(" ", "-")
        if entity_type_tag not in tags:
            tags.append(entity_type_tag)
        return tags
