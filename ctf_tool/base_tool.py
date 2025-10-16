# -*- coding: utf-8 -*-
# Base class for all tools
from abc import ABC, abstractmethod
from typing import Dict, Tuple


class BaseTool(ABC):
    @abstractmethod
    def execute(self, *args, **kwargs) -> Tuple[str, str]:
        """Run the tool and return stdout/stderr."""
        pass

    @property
    @abstractmethod
    def function_config(self) -> Dict:
        """Return the function-call configuration exposed to the agent."""
        pass
