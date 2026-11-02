"""
Platform Directory Registry and URL builder for all 147 sources.
"""

import json
import os
import urllib.parse
from typing import Dict, List, Optional
from scraper.models import Platform

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PLATFORMS_FILE = os.path.join(DATA_DIR, "platforms.json")

class PlatformRegistry:
    def __init__(self, filepath: str = PLATFORMS_FILE):
        self.filepath = filepath
        self._platforms: Dict[str, Platform] = {}
        self.load()

    def load(self):
        if not os.path.exists(self.filepath):
            return
        with open(self.filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
            for item in raw:
                p = Platform(**item)
                self._platforms[p.id] = p

    def get_all(self) -> List[Platform]:
        return list(self._platforms.values())

    def get_by_id(self, platform_id: str) -> Optional[Platform]:
        return self._platforms.get(platform_id)

    def get_active_adapters(self) -> List[Platform]:
        return [p for p in self._platforms.values() if p.has_adapter]

    def build_search_url(self, platform_id: str, role_title: str) -> str:
        """
        Builds a direct search URL for a given role on this platform.
        """
        platform = self.get_by_id(platform_id)
        if not platform:
            return ""

        encoded = urllib.parse.quote_plus(role_title)
        slug = role_title.lower().replace(" ", "-").replace("/", "-")

        template = platform.search_url_template
        if not template:
            return platform.website

        return template.replace("{role_encoded}", encoded).replace("{role_slug}", slug)

