"""
Professional Meeting Bot Engine

This module implements a comprehensive chatbot for analyzing meeting transcripts
with support for:
- Intelligent prompt routing
- Transcript summarization
- Question-answering
- Conversation history management with MongoDB
- Logging and observability

Author: AI Assistant
"""

import os
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_mongodb import MongoDBChatMessageHistory
from langchain.memory import ConversationBufferWindowMemory
from langchain.chains import LLMChain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from pydantic import SecretStr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Intent(Enum):
    """Enumeration of user intents for prompt routing"""
    SUMMARIZE = "summarize"
    QUESTION_ANSWER = "question_answer"
    GENERAL_CHAT = "general_chat"
    CLARIFICATION = "clarification"


class PromptRouter:
    """
    Intelligent prompt routing system that classifies user intents
    """
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.router_prompt = ChatPromptTemplate.from_template("""
        You are a smart intent classifier for a meeting transcript chatbot.
        
        Classify the user's message into one of these intents:
        - "summarize": User wants a summary of the meeting or specific topics
        - "question_answer": User is asking specific questions about the meeting content
        - "general_chat": General conversation not directly related to meeting content
        - "clarification": User is asking for clarification of previous responses
        
        User message: {message}
        Chat history context: {chat_history}
        
        Return ONLY the intent name (one word): summarize, question_answer, general_chat, or clarification
        """)
        
        self.router_chain = self.router_prompt | self.llm | StrOutputParser()
    
    def classify_intent(self, message: str, chat_history: List[Dict] | None = None) -> Intent:
        """
        Classify user message intent
        
        Args:
            message: User's message
            chat_history: Recent chat history for context
            
        Returns:
            Intent: Classified intent
        """
        try:
            # Format chat history for context
            history_context = ""
            if chat_history:
                recent_messages = chat_history[-3:]  # Last 3 messages for context
                history_context = "\n".join([
                    f"{msg['sender']}: {msg['content']}" 
                    for msg in recent_messages
                ])
            
            result = self.router_chain.invoke({
                "message": message,
                "chat_history": history_context
            })
            
            # Parse result and return Intent enum
            intent_str = result.strip().lower()
            
            if intent_str == "summarize":
                return Intent.SUMMARIZE
            elif intent_str == "question_answer":
                return Intent.QUESTION_ANSWER
            elif intent_str == "clarification":
                return Intent.CLARIFICATION
            else:
                return Intent.GENERAL_CHAT
                
        except Exception as e:
            logger.error(f"Error in intent classification: {e}")
            return Intent.GENERAL_CHAT


class TranscriptSummarizer:
    """
    Handles transcript summarization with different granularities
    """
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=4000,
            chunk_overlap=200,
            length_function=len
        )
        
        self.summary_prompt = ChatPromptTemplate.from_template("""
        You are an expert meeting analyst. Analyze the following meeting transcript and provide a comprehensive summary.
        
        Meeting Transcript:
        {transcript}
        
        Please provide:
        1. **Main Topics Discussed**: Key themes and subjects covered
        2. **Key Decisions Made**: Important decisions or conclusions reached
        3. **Action Items**: Tasks assigned or next steps identified
        4. **Important Participants**: Who spoke and their main contributions
        5. **Overall Meeting Outcome**: Summary of what was accomplished
        
        Format your response clearly with the above sections.
        """)
        
        self.summary_chain = self.summary_prompt | self.llm | StrOutputParser()
    
    def summarize_transcript(self, transcript: str) -> str:
        """
        Create a comprehensive summary of the meeting transcript
        
        Args:
            transcript: The meeting transcript text
            
        Returns:
            str: Formatted summary
        """
        try:
            if not transcript or len(transcript.strip()) < 50:
                return "The transcript appears to be too short or empty to provide a meaningful summary."
            
            # For very long transcripts, we might need to chunk and summarize
            if len(transcript) > 12000:
                return self._summarize_long_transcript(transcript)
            else:
                return self.summary_chain.invoke({"transcript": transcript})
                
        except Exception as e:
            logger.error(f"Error in transcript summarization: {e}")
            return "I apologize, but I encountered an error while summarizing the transcript. Please try again."
    
    def _summarize_long_transcript(self, transcript: str) -> str:
        """
        Handle summarization of very long transcripts by chunking
        
        Args:
            transcript: Long transcript text
            
        Returns:
            str: Summarized content
        """
        try:
            # Split into chunks
            chunks = self.text_splitter.split_text(transcript)
            
            # Summarize each chunk
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                chunk_summary = self.summary_chain.invoke({"transcript": chunk})
                chunk_summaries.append(f"Section {i+1}: {chunk_summary}")
            
            # Create final summary from chunk summaries
            combined_summary = "\n\n".join(chunk_summaries)
            final_summary_prompt = ChatPromptTemplate.from_template("""
            You have multiple summaries of sections from a long meeting transcript.
            Please create a comprehensive, unified summary that combines all the key information.
            
            Section Summaries:
            {summaries}
            
            Provide a unified summary with:
            1. **Overall Main Topics**
            2. **Key Decisions**
            3. **Action Items**
            4. **Important Participants**
            5. **Meeting Outcome**
            """)
            
            final_chain = final_summary_prompt | self.llm | StrOutputParser()
            return final_chain.invoke({"summaries": combined_summary})
            
        except Exception as e:
            logger.error(f"Error in long transcript summarization: {e}")
            return "I encountered an error while processing the long transcript. Please try with a shorter transcript."


class QuestionAnsweringSystem:
    """
    Handles question-answering about meeting transcripts
    """
    
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.qa_prompt = ChatPromptTemplate.from_template("""
        You are an expert meeting analyst. Answer the user's question based on the meeting transcript provided.
        
        Meeting Transcript:
        {transcript}
        
        Chat History (for context):
        {chat_history}
        
        User Question: {question}
        
        Instructions:
        - Answer based ONLY on the information available in the transcript
        - If the answer is not in the transcript, clearly state that
        - Provide specific quotes or references when possible
        - Be concise but comprehensive
        - If clarification is needed, ask follow-up questions
        
        Answer:
        """)
        
        self.qa_chain = self.qa_prompt | self.llm | StrOutputParser()
    
    def answer_question(self, question: str, transcript: str, chat_history: List[Dict] | None = None) -> str:
        """
        Answer a question about the meeting transcript
        
        Args:
            question: User's question
            transcript: Meeting transcript
            chat_history: Recent chat history for context
            
        Returns:
            str: Answer to the question
        """
        try:
            # Format chat history
            history_context = ""
            if chat_history:
                recent_messages = chat_history[-5:]  # Last 5 messages for context
                history_context = "\n".join([
                    f"{msg['sender']}: {msg['content']}" 
                    for msg in recent_messages
                ])
            
            return self.qa_chain.invoke({
                "transcript": transcript,
                "question": question,
                "chat_history": history_context
            })
            
        except Exception as e:
            logger.error(f"Error in question answering: {e}")
            return "I apologize, but I encountered an error while processing your question. Please try rephrasing your question."


class ChatHistoryManager:
    """
    Manages conversation history using MongoDB
    """
    
    def __init__(self, mongodb_connection_string: str | None = None):
        self.connection_string = mongodb_connection_string or os.getenv(
            "MONGODB_CONNECTION_STRING", 
            "mongodb://localhost:27017/"
        )
        self.database_name = "meeting_bot"
        self.collection_name = "chat_history"
    
    def get_chat_history(self, session_id: str) -> MongoDBChatMessageHistory | None:
        """
        Get or create MongoDB chat history for a session
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            MongoDBChatMessageHistory: Chat history instance
        """
        try:
            return MongoDBChatMessageHistory(
                connection_string=self.connection_string,
                session_id=session_id,
                database_name=self.database_name,
                collection_name=self.collection_name
            )
        except Exception as e:
            logger.error(f"Error creating MongoDB chat history: {e}")
            # Return None if MongoDB is not available
            return None
    
    def add_conversation_turn(self, session_id: str, user_message: str, ai_response: str):
        """
        Add a conversation turn to the chat history
        
        Args:
            session_id: Session identifier
            user_message: User's message
            ai_response: AI's response
        """
        try:
            chat_history = self.get_chat_history(session_id)
            if chat_history:
                chat_history.add_user_message(user_message)
                chat_history.add_ai_message(ai_response)
        except Exception as e:
            logger.error(f"Error adding conversation turn: {e}")


class MeetingBotEngine:
    """
    Main orchestrator for the meeting bot engine
    """
    
    def __init__(self, openai_api_key: str | None = None, mongodb_connection_string: str | None = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            api_key=SecretStr(self.openai_api_key),
            base_url="https://openrouter.ai/api/v1",
            model="mistralai/mistral-small-3.2-24b-instruct:free",
            temperature=0.1
        )
        
        # Initialize components
        self.prompt_router = PromptRouter(self.llm)
        self.summarizer = TranscriptSummarizer(self.llm)
        self.qa_system = QuestionAnsweringSystem(self.llm)
        # self.chat_history_manager = ChatHistoryManager(mongodb_connection_string)
        
        logger.info("MeetingBotEngine initialized successfully")
    
    def process_message(self, user_message: str, session_data: Dict) -> str:
        """
        Main message processing function
        
        Args:
            user_message: User's message
            session_data: Session data containing transcript and chat history
            
        Returns:
            str: Bot's response
        """
        try:
            # Extract session data
            transcript = session_data.get("transcript", "")
            chat_history = session_data.get("chat_history", [])
            # chat_history = await self.chat_history_manager.get_chat_history(session_data.get("session_id", "")).aget_messages()

            session_id = session_data.get("session_id", "")
            
            # Check if transcript is available
            if not transcript:
                return "Please upload a meeting transcript first so I can help you analyze it."
            
            # Log the interaction
            logger.info(f"Processing message for session {session_id}: {user_message[:50]}...")
            
            # Classify intent
            intent = self.prompt_router.classify_intent(user_message, chat_history)
            logger.info(f"Classified intent: {intent.value}")
            
            # Route to appropriate handler
            if intent == Intent.SUMMARIZE:
                response = self.summarizer.summarize_transcript(transcript)
            elif intent == Intent.QUESTION_ANSWER:
                response = self.qa_system.answer_question(user_message, transcript, chat_history)
            elif intent == Intent.CLARIFICATION:
                response = self.qa_system.answer_question(user_message, transcript, chat_history)
            else:
                response = self._handle_general_chat(user_message, transcript, chat_history)
            
            # Add to MongoDB chat history
            # self.chat_history_manager.add_conversation_turn(session_id, user_message, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I apologize, but I encountered an error while processing your message. Please try again."
    
    def _handle_general_chat(self, message: str, transcript: str, chat_history: List[Dict]) -> str:
        """
        Handle general chat messages
        
        Args:
            message: User message
            transcript: Meeting transcript
            chat_history: Chat history
            
        Returns:
            str: Response
        """
        general_chat_prompt = ChatPromptTemplate.from_template("""
        You are a helpful meeting bot assistant. The user is having a general conversation.
        
        You have access to a meeting transcript, so you can reference it if relevant.
        
        Meeting Transcript (available if needed):
        {transcript}
        
        Recent Chat History:
        {chat_history}
        
        User Message: {message}
        
        Respond in a friendly, helpful manner. If the user's message could be related to the meeting,
        offer to help with analysis, summaries, or questions about the meeting.
        """)
        
        try:
            # Format chat history
            history_context = ""
            if chat_history:
                recent_messages = chat_history[-3:]
                history_context = "\n".join([
                    f"{msg['sender']}: {msg['content']}" 
                    for msg in recent_messages
                ])
            
            chain = general_chat_prompt | self.llm | StrOutputParser()
            return chain.invoke({
                "message": message,
                "transcript": transcript[:1000] + "..." if len(transcript) > 1000 else transcript,
                "chat_history": history_context
            })
            
        except Exception as e:
            logger.error(f"Error in general chat: {e}")
            return "I'm here to help you analyze your meeting transcript! You can ask me to summarize the meeting, answer specific questions, or just chat about the content."


# Main function for backward compatibility
def respond(user_message: str, session_data: Dict) -> str:
    """
    Main chatbot response function - now powered by the professional engine
    
    Args:
        user_message (str): The user's chat message
        session_data (dict): Session data containing:
            - transcript (str): The uploaded meeting transcript
            - chat_history (list): List of previous messages
            - session_id (str): Unique session identifier
    
    Returns:
        str: The chatbot's response
    """
    try:
        # Initialize the engine (this could be cached for better performance)
        engine = MeetingBotEngine()
        
        # Process the message
        return engine.process_message(user_message, session_data)
        
    except Exception as e:
        logger.error(f"Error in respond function: {e}")
        return "I apologize, but I'm having trouble connecting to the AI service. Please check your OpenAI API key configuration and try again."
