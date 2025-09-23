from pydantic import BaseModel, Field


class EmbeddRequest(BaseModel):
    input_string: str = Field(..., description="Text to be embedded")


class EmbeddResponse(BaseModel):
    output: str = Field(..., description="Text generated out of embeddings")
