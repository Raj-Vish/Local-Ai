# Local Enterprise AI Assistant (Expense RAG)

This project is a Secure, Local AI-Assisted Expense Management System. It allows users to upload financial documents (PDFs/Receipts) and interact with an AI to summarize, extract, and query expense data. The entire system runs **100% offline** on local hardware using Small Language Models (SLMs).

## Architecture

The system is divided into two main components:
1. **Frontend (React/Vite)**: A modern, ChatGPT-like web interface for users to upload documents and chat.
2. **Backend (Python/FastAPI)**: The bridging server that processes PDFs, manages conversation memory, and communicates with the local AI.

---

## 1. The Backend (Python)
**File:** `server.py`

### What it does:
- Acts as the middleman between the React UI and the local AI (Ollama).
- Listens on `http://localhost:8000/chat`.
- **File Uploads**: Uses `PyMuPDF` (`fitz`) to extract text directly from uploaded PDFs in memory.
- **Persistent Memory**: Saves the conversation history to `backend_memory.json` so the AI retains context even if the server restarts.
- **AI Integration**: Sends the extracted text and user prompt to `qwen2.5:3b` via Ollama with `temperature: 0.0` to ensure factual, non-hallucinated answers.

### How to run it:
1. Open a terminal in the project folder.
2. Ensure Ollama is running in the background.
3. Start the FastAPI server:
   ```bash
   uvicorn server:app --reload
   ```

---

## 2. The Frontend (React)
**Folder:** `src/`

### What it does:
- Provides a beautiful, dark-mode workspace (`ChatView.jsx`, `Sidebar.jsx`).
- **File Attachments**: Users can attach documents using the `+` button (`Composer.jsx`).
- **Persistent Memory**: Uses `localStorage` inside `useChatSession.js` so that if the user refreshes the browser, their chats are not lost.
- **Full-Stack Connection**: Connects to the backend via a `fetch()` request sending a `FormData` object containing the user's message and the attached PDF binary.

### How to run it:
1. Open a second terminal in the project folder.
2. Install dependencies (only needed once): `npm install`
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
4. Open the provided `localhost` link in your browser.

---

## Previous Prototype Scripts (Reference)
Before building the full-stack app, we built prototypes to test the individual pieces:
- **`read_pdf_ai.py`**: A pure terminal script to test if `PyMuPDF` could extract text from a dummy PDF and pass it to Ollama.
- **`expense_rag.py`**: A prototype script to test Vector Database chunking using ChromaDB (this logic will be integrated into `server.py` in the next phase).
