import os
import time
import re
import json
import asyncio
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, Optional
import sys
from contextlib import asynccontextmanager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from langchain_qdrant import Qdrant
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.question_answering import load_qa_chain
from langchain.prompts import PromptTemplate
from qdrant_client import QdrantClient
from dotenv import load_dotenv
from db import DatabaseManager
from groq import Groq

# Load environment variables first
load_dotenv()

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
FILE_PATH = os.path.join(PROJECT_ROOT, "supreme_court_cleaned_texts")
TEXT_FILE_DIR = FILE_PATH 
FAISS_INDEX_BASE = os.path.join(PROJECT_ROOT, "faiss_index")
COLLECTION_NAME = "legal_documents"

# Create necessary directories
os.makedirs(FAISS_INDEX_BASE, exist_ok=True)
os.makedirs(TEXT_FILE_DIR, exist_ok=True)

# Environment variables
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
QDRANT_CLOUD_URL = os.getenv("QDRANT_CLOUD_URL")
QDRANT_API_KEY = os.getenv("QDRANT_CLOUD_API_KEY")

# Server configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Validate required environment variables
required_env_vars = {
    "GROQ_API_KEY": GROQ_API_KEY,
    "QDRANT_CLOUD_URL": QDRANT_CLOUD_URL,
    "QDRANT_API_KEY": QDRANT_API_KEY
}

missing_vars = [var for var, value in required_env_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize components on startup"""
    global embeddings_hf, qdrant, qdrant_client
    
    try:
        # Initialize HuggingFace embeddings (for Qdrant and FAISS loading)
        embeddings_hf = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # Initialize Qdrant client
        qdrant_client = QdrantClient(
            url=QDRANT_CLOUD_URL,
            api_key=QDRANT_API_KEY,
            timeout=30
        )
        
        # Verify collection exists
        existing_collections = [col.name for col in qdrant_client.get_collections().collections]
        if COLLECTION_NAME not in existing_collections:
            raise ValueError(f"Collection '{COLLECTION_NAME}' not found in Qdrant Cloud.")
        
        # Create Qdrant instance
        qdrant = Qdrant(
            client=qdrant_client,
            collection_name=COLLECTION_NAME,
            embeddings=embeddings_hf
        )
        
        print(f"✅ Successfully connected to Qdrant collection: {COLLECTION_NAME}")
        yield
        print("🔄 Shutting down components...")
        
    except Exception as e:
        print(f"❌ Failed to initialize components: {e}")
        raise e

# Create FastAPI app
app = FastAPI(
    title="Kanoon Legal Search API", 
    version="1.0.0",
    description="AI-powered legal document search and analysis system",
    lifespan=lifespan
)

# Configure CORS with environment-based origins
allowed_origins = [FRONTEND_URL]
if ENVIRONMENT == "development":
    allowed_origins.extend(["http://localhost:3000", "http://localhost:5173"])
elif ENVIRONMENT == "production":
    # Add Vercel domains for production
    allowed_origins.extend([
        "https://kanoon-two.vercel.app",
        "https://kanoon.vercel.app",
        "https://*.vercel.app"  # Allow all Vercel subdomains
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Restrict methods
    allow_headers=["*"],
)

# Global components
embeddings_hf = None
qdrant = None
qdrant_client = None
groq_client = None
  
# Pydantic models
class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    
    class Config:
        schema_extra = {
            "example": {
                "query": "fundamental rights constitutional violation",
                "top_k": 5
            }
        }

class AddDocumentsRequest(BaseModel):
    file_path: str

class StructuredQueryRequest(BaseModel):
    text: str
    source: str

class ChatInitRequest(BaseModel):
    case_id: str

class ChatMessageRequest(BaseModel):
    case_id: str
    question: str

class GroqRateLimiter:
    def __init__(self, max_requests_per_minute=25):  # 25 to stay safe under 30
        self.max_requests = max_requests_per_minute
        self.requests = deque()
        self.lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        """Wait if we're approaching rate limit"""
        async with self.lock:
            now = datetime.now()
            
            # Remove requests older than 1 minute
            while self.requests and now - self.requests[0] > timedelta(minutes=1):
                self.requests.popleft()
            
            # If we're at the limit, wait
            if len(self.requests) >= self.max_requests:
                wait_time = 61 - (now - self.requests[0]).seconds
                if wait_time > 0:
                    print(f"⏳ Rate limit reached. Waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    # Clean old requests after waiting
                    self.requests.clear()
            
            # Record this request
            self.requests.append(now)
            
            # Small delay between requests for safety
            await asyncio.sleep(2)  # 2 second delay = max 30 per minute

# Global rate limiter instance
groq_rate_limiter = GroqRateLimiter(max_requests_per_minute=25)

# Helper functions
def get_groq_client():
    """Get Groq client instance"""
    global groq_client
    if groq_client is None:
        groq_client = Groq(api_key=GROQ_API_KEY)
    return groq_client

def get_case_metadata(case_id: str) -> Optional[Dict]:
    """Get case metadata from your database"""
    try:
        # Try by filename first (for existing functionality)
        result = DatabaseManager.get_case_by_filename(f"{case_id}.txt")
        if result:
            return result
        
        # Try by ID if filename doesn't work
        try:
            result = DatabaseManager.get_case_by_id(int(case_id))
            if result:
                print(f"Case metadata retrieved: {result}")
                return result
        except ValueError:
            pass
        
        # If not found in database, check if file exists and create basic metadata
        text_file_path = os.path.join(TEXT_FILE_DIR, f"{case_id}.txt")
        if os.path.exists(text_file_path):
            print(f"📄 Case {case_id} file exists but not in database, creating basic metadata")
            return {
                "id": case_id,
                "file_name": f"{case_id}.txt",
                "title": f"Legal Case {case_id} - Supreme Court Judgment",
                "judges": "Not available",
                "date": "Not available",
                "summary": "Legal case summary not available"
            }
        
        return None
            
    except Exception as e:
        print(f"Error retrieving case metadata: {e}")
        return None

def save_case_metadata(data: Dict) -> bool:
    """Save case metadata using your existing insert function"""
    if not data.get("file_name") and data.get("id"):
        data["file_name"] = f"{data['id']}.txt"
    
    if not data.get("file_name"):
        print(f"❌ Cannot save metadata without file_name: {data}")
        return False
    
    return DatabaseManager.insert_metadata(data)
    
def extract_case_id(source_path: str) -> str:
    """Extract numeric ID from source path"""
    try:
        return source_path.split("/")[-1].split(".")[0]
    except Exception:
        raise ValueError("Invalid source path format")

def vector_store_exists(case_id: str) -> bool:
    """Check if FAISS vector store exists for case"""
    index_dir = os.path.join(FAISS_INDEX_BASE, case_id)
    return os.path.exists(os.path.join(index_dir, "index.faiss"))

def create_vector_store(case_id: str, text: str) -> str:
    """
    Check if FAISS vector store exists for case
    Note: This function is kept for compatibility but indexes should be pre-built
    """
    index_path = os.path.join(FAISS_INDEX_BASE, case_id)
    
    if not vector_store_exists(case_id):
        raise ValueError(f"Pre-built FAISS index not found for case {case_id}. Please run build_all_indexes.py first.")
    
    return index_path

def load_qa_model():
    """Load QA chain model"""
    prompt_template = """
    You are a legal document analyst. Answer the question concisely and precisely from the provided context.
    
    IMPORTANT RULES:
    - Give direct, concise answers
    - If information is not in the context, respond with "Not available"
    - For dates: Extract exact dates in YYYY-MM-DD format if possible
    - For case titles: Extract the exact case name or citation
    - For judges: List judge names separated by commas
    - For summaries: Maximum 100 words, focus on key legal points
    - If information is not in the context, say only "Not available"
    - Do not explain why information is not available
    - Do not add extra sentences

    Context: \n {context}\n
    Question: \n {question}\n
    Answer:
    """
    
    class GroqLLM:
        def __init__(self):
            self.client = get_groq_client()
        
        def invoke(self, prompt_input):
            try:
                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(groq_rate_limiter.wait_if_needed())
                except:
                    time.sleep(2)  # Fallback simple delay
                completion = self.client.chat.completions.create(
                    model="llama-3.1-8b-instant",  # Fast Groq model
                    messages=[
                        {"role": "user", "content": prompt_input}
                    ],
                    temperature=0.1,
                )
                return completion.choices[0].message.content
            except Exception as e:
                print(f"Groq API error: {e}")
                return "Error generating response"
    
    model = GroqLLM()
    prompt = PromptTemplate(
        template=prompt_template, 
        input_variables=["context", "question"]
    )
    
    # Custom QA chain since we're not using standard LangChain model
    class CustomQAChain:
        def __init__(self, model, prompt):
            self.model = model
            self.prompt = prompt
        
        def invoke(self, inputs):
            docs = inputs["input_documents"]
            question = inputs["question"]
            
            # Combine all document content
            context = "\n\n".join([doc.page_content for doc in docs])
            
            # Format prompt
            prompt_text = self.prompt.format(context=context, question=question)
            
            # Get response
            output_text = self.model.invoke(prompt_text)
            
            return {"output_text": output_text}
    
    return CustomQAChain(model, prompt)

def query_vector_store(user_question: str, case_id: str) -> str:
    """Query FAISS vector store for specific case"""
    index_path = os.path.join(FAISS_INDEX_BASE, case_id)
    
    if not vector_store_exists(case_id):
        raise ValueError(f"Pre-built FAISS index not found for case {case_id}. Please run build_all_indexes.py first.")
    
    vector_store = FAISS.load_local(
        index_path,
        embeddings_hf,
        allow_dangerous_deserialization=True
    )
    
    # Get case metadata for context
    case_metadata = get_case_metadata(case_id)
    
    # Use FAISS to find the single most relevant document for the specific question
    docs = vector_store.similarity_search(user_question, k=1)  # Get only the most relevant document
    
    try:
        asyncio.create_task(groq_rate_limiter.wait_if_needed())
        client = get_groq_client()
        
        # Use the single most relevant document (no size limiting)
        context = docs[0].page_content if docs else "No relevant content found."
        
        # Build case info for context
        case_info = ""
        if case_metadata:
            case_info = f"""
        CASE INFORMATION:
        - Case Title: {case_metadata.get('title', 'Not available')}
        - Judges: {case_metadata.get('judges', 'Not available')}
        - Date: {case_metadata.get('date', 'Not available')}
        - Summary: {case_metadata.get('summary', 'Not available')}
        """
        
        chat_prompt = f"""You are Lexiscope, a legal AI assistant specializing in Indian law cases.

        {case_info}

        MOST RELEVANT CASE CONTENT (found by semantic search):
        {context}

        USER QUESTION: {user_question}

        INSTRUCTIONS:
        - Answer the question based on the most relevant case content above
        - This content was specifically selected as the most relevant to your question
        - Be specific and cite relevant details from the case content
        - If the answer is not in this specific content, state "This information is not available in the most relevant part of the case documents"
        - Use clear, professional legal language
        - Provide a direct, focused answer

        RESPONSE:"""
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": chat_prompt}],
            temperature=0.2,
        )
        
        answer = completion.choices[0].message.content.strip()
        
        # Clean up common AI response artifacts
        answer = answer.replace("Answer is not available in the context.", "Not available")
        answer = answer.replace("answer is not available in the context", "Not available")
        
        return answer
        
    except Exception as e:
        print(f"Error querying with Groq: {e}")
        return "Error processing query"

async def extract_all_metadata_single_call(full_text: str) -> Dict:
    try:
        print("🔄 Starting metadata extraction with Groq...")
        await groq_rate_limiter.wait_if_needed()
        client = get_groq_client()

        # ✅ SPLIT FULL TEXT INTO LOGICAL SECTIONS
        lines = full_text.strip().split("\n")
        first_page = "\n".join(lines[:100])  # First 100 lines for title
        last_page = "\n".join(lines[-100:])  # Last 100 lines for judges/date
        
        # Use first 4000 chars for summary context
        text_sample = full_text[:4000] + "..." if len(full_text) > 4000 else full_text
        
        print(f"📄 Document stats: {len(full_text)} chars, {len(lines)} lines")
        print(f"📄 First page preview: {first_page[:200]}...")
        print(f"📄 Last page preview: ...{last_page[-200:]}")
        
        # ✅ SEPARATE SYSTEM AND USER MESSAGES (like playground)
        system_prompt = """You are a legal metadata extractor for Supreme Court of India judgments. Extract information and return ONLY valid JSON.

        Extract and return EXACTLY this JSON format with no additional text:
        {
            "title": "exact case name with vs/v.",
            "judges": "judge names separated by commas, no titles",
            "date": "judgment date in DD-MM-YYYY format",
            "summary": "concise 100-word summary of main legal issue and outcome"
        }

        Rules:
        - For title: Look for "PETITIONER vs RESPONDENT" or "Appellant vs Respondent" pattern
        - For judges: Extract names from end signature lines like "....J. (Judge Name)" 
        - For date: Look for date at end after "New Delhi;" or similar
        - For summary: Focus on key legal principles, main issue, and court's decision
        - Use "Not available" if information cannot be found
        - Return only the JSON, no other text"""

        user_content = f"""FIRST PAGE (for case title):
        {first_page}

        LAST PAGE (for judges and date):
        {last_page}

        DOCUMENT SAMPLE (for summary):
        {text_sample}"""

        print("📡 Making Groq API call with system/user messages...")
        
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.21,  # Match playground
            max_completion_tokens=600,
            top_p=1,
            timeout=30
        )

        response_text = completion.choices[0].message.content.strip()
        print(f"🔥 GROQ RAW RESPONSE:")
        print(f"{'='*50}")
        print(response_text)
        print(f"{'='*50}")
    
        # Parse JSON response
        try:
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start != -1 and json_end != -1:
                json_text = response_text[json_start:json_end]
                metadata = json.loads(json_text)
                
                # Validate and clean required keys
                required_keys = ["title", "judges", "date", "summary"]
                for key in required_keys:
                    if key not in metadata or not metadata[key]:
                        metadata[key] = "Not available"
                    else:
                        metadata[key] = metadata[key].strip()
                        
                        # Fix judges field if it's a list (convert to string)
                        if key == "judges" and isinstance(metadata[key], list):
                            metadata[key] = ", ".join(metadata[key])
                
                print(f"✅ Successfully parsed metadata: {metadata}")
                return metadata
            else:
                raise json.JSONDecodeError("No JSON found in response", response_text, 0)
                
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            return parse_response_manually(response_text)
        
    except Exception as e:
        print(f"❌ Error extracting metadata with Groq: {e}")
        print(f"Error type: {type(e).__name__}")
        
        # Return fallback metadata
        return {
            "title": "Not available",
            "judges": "Not available",
            "date": "Not available",
            "summary": "Not available"
        }

def parse_response_manually(text: str) -> Dict:
    """Manually parse response if JSON parsing fails"""
    metadata = {}
    
    # Try to extract fields manually
    title_match = re.search(r'"title":\s*"([^"]*)"', text, re.IGNORECASE)
    judges_match = re.search(r'"judges":\s*"([^"]*)"', text, re.IGNORECASE)
    date_match = re.search(r'"date":\s*"([^"]*)"', text, re.IGNORECASE)
    summary_match = re.search(r'"summary":\s*"([^"]*)"', text, re.IGNORECASE | re.DOTALL)
    
    metadata["title"] = title_match.group(1) if title_match else "Not available"
    metadata["judges"] = judges_match.group(1) if judges_match else "Not available"
    metadata["date"] = date_match.group(1) if date_match else "Not available"
    metadata["summary"] = summary_match.group(1) if summary_match else "Not available"
    
    return metadata

# API Endpoints
@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Lexiscope Legal Search API",
        "version": "1.0.0"
    }

@app.get("/faiss_status")
async def check_faiss_status():
    """Check status of pre-built FAISS indexes"""
    try:
        if not os.path.exists(FAISS_INDEX_BASE):
            return {
                "status": "not_found",
                "message": "FAISS index directory not found",
                "indexes_available": 0,
                "total_size_mb": 0
            }
        
        # Count available indexes
        indexes = []
        for item in os.listdir(FAISS_INDEX_BASE):
            item_path = os.path.join(FAISS_INDEX_BASE, item)
            if os.path.isdir(item_path) and vector_store_exists(item):
                indexes.append(item)
        
        # Calculate total size
        total_size = 0
        for index_dir in indexes:
            index_path = os.path.join(FAISS_INDEX_BASE, index_dir)
            for root, dirs, files in os.walk(index_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size += os.path.getsize(file_path)
        
        total_size_mb = total_size / (1024 * 1024)
        
        return {
            "status": "available",
            "message": f"Found {len(indexes)} pre-built FAISS indexes",
            "indexes_available": len(indexes),
            "total_size_mb": round(total_size_mb, 2),
            "sample_indexes": indexes[:10] if len(indexes) > 10 else indexes
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error checking FAISS status: {str(e)}",
            "indexes_available": 0,
            "total_size_mb": 0
        }

@app.post("/query")
async def query_documents(request: QueryRequest):
    """Search legal documents using vector similarity"""
    try:
        if not qdrant:
            raise HTTPException(status_code=503, detail="Service not initialized")

        retriever = qdrant.as_retriever(search_kwargs={"k": request.top_k})
        results = retriever.invoke(request.query)
        
        structured_results = []
        seen_case_ids = set()
        
        for doc in results:
            source = doc.metadata.get("source", "")
            if not source:
                continue
                
            case_id = extract_case_id(source)

            # Skip if we've already processed this case
            if case_id in seen_case_ids:
                continue
            
            seen_case_ids.add(case_id)

            # Check database cache first
            cached_data = get_case_metadata(case_id)
            if cached_data:
                structured_results.append(cached_data)
                continue
            
            # Process with RAG if not cached
            try:
                structured_data = await process_document_metadata(doc.page_content, source)
                if structured_data:
                    save_case_metadata(structured_data)
                    structured_results.append(structured_data)
            except Exception as e:
                print(f"Error processing document {source}: {e}")
                continue
        
        return {
            "query": request.query,
            "total_results": len(structured_results),
            "results": structured_results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

async def process_document_metadata(text: str, source: str) -> Optional[Dict]:
    """Process document to extract metadata"""
    try:
        case_id = extract_case_id(source)
        print(f"🔄 Processing case {case_id}")

        text_file_path = os.path.join(TEXT_FILE_DIR, f"{case_id}.txt")
        
        if os.path.exists(text_file_path):
            with open(text_file_path, "r", encoding="utf-8") as file:
                full_document_text = file.read()
            print(f"📄 Loaded full document: {len(full_document_text)} characters")
        else:
            print(f"⚠️ File not found: {text_file_path}, using provided text")
            full_document_text = text
        
        # Single API call to extract all metadata
        print(f"🤖 Extracting metadata from full document for case {case_id}")
        metadata = await extract_all_metadata_single_call(full_document_text)

        if not metadata:
            print(f"❌ No metadata extracted for case {case_id}")
            return None
        
        # Clean up the case title
        case_title = metadata.get("title", "Not available")
        if case_title == "Not available" or len(case_title) > 200 or "not available" in case_title.lower():
            case_title = f"Case {case_id}"
        
        # Ensure title is always clickable by making it descriptive
        if case_title == f"Case {case_id}":
            case_title = f"Legal Case {case_id} - Supreme Court Judgment"
        
        result = {
            "id": case_id,
            "file_name": f"{case_id}.txt",
            "source": source,
            "title": case_title,
            "judges": metadata.get("judges", "Not available"),
            "date": metadata.get("date", "Not available"),
            "summary": metadata.get("summary", "Legal case summary not available"),
            "pdf_path": f"{case_id}.pdf",
            "summary_path": f"{case_id}.txt"
        }
        
        print(f"✅ Successfully processed case {case_id}: {case_title}")
        return result
        
    except Exception as e:
        print(f"Error processing document metadata: {e}")
        return None

@app.post("/chat_init")
async def initialize_chat_session(request: ChatInitRequest):
    """Initialize chat session with pre-built FAISS index"""
    try:
        case_id = request.case_id.strip()
        
        # Check if pre-built FAISS index exists
        if not vector_store_exists(case_id):
            raise HTTPException(
                status_code=404, 
                detail=f"FAISS index not found for case {case_id}. Please ensure indexes are pre-built."
            )
        
        return {
            "status": "ready", 
            "message": "Chat initialized successfully with pre-built index",
            "case_id": case_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")

@app.post("/chat_query")
async def handle_chat_query(request: ChatMessageRequest):
    """Handle chat query for initialized session"""
    try:
        case_id = request.case_id.strip()
        question = request.question.strip()
        
        if not question:
            raise HTTPException(status_code=400, detail="Question cannot be empty")
        
        if not vector_store_exists(case_id):
            raise HTTPException(
                status_code=404, 
                detail="Chat session not initialized. Call /chat_init first."
            )
        
        answer = query_vector_store(question, case_id)
        
        return {
            "case_id": case_id,
            "question": question,
            "answer": answer
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat query failed: {str(e)}")

@app.get("/cases/{case_id}")
async def get_case_details(case_id: str):
    """Get complete case details"""
    try:
        case_data = get_case_metadata(case_id.strip())
        
        if not case_data:
            raise HTTPException(status_code=404, detail="Case not found")
        
        return {
            "id": case_data["id"],
            "title": case_data.get("title", case_data.get("file_name", f"Case {case_data['id']}")),
            "judges": case_data.get("judges", "Not available"),
            "date": case_data.get("date", "Not available"),
            "summary": case_data.get("summary", "Legal case summary not available")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get case details: {str(e)}")

@app.get("/health")
async def health_check():
    """Comprehensive health check"""
    try:
        # Check Qdrant connection
        qdrant_status = "healthy" if qdrant and qdrant_client else "unhealthy"
        
        # Check file system
        text_dir_exists = os.path.exists(TEXT_FILE_DIR)
        faiss_dir_exists = os.path.exists(FAISS_INDEX_BASE)
        
        return {
            "status": "healthy",
            "components": {
                "qdrant": qdrant_status,
                "text_directory": "healthy" if text_dir_exists else "missing",
                "faiss_directory": "healthy" if faiss_dir_exists else "missing"
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")
    
@app.get("/cases")
async def get_all_cases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Get all cases with pagination"""
    try:
        cases = DatabaseManager.get_all_cases(limit=limit, offset=offset)
        total_count = DatabaseManager.get_cases_count()
        
        return {
            "cases": cases,
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve cases: {str(e)}")

@app.get("/search/database")
async def search_database(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50)
):
    """Search cases in database by text"""
    try:
        start_time = time.time()
        results = DatabaseManager.search_cases(q, limit=limit)
        response_time = time.time() - start_time
        
        # Log search
        DatabaseManager.log_search(q, len(results), response_time)
        
        return {
            "query": q,
            "results": results,
            "count": len(results),
            "response_time": response_time
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/analytics/search")
async def get_search_analytics():
    """Get search analytics from your database"""
    try:
        analytics = DatabaseManager.get_search_analytics()
        popular_queries = DatabaseManager.get_popular_queries()
        
        return {
            "analytics": analytics,
            "popular_queries": popular_queries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")

@app.get("/cases/by-judge/{judge_name}")
async def get_cases_by_judge(judge_name: str):
    """Use your existing query function"""
    try:
        from db.query_metadata import search_cases_by_judge
        results = search_cases_by_judge(judge_name)
        
        # Convert to dict format
        formatted_results = []
        for row in results:
            formatted_results.append({
                "id": row[0],
                "file_name": row[1], 
                "case_number": row[2],
                "petitioner": row[3],
                "respondent": row[4],
                "date": row[5],
                "judges": row[6],
                "acts_referred": row[7],
                "summary": row[8],
                "file_path": row[9]
            })
        
        return {
            "judge": judge_name,
            "cases": formatted_results,
            "count": len(formatted_results)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Judge search failed: {str(e)}")

@app.get("/api/groq-status")
async def groq_status():
    """Monitor Groq API usage"""
    async with groq_rate_limiter.lock:
        now = datetime.now()
        # Count requests in last minute
        recent_requests = [
            req for req in groq_rate_limiter.requests 
            if now - req < timedelta(minutes=1)
        ]
        
        return {
            "requests_last_minute": len(recent_requests),
            "max_requests_per_minute": groq_rate_limiter.max_requests,
            "remaining_requests": max(0, groq_rate_limiter.max_requests - len(recent_requests)),
            "rate_limit_active": len(recent_requests) >= groq_rate_limiter.max_requests
        }

if __name__ == "__main__":
    import uvicorn
    
    print(f"🚀 Starting Kanoon Legal Search API on {HOST}:{PORT}")
    print(f"📊 Environment: {ENVIRONMENT}")
    print(f"🔗 Access URL: http://{HOST}:{PORT}")
    print(f"🌐 Frontend URL: {FRONTEND_URL}")
    
    uvicorn.run(
        app, 
        host=HOST, 
        port=PORT,
        reload=(ENVIRONMENT == "development"),  # Enable reload only in development
        log_level="info"
    )
