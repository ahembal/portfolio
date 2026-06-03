from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    companion: str = Field(default="docs")
    message: str = Field(min_length=1, max_length=4000)
    page_url: str = Field(default="")
    page_content: str = Field(default="", max_length=8000)


class ResearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class HealthResponse(BaseModel):
    status: str
    backend: str
    p6_research_agent: str
    ollama: str
