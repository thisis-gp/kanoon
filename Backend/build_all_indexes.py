#!/usr/bin/env python3
"""
Script to pre-build all FAISS indexes for cases
This should be run once during deployment to avoid quota issues
"""
import os
import sys
import time
from pathlib import Path

# Add the model directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

load_dotenv()

# Initialize HuggingFace embeddings (same as Qdrant for consistency)
# Using all-MiniLM-L6-v2 - 384 dimensions, same as Qdrant
embeddings_hf = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)

# Configuration
TEXT_FILE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "supreme_court_cleaned_texts")
FAISS_INDEX_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index")

def vector_store_exists(case_id: str) -> bool:
    """Check if FAISS vector store exists for case"""
    index_dir = os.path.join(FAISS_INDEX_BASE, case_id)
    return os.path.exists(os.path.join(index_dir, "index.faiss"))

def create_vector_store(case_id: str, text: str) -> str:
    """Create FAISS vector store for case"""
    index_path = os.path.join(FAISS_INDEX_BASE, case_id)
    
    if vector_store_exists(case_id):
        return index_path
    
    # Split text into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=10000, 
        chunk_overlap=1000
    )
    chunks = text_splitter.split_text(text)
    
    print(f"  📊 Created {len(chunks)} chunks for case {case_id}")
    
    # Create vector store with HuggingFace embeddings (no API limits)
    try:
        vector_store = FAISS.from_texts(chunks, embedding=embeddings_hf)
        print(f"  ✅ Successfully created embeddings for case {case_id}")
    except Exception as e:
        print(f"  ❌ Error creating embeddings for case {case_id}: {e}")
        raise e
    
    os.makedirs(index_path, exist_ok=True)
    vector_store.save_local(index_path)
    
    return index_path

def build_all_indexes():
    """Build FAISS indexes for all cases"""
    print("🚀 Starting to build FAISS indexes for all cases...")
    
    # Get all text files
    text_files = list(Path(TEXT_FILE_DIR).glob("*.txt"))
    print(f"📁 Found {len(text_files)} text files")
    
    built_count = 0
    skipped_count = 0
    error_count = 0
    
    for i, text_file in enumerate(text_files, 1):
        case_id = text_file.stem  # Get filename without extension
        
        print(f"\n[{i}/{len(text_files)}] Processing case {case_id}")
        
        # Check if index already exists
        if vector_store_exists(case_id):
            print(f"⏭️  Index already exists for case {case_id}, skipping...")
            skipped_count += 1
            continue
        
        try:
            # Read the text file
            with open(text_file, 'r', encoding='utf-8') as f:
                text = f.read()
            
            if not text.strip():
                print(f"⚠️  Empty file: {text_file}")
                error_count += 1
                continue
            
            print(f"📄 Building index for case {case_id} ({len(text)} characters)")
            
            # Create vector store with rate limiting
            create_vector_store(case_id, text)
            built_count += 1
            
            # No delay needed with HuggingFace embeddings (local processing)
            
            print(f"✅ Successfully built index for case {case_id}")
            
        except Exception as e:
            print(f"❌ Error building index for case {case_id}: {e}")
            error_count += 1
            
            # If it's a quota error, wait longer
            if "429" in str(e) or "quota" in str(e).lower():
                print("⏳ Quota exceeded, waiting 60 seconds...")
                time.sleep(60)
    
    print(f"\n🎉 Index building completed!")
    print(f"✅ Built: {built_count}")
    print(f"⏭️  Skipped: {skipped_count}")
    print(f"❌ Errors: {error_count}")
    
    # Show deployment info
    print(f"\n🚀 FAISS indexes ready for deployment!")
    print(f"📁 Index location: {FAISS_INDEX_BASE}")
    print(f"📊 Total size: {get_directory_size(FAISS_INDEX_BASE):.1f} MB")
    print(f"💾 AWS Free Tier: 30GB storage (plenty of space)")

def get_directory_size(path):
    """Get total size of directory in MB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # Convert to MB

if __name__ == "__main__":
    build_all_indexes()
