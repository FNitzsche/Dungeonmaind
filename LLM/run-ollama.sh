#!/usr/bin/env bash

ollama serve &
sleep 5
echo "Listing existing models..."
ollama list
ollama pull hf.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF:Q5_K_M

echo "Listing models after pull..."
ollama list