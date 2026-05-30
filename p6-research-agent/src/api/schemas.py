from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    max_steps: int = Field(default=10, ge=1, le=30)


class Citation(BaseModel):
    type: str           # "pubmed" | "uniprot"
    id: str             # PMID or UniProt accession
    title: str = ""
    url: str = ""


class StepRecord(BaseModel):
    step: int
    tool: str
    input: dict
    output: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    steps: list[StepRecord]
    latency_ms: float


class HealthResponse(BaseModel):
    status: str
    ollama: str
    vector_store: str
    model: str
