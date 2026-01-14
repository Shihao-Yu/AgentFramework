from app.onboarding.base import OnboardingPipeline
from app.onboarding.models import FeaturePermissionExtraction


class FeaturePermissionPipeline(OnboardingPipeline[FeaturePermissionExtraction]):
    node_type = "FEATURE_PERMISSION"
    extraction_model = FeaturePermissionExtraction
    prompt_name = "onboarding_feature_permission_extraction"

    def to_node_content(self, extraction: FeaturePermissionExtraction) -> dict:
        return {
            "feature": extraction.feature,
            "rules": [
                {
                    "role": rule.role,
                    "action": rule.action,
                    "condition": rule.condition,
                }
                for rule in extraction.rules
            ],
            "conditions": extraction.conditions,
        }

    def get_title(self, extraction: FeaturePermissionExtraction) -> str:
        return f"{extraction.feature} Permissions"

    def get_tags(self, extraction: FeaturePermissionExtraction) -> list[str]:
        return extraction.tags
