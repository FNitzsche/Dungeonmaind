from pydantic import BaseModel, Field

class ConfigRequest(BaseModel):
    selected_LLM: str = Field(..., description="User selected LLM")

class ConfigResponse(BaseModel):
    status: str = Field(..., description="Confirmation status")

