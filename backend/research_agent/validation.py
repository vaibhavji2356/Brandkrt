"""Fail-closed research task validation."""

import re

from brand_discovery_ai.discovery_schemas import Platform
from brand_discovery_ai.source_adapters import CAPABILITY_REGISTRY

from .errors import TaskValidationError
from .metrics import research_metrics
from .models import ResearchTask, TaskType


PLATFORMS = {item.value for item in Platform}
NETWORK_ONLY_PLATFORMS = {"website", "google"}
UNSAFE_QUERY = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]|(?:javascript|data|file):|(?:api[_-]?key|authorization|password)\s*[:=]", re.IGNORECASE)


class TaskValidator:
    def validate_all(self, tasks: list[ResearchTask]) -> list[ResearchTask]:
        valid, fingerprints = [], set()
        for task in tasks:
            try:
                self.validate(task)
                fingerprint = self.fingerprint(task)
                if fingerprint in fingerprints:
                    raise TaskValidationError("Duplicate research task.")
                fingerprints.add(fingerprint)
                valid.append(task)
            except TaskValidationError:
                research_metrics.add("validation_failures")
                raise
        return valid

    def validate(self, task: ResearchTask) -> None:
        if not task.query.strip():
            raise TaskValidationError("Research task query is empty.")
        if UNSAFE_QUERY.search(task.query):
            raise TaskValidationError("Research task query contains unsafe content.")
        if task.platform and task.platform not in PLATFORMS | NETWORK_ONLY_PLATFORMS:
            raise TaskValidationError("Research task platform is invalid.")
        if task.type in {
            TaskType.CREATOR_SEARCH, TaskType.BRAND_SEARCH, TaskType.PROFILE_LOOKUP,
            TaskType.KEYWORD_LOOKUP, TaskType.PLATFORM_LOOKUP,
        } and not task.platform:
            raise TaskValidationError("Research task requires a platform.")
        if task.platform in NETWORK_ONLY_PLATFORMS:
            raise TaskValidationError("Capability is defined but unavailable in mock-only mode.")
        if task.platform in PLATFORMS:
            capabilities = CAPABILITY_REGISTRY[Platform(task.platform)]
            if task.type == TaskType.BRAND_SEARCH and not capabilities.brand_discovery:
                raise TaskValidationError("Provider does not support brand discovery.")
            if task.type == TaskType.CREATOR_SEARCH and not capabilities.creator_discovery:
                raise TaskValidationError("Provider does not support creator discovery.")
            if task.type == TaskType.KEYWORD_LOOKUP and not capabilities.keyword_search:
                raise TaskValidationError("Provider does not support keyword lookup.")

    @staticmethod
    def fingerprint(task: ResearchTask) -> tuple:
        return task.type, task.platform, task.entity_type, task.query.casefold().strip()
