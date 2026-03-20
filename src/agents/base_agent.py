from abc import ABC, abstractmethod
from typing import Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class AgentType(Enum):
    DEVOPS = "devops"
    CODE_QUALITY = "code_quality"
    SECURITY = "security"
    PERFORMANCE = "performance"
    TECH_DEBT = "tech_debt"
    TESTS = "tests"
    STYLE = "style"
    ARCHITECTURE = "architecture"
    DOCS = "docs"
    MASTER = "master"
    SPECIALIST = "specialist"


class AgentCapability(Enum):
    READ_CODE = "read_code"
    WRITE_CODE = "write_code"
    EXECUTE_COMMAND = "execute_command"
    GITHUB_API = "github_api"
    FILE_SYSTEM = "file_system"
    USER_INTERACTION = "user_interaction"
    CODE_ANALYSIS = "code_analysis"
    SECURITY_SCAN = "security_scan"


@dataclass
class AgentResponse:
    success: bool
    message: str
    data: Optional[dict[str, Any]] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    name: str
    agent_type: AgentType
    description: str
    capabilities: list[AgentCapability] = field(default_factory=list)
    model: str = "gemini/gemini-1.5-flash"


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self._history: list[AgentResponse] = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def agent_type(self) -> AgentType:
        return self.config.agent_type

    def add_to_history(self, response: AgentResponse):
        self._history.append(response)

    def get_history(self) -> list[AgentResponse]:
        return self._history.copy()

    @abstractmethod
    async def execute(self, task: dict[str, Any]) -> AgentResponse:
        pass

    def can_execute(self, capability: AgentCapability) -> bool:
        return capability in self.config.capabilities

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} type={self.agent_type.value}>"
