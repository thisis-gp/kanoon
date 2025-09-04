import os
import time
from typing import List
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from langchain_qdrant import Qdrant
from langchain_community.document_loaders import DirectoryLoader
from langchain_huggingface import HuggingFaceEmbeddings  # Updated import
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

load_dotenv()

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
FILE_PATH = os.path.join(PROJECT_ROOT, "supreme_court_cleaned_texts")
QDRANT_CLOUD_URL = os.getenv("QDRANT_CLOUD_URL")  
QDRANT_API_KEY = os.getenv("QDRANT_CLOUD_API_KEY")
COLLECTION_NAME = "legal_documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 384 dimensions
VECTOR_SIZE = 384  # Dimension for all-MiniLM-L6-v2

def validate_environment():
    """Validate required environment variables"""
    if not QDRANT_CLOUD_URL:
        raise ValueError("❌ QDRANT_CLOUD_URL not found in environment variables")
    if not QDRANT_API_KEY:
        raise ValueError("❌ QDRANT_CLOUD_API_KEY not found in environment variables")
    if not os.path.exists(FILE_PATH):
        raise ValueError(f"❌ Document directory not found: {FILE_PATH}")
    
    print("✅ Environment validation passed")

def load_and_split_documents() -> List[Document]:
    """Load and split documents into chunks"""
    print(f"📁 Loading documents from: {FILE_PATH}")
    
    # Load documents
    loader = DirectoryLoader(
        FILE_PATH,
        glob="*.txt",  # Only load .txt files
        show_progress=True
    )
    docs = loader.load()
    print(f"📄 Loaded {len(docs)} documents")
    
    if not docs:
        raise ValueError(f"❌ No documents found in {FILE_PATH}")
    
    # Split documents into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,  # Increased overlap for better context
        length_function=len,
        is_separator_regex=False,
    )
    
    split_docs = text_splitter.split_documents(docs)
    print(f"📝 Split into {len(split_docs)} chunks")
    
    return split_docs

def initialize_embeddings() -> HuggingFaceEmbeddings:
    """Initialize embedding model"""
    print(f"🤖 Loading embedding model: {EMBEDDING_MODEL}")
    
    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL,
        model_kwargs={'device': 'cpu'},  # Use CPU for compatibility
        encode_kwargs={'normalize_embeddings': True}  # Normalize for better performance
    )
    
    print("✅ Embedding model loaded")
    return embeddings

def initialize_qdrant_client() -> QdrantClient:
    """Initialize and test Qdrant client connection"""
    print("🔗 Connecting to Qdrant Cloud...")
    
    client = QdrantClient(
        url=QDRANT_CLOUD_URL,
        api_key=QDRANT_API_KEY,
        prefer_grpc=False,
        check_compatibility=False
    )
    
    try:
        # Test connection
        collections = client.get_collections()
        print(f"✅ Connected to Qdrant. Found {len(collections.collections)} collections")
        return client
    except Exception as e:
        raise ConnectionError(f"❌ Failed to connect to Qdrant: {e}")

def create_collection_if_not_exists(client: QdrantClient):
    """Create collection if it doesn't exist"""
    try:
        client.get_collection(COLLECTION_NAME)
        print(f"✅ Collection '{COLLECTION_NAME}' already exists")
    except Exception:
        print(f"🔨 Creating collection '{COLLECTION_NAME}'...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=VECTOR_SIZE,
                distance=Distance.COSINE
            ),
        )
        print(f"✅ Collection '{COLLECTION_NAME}' created")

def insert_documents_to_qdrant(split_docs: List[Document], embeddings: HuggingFaceEmbeddings) -> Qdrant:
    """Insert documents into Qdrant with progress tracking"""
    print(f"🚀 Inserting {len(split_docs)} document chunks into Qdrant...")
    
    start_time = time.time()
    
    try:
        qdrant_collection = Qdrant.from_documents(
            documents=split_docs,
            embedding=embeddings,
            url=QDRANT_CLOUD_URL,
            api_key=QDRANT_API_KEY,
            collection_name=COLLECTION_NAME,
            force_recreate=False,  # Don't recreate if exists
        )
        
        elapsed_time = time.time() - start_time
        print(f"✅ Successfully inserted documents in {elapsed_time:.1f} seconds")
        print(f"⚡ Average: {elapsed_time/len(split_docs):.2f}s per document")
        
        return qdrant_collection
        
    except Exception as e:
        print(f"❌ Error inserting documents: {e}")
        raise

def verify_insertion(client: QdrantClient):
    """Verify that documents were inserted correctly"""
    try:
        collection_info = client.get_collection(COLLECTION_NAME)
        vector_count = collection_info.vectors_count or 0
        print(f"📊 Collection statistics:")
        print(f"   • Vectors: {vector_count}")
        print(f"   • Status: {collection_info.status}")
        
        if vector_count > 0:
            print("✅ Documents successfully indexed!")
        else:
            print("⚠️ No vectors found in collection")
            
    except Exception as e:
        print(f"⚠️ Could not verify insertion: {e}")


def main():
    """Main execution function"""
    try:
        print("🚀 Starting Qdrant document insertion process...")
        
        # Step 1: Validate environment
        validate_environment()
        
        # Step 2: Load and split documents
        split_docs = load_and_split_documents()
        
        # Step 3: Initialize Qdrant client
        client = initialize_qdrant_client()
        
        # Step 4: Create collection if needed
        create_collection_if_not_exists(client)
        
        # Step 5: Initialize embeddings
        embeddings = initialize_embeddings()
        
        # Step 6: Insert documents
        qdrant_collection = insert_documents_to_qdrant(split_docs, embeddings)
        
        # Step 7: Verify insertion
        verify_insertion(client)
        
        print("\n🎉 Document insertion completed successfully!")
        print(f"📋 Collection: {COLLECTION_NAME}")
        print(f"🔗 Qdrant URL: {QDRANT_CLOUD_URL}")
        
        return qdrant_collection
        
    except Exception as e:
        print(f"❌ Process failed: {e}")
        return None

if __name__ == "__main__":
    result = main()
    
    if result:
        print("\n✅ Ready for vector search operations!")
    else:
        print("\n❌ Setup incomplete. Please check errors above.")