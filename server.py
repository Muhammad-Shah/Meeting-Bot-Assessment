import os
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
from chatbot.engine import respond
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Load environment variables from .env file
load_dotenv()

app = FastAPI(title="Meeting Bot API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# In-memory session storage
sessions: Dict[str, dict] = {}

# Pydantic models for request validation
class TranscriptUpload(BaseModel):
    transcript: str
    session_id: str = str(uuid.uuid4())

class ChatMessage(BaseModel):
    message: str
    session_id: str

@app.post("/upload")
async def upload_transcript(data: TranscriptUpload):
    """Upload a meeting transcript"""
    # Save to session
    sessions[data.session_id] = {
        'transcript': data.transcript,
        'chat_history': [],
        'session_id': data.session_id
    }

    return {"message": "Transcript uploaded successfully"}

@app.post("/chat")
async def chat(data: ChatMessage):
    """Chat with the bot"""
    session_data = sessions.get(data.session_id)

    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a transcript first.")

    # Ensure session_id is in session_data
    session_data['session_id'] = data.session_id

    # Append to chat history
    chat_entry = {
        'sender': 'user',
        'content': data.message
    }
    session_data['chat_history'].append(chat_entry)

    # Get response from the enhanced engine
    response_message = respond(data.message, session_data)

    # Append bot response to chat history
    chat_entry = {
        'sender': 'bot',
        'content': response_message
    }
    session_data['chat_history'].append(chat_entry)

    return {"response": response_message}

@app.get("/health")
async def health_check():
    """Simple health check endpoint"""
    return {"status": "healthy", "message": "Meeting Bot API is running"}

# Serve index.html
# Mount the static files directory
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Serve index.html
@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    # Check if OpenAI API key is configured
    if not os.getenv('OPENAI_API_KEY'):
        print("WARNING: OPENAI_API_KEY environment variable is not set!")
        print("Please set your OpenAI API key in the environment or .env file")
    
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=5000,
        reload=os.getenv('DEBUG', 'False').lower() == 'true'
    )
