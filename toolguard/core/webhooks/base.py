from abc import ABC, abstractmethod
from typing import Any, Dict

class WebhookProvider(ABC):
    """
    Base class for sending outbound context regarding an operation
    that has been paused for human approval.
    """
    
    @abstractmethod
    def send_approval_request(self, 
                              tool_name: str, 
                              arguments: Dict[str, Any], 
                              grant_id: str, 
                              timeout: int) -> bool:
        """
        Deliver the approval notification to the external entity.
        Returns True if sent successfully, False otherwise.
        """
        pass
