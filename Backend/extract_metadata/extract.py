import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import time
import json
from google import genai
from google.genai import types
from db.insert_metadata import insert_metadata
from dotenv import load_dotenv
import re

# Load environment variables from .env file
load_dotenv()

# Input folder with text files
INPUT_FOLDER = "supreme_court_cleaned_texts"

# Prompt for metadata extraction
METADATA_PROMPT = """
You are a legal metadata extraction assistant.
Task: Extract metadata from the following text.
Return JSON with the following keys:
case_title
petitioner
respondent
judges
decision_date
citations
outcome
court

If a field is not available, put null.
Return only valid JSON, no extra text.
"""

# Rate limit configs
REQUESTS_PER_MIN = 10
DELAY = 60 / REQUESTS_PER_MIN  # 6 seconds per request



def safe_parse_json(text, filename):
    """
    Extract and parse JSON safely from model output.
    """
    # Remove Markdown code fences if present
    cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    
    try:
        return json.loads(cleaned)
    except Exception as e:
        print(f"⚠️ Still failed parsing JSON for {filename}: {e}")
        print("Raw response was:\n", text[:500], "...")  # show preview
        return None

def extract_metadata_from_file(client, filepath, filename):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()

    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=METADATA_PROMPT + "\n\n" + text)],
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=0,
        thinking_config=types.ThinkingConfig(thinking_budget=-1),
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=generate_content_config,
    )

    # Parse JSON response safely
    metadata = safe_parse_json(response.text.strip(), filename)
    if not metadata:
        print(f"⚠️ JSON parse failed for {filename}")
        return None

    # Add extra fields for DB
    metadata["file_name"] = filename
    metadata["file_path"] = filepath
    return metadata

# ---------- Main ----------

def main():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    for idx, filename in enumerate(os.listdir(INPUT_FOLDER)):
        if filename.endswith(".txt"):
            filepath = os.path.join(INPUT_FOLDER, filename)
            print(f"📂 Processing {filepath} ...")

            try:
                metadata = extract_metadata_from_file(client, filepath, filename)
                if metadata:
                    insert_metadata(metadata)
                    print(f"✅ Inserted metadata for {filename}")
            except Exception as e:
                print(f"❌ Error processing {filename}: {e}")

        if idx + 1 < len(os.listdir(INPUT_FOLDER)) - 1:
            time.sleep(DELAY)  # Rate limiting
            
    print("🎉 Metadata extraction + SQLite insertion completed.")

if __name__ == "__main__":
    main()
