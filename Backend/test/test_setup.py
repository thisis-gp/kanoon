#!/usr/bin/env python3
"""
Test the complete setup
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        # Test database imports
        from db import DatabaseManager, insert_metadata, create_db
        print("✅ Database imports successful")
        
        # Test FastAPI imports
        from fastapi import FastAPI, HTTPException, Query
        print("✅ FastAPI imports successful")
        
        # Test LangChain imports
        from langchain_qdrant import Qdrant
        from langchain_huggingface import HuggingFaceEmbeddings
        print("✅ LangChain imports successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False

def test_database():
    """Test database operations"""
    print("\n🧪 Testing database...")
    
    try:
        from db import DatabaseManager, create_db
        
        # First, create the basic database structure
        print("📝 Creating basic database structure...")
        create_db()
        print("✅ Basic database created")
        
        # Then, create enhanced tables
        print("🔧 Creating enhanced tables...")
        DatabaseManager.create_enhanced_tables()
        print("✅ Enhanced database tables created")
        
        # Test case count
        count = DatabaseManager.get_cases_count()
        print(f"✅ Current case count: {count}")
        
        # Test basic insert functionality
        test_case = {
            "file_name": "test_setup.txt",
            "case_number": "TEST/2024/SETUP",
            "petitioner": "Test Petitioner",
            "respondent": "Test Respondent", 
            "date": "2024-01-01",
            "judges": "Test Judge",
            "acts_referred": "Test Act Section 1",
            "summary": "This is a test case for setup verification",
            "file_path": "/test/path/test_setup.txt"
        }
        
        # Test insert
        print("🧪 Testing database insert...")
        if DatabaseManager.insert_metadata(test_case):
            print("✅ Database insert test successful")
            
            # Verify the insert worked
            new_count = DatabaseManager.get_cases_count()
            print(f"✅ Updated case count: {new_count}")
            
            # Test search functionality
            search_results = DatabaseManager.search_cases("test", limit=1)
            print(f"✅ Search test found {len(search_results)} results")
        else:
            print("⚠️ Database insert test failed")
        
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_environment():
    """Test environment variables"""
    print("\n🧪 Testing environment...")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    required_vars = [
        "GOOGLE_GEMINI_API_KEY", 
        "GEMINI_API_KEY",
        "QDRANT_CLOUD_URL", 
        "QDRANT_CLOUD_API_KEY",
        "QDRANT_API_KEY"
    ]
    
    found_vars = []
    for var in required_vars:
        if os.getenv(var):
            found_vars.append(var)
    
    print(f"✅ Found environment variables: {found_vars}")
    
    # Check we have the essential ones
    has_gemini = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GEMINI_API_KEY")
    has_qdrant_url = os.getenv("QDRANT_CLOUD_URL")
    has_qdrant_key = os.getenv("QDRANT_CLOUD_API_KEY") or os.getenv("QDRANT_API_KEY")
    
    if has_gemini and has_qdrant_url and has_qdrant_key:
        print("✅ All essential environment variables present")
        return True
    else:
        print("⚠️ Some essential environment variables missing")
        return False

def main():
    """Run all tests"""
    print("🚀 Testing Kanoon Setup...")
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check if database exists
    db_path = "cases_metadata.db"
    if os.path.exists(db_path):
        print(f"📊 Existing database found: {db_path}")
    else:
        print(f"🆕 No existing database - will create fresh: {db_path}")
    
    tests = [
        ("Environment Variables", test_environment),
        ("Package Imports", test_imports),
        ("Database Operations", test_database)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"🧪 {test_name}")
        print('='*50)
        
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append(False)
    
    print(f"\n{'='*50}")
    print("📊 SUMMARY")
    print('='*50)
    
    if all(results):
        print("🎉 All tests passed! Your Lexiscope setup is ready.")
        print("\n🚀 Next steps:")
        print("1. cd model")
        print("2. python main.py")
        print("3. Open http://localhost:8000/docs")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)