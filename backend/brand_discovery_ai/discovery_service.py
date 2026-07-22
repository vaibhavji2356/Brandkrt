"""Orchestration for mock-only multi-platform discovery; deliberately DB-free."""

import asyncio

from .discovery_schemas import DiscoveryCriteria, DiscoveryPreviewResponse, EntityType
from .normalization import deduplicate_profiles
from .ranking import rank_profiles
from .source_adapters import SourceProvider, build_mock_adapters


class MultiPlatformDiscoveryService:
    def __init__(self, adapters: dict | None = None):
        self.adapters = adapters or build_mock_adapters()

    async def preview(self, criteria: DiscoveryCriteria) -> DiscoveryPreviewResponse:
        selected = [self.adapters[platform] for platform in criteria.platforms]
        operations = []
        for adapter in selected:
            if criteria.entity_type in {EntityType.CREATOR, EntityType.BOTH}:
                operations.append(adapter.search_creators(criteria))
            if criteria.entity_type in {EntityType.BRAND, EntityType.BOTH}:
                operations.append(adapter.search_brands(criteria))
        batches = await asyncio.gather(*operations)
        profiles = deduplicate_profiles([profile for batch in batches for profile in batch])
        ranked = rank_profiles(profiles, criteria)[:criteria.result_limit]
        warnings = ["Mock-only preview. All profiles are synthetic and must be verified before use."]
        unsupported = [adapter.platform.value for adapter in selected if criteria.entity_type == EntityType.BRAND and not adapter.capabilities.brand_discovery]
        if unsupported:
            warnings.append(f"Brand discovery is unsupported by mock capability policy for: {', '.join(unsupported)}.")
        return DiscoveryPreviewResponse(results=ranked, count=len(ranked), sources=sorted({item.profile.source for item in ranked}), warnings=warnings)
