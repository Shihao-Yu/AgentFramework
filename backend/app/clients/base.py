"""
Base client interface.
"""

from abc import ABC, abstractmethod


class BaseClient(ABC):
    """
    Base class for all external service clients.
    
    All clients should implement health_check for monitoring.
    """
    
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the client is healthy and ready.
        
        Returns:
            True if healthy, False otherwise
        """
        pass
