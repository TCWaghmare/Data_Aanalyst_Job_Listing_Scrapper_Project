"""
Abstract Base Adapter interface for modular job scrapers.
"""

from abc import ABC, abstractmethod
from typing import List
from scraper.models import Job

class BaseAdapter(ABC):
    def __init__(self, platform_id: str, platform_name: str):
        self.platform_id = platform_id
        self.platform_name = platform_name

    @abstractmethod
    def scrape(
        self,
        roles: List[str] = None,
        limit: int = 50,
        cities: List[str] = None,
        work_modes: List[str] = None,
        **kwargs
    ) -> List[Job]:
        """
        Scrapes job listings for the given roles up to the specified limit.
        Optionally filters/prioritizes by cities and work_modes (e.g. On-Site, Hybrid).
        Returns a list of normalized Job objects.
        """
        pass

