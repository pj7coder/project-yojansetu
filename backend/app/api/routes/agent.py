import logging
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.agent.tools import (
    TOOL_REGISTRY,
    get_tools_schema,
    execute_tool as dispatch_tool,
)
from app.agent.orchestrator import WelfareAgentOrchestrator
from app.schemas.agent import (
    AgentQueryRequest,
    AgentQueryResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolExecutionStep,
    ToolSchemaResponse,
)

logger = logging.getLogger("jansetu.api.agent")

router = APIRouter(prefix="/agent", tags=["ReAct Agent & Tools Engine"])


@router.get(
    "/tools",
    response_model=ToolSchemaResponse,
    summary="Get registered tool definitions and JSON schemas",
    description="Returns OpenAPI/JSON Schema specifications for all decorated domain tools registered in the agent engine.",
)
def get_tools() -> ToolSchemaResponse:
    try:
        schemas = get_tools_schema()
        return ToolSchemaResponse(tools=schemas)
    except Exception as e:
        logger.error(f"Error fetching tool schemas: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch tool schemas: {str(e)}",
        )


@router.post(
    "/query",
    response_model=AgentQueryResponse,
    summary="Execute multi-step ReAct agent query",
    description="Sequences Thought -> Action -> Observation steps with domain tools to deliver deterministic, circular-grounded welfare advice.",
)
def run_agent_query(
    request: AgentQueryRequest,
    session: Session = Depends(get_db),
) -> AgentQueryResponse:
    start_time = time.time()
    try:
        result = WelfareAgentOrchestrator.process_query(
            query=request.query,
            language_preference=request.language,
            initial_profile=request.context,
        )

        steps = [
            ToolExecutionStep(
                step=s.step_number,
                thought=s.thought,
                tool_name=s.tool_name,
                tool_args=s.tool_input,
                tool_result=s.tool_output,
                duration_ms=s.duration_ms,
            )
            for s in result.reasoning_steps
        ]

        structured = {
            "citations": result.citations,
            "recommended_schemes": result.recommended_schemes,
            "required_documents": result.required_documents,
            "emitra_kiosk_info": result.emitra_kiosk_info,
            "profile_extracted": result.profile_extracted,
        }

        exec_ms = round((time.time() - start_time) * 1000, 2)
        return AgentQueryResponse(
            final_answer=result.answer,
            language=result.language,
            steps=steps,
            structured_data=structured,
            execution_time_ms=exec_ms,
        )
    except Exception as e:
        logger.error(f"Agent execution error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent orchestrator failed: {str(e)}",
        )


@router.post(
    "/tool-call",
    response_model=ToolExecutionResponse,
    summary="Directly execute a registered domain tool",
    description="Invokes a specific decorated tool directly with arguments (e.g. for deterministic simulation or UI widgets).",
)
def execute_tool(
    request: ToolExecutionRequest,
    session: Session = Depends(get_db),
) -> ToolExecutionResponse:
    try:
        if request.tool_name not in TOOL_REGISTRY:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tool '{request.tool_name}' not found. Available: {list(TOOL_REGISTRY.keys())}",
            )
        
        args = dict(request.arguments or {})
        target = TOOL_REGISTRY[request.tool_name]
        # Inject db session if required
        if "db" in target.func.__code__.co_varnames:
            args["db"] = session
            
        exec_res = dispatch_tool(request.tool_name, args)
        return ToolExecutionResponse(tool_name=request.tool_name, result=exec_res)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing tool {request.tool_name}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(e)}",
        )
