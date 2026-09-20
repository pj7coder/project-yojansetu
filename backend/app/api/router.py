from fastapi import APIRouter
from app.api.routes import (
    chunks,
    departments,
    document_duplicates,
    documents,
    evidence_verification,
    extraction,
    health,
    ocr,
    parsing,
    scheme_drafts,
    schemes,
    validation,
    review,
    eligibility,
    discovery,
    citizen_sessions,
    admin_cache,
    source_monitoring,
    change_analysis,
    versioning,
    citizen,
    admin_dashboard,
    audio_dev,
    citizen_input,
    conversation,
    tts,
    voice,
    agent,
    rag,
)

api_router = APIRouter()

# Register core health router
api_router.include_router(health.router)

# Register audio & TTS development routers
api_router.include_router(audio_dev.router)
api_router.include_router(tts.router)

# Register domain entities
api_router.include_router(schemes.router, prefix="/schemes", tags=["Schemes"])
api_router.include_router(departments.router, prefix="/departments", tags=["Departments"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(document_duplicates.router, prefix="/documents", tags=["Duplicate Detection"])
api_router.include_router(parsing.router, prefix="/documents", tags=["Document Parsing"])
api_router.include_router(ocr.router, prefix="/documents", tags=["Document OCR"])
api_router.include_router(chunks.router, tags=["Document Chunking"])
api_router.include_router(extraction.router, tags=["Document LLM Extraction"])
api_router.include_router(scheme_drafts.router, tags=["Canonical Scheme Drafts"])
api_router.include_router(validation.router, tags=["Deterministic Validation Engine"])
api_router.include_router(evidence_verification.router, tags=["Evidence Verification Engine"])
api_router.include_router(review.router, tags=["Human Review Workflow"])
api_router.include_router(eligibility.router, tags=["Deterministic Eligibility Engine"])
api_router.include_router(discovery.router, tags=["Scheme Discovery & Semantic Ranking"])
api_router.include_router(citizen_sessions.router)
api_router.include_router(citizen.router)
api_router.include_router(admin_cache.router)
api_router.include_router(source_monitoring.router)
api_router.include_router(change_analysis.router)
api_router.include_router(versioning.router)
api_router.include_router(admin_dashboard.router)
api_router.include_router(citizen_input.router)
api_router.include_router(conversation.router)
api_router.include_router(voice.router)
api_router.include_router(agent.router)
api_router.include_router(rag.router)
