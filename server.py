from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import ollama
import time
import fitz  # PyMuPDF

import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

HISTORY_FILE = "backend_memory.json"

# Load memory from disk if it exists, otherwise use the default system prompt
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r") as f:
        chat_history = json.load(f)
else:
    chat_history = [
        {
            "role": "system",
            "content": """You are the Company Expense AI Assistant.
When a user uploads a document, carefully read the text provided to answer their questions.
Be precise, professional, and do not hallucinate numbers or facts."""
        }
    ]

def extract_text_from_pdf_bytes(pdf_bytes):
    """Helper function to read a PDF directly from memory (no saving to disk needed!)"""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

import base64

@app.post("/chat")
async def chat_endpoint(
    message: str = Form(...),
    user_role: str = Form("Employee"),
    files: List[UploadFile] = File(default=[]) 
):
    global chat_history
    
    print(f"\n[*] Received message from React UI: {message}")
    start_time = time.time()
    
    document_context = ""
    
    # 1. Process files based on their type (PDF vs Text)
    if files:
        for file in files:
            print(f"[*] Processing uploaded document: {file.filename}")
            content = await file.read()
            
            if file.filename.lower().endswith(".pdf"):
                extracted_text = extract_text_from_pdf_bytes(content)
                document_context += f"\n--- Document: {file.filename} ---\n{extracted_text}\n"
            else:
                document_context += f"\n--- Document: {file.filename} ---\n{content.decode('utf-8')}\n"

    if document_context:
        full_prompt = f"I have uploaded a document. {document_context}\n\nUser Question: {message}"
    else:
        full_prompt = message

    # Build the message object
    chat_history.append({"role": "user", "content": full_prompt})
    
    try:
        response = ollama.chat(
            model="qwen2.5:3b",
            messages=chat_history,
            options={"temperature": 0.0} 
        )
        
        answer = response["message"]["content"]
        chat_history.append({"role": "assistant", "content": answer})
        
        with open(HISTORY_FILE, "w") as f:
            json.dump(chat_history, f, indent=4)
        
        print(f"[*] AI Response generated in {time.time() - start_time:.2f} seconds.")
        return {"reply": answer, "status": "success"}
        
    except Exception as e:
        print(f"[!] Error: {e}")
        return {"reply": f"Error: Could not connect to SLM. Details: {e}", "status": "error"}
