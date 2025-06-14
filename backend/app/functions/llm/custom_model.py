import ollama


def run_custom_model(prompt: str) -> str:
    """
    Run a custom LLM.
    """

    # Initialize the Ollama client
    client = ollama.Client()

    # Define the model
    model = "hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M"

    # Send the query to the model
    response = client.generate(model=model, prompt=prompt)

    return f"[model output: {response.response}]"
