from fastapi import APIRouter
from app.base_models.llm_base_models import LLMRequest
from app.functions.llm.custom_model import run_custom_model

from fastapi.responses import StreamingResponse

router = APIRouter()

chat_history = []

@router.post("/runLLM")
async def run_llm(request: LLMRequest):
    chat_history.append({"role": "user", "content": request.input_string})

    def event_generator():
        assistant_response = ""
        for chunk in run_custom_model(chat_history):
            assistant_response += chunk
            yield f"{chunk}"
        # Append full assistant response to chat history after streaming
        chat_history.append({"role": "assistant", "content": assistant_response})
        #print(chat_history)

    return StreamingResponse(event_generator(), media_type="text/plain")