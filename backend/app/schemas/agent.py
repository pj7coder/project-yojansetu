from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(..., description="Citizen natural language query in Hindi or English")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Citizen profile attributes e.g. age, gender, caste, land")
    language: Optional[str] = Field("auto", description="Target language ('hi', 'en', 'auto')")


class ToolExecutionStep(BaseModel):
    step: int
    thought: str
    tool_name: str
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    tool_result: Dict[str, Any] = Field(default_factory=dict)
    duration_ms: float = 0.0


class AgentQueryResponse(BaseModel):
    final_answer: str
    language: str
    steps: List[ToolExecutionStep] = Field(default_factory=list)
    structured_data: Dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float


class ToolExecutionRequest(BaseModel):
    tool_name: str = Field(..., description="Exact registered name of tool")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool parameter arguments")


class ToolExecutionResponse(BaseModel):
    tool_name: str
    result: Dict[str, Any]


class ToolSchemaResponse(BaseModel):
    tools: List[Dict[str, Any]]
