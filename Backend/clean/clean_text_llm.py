import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

# Initialize Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def clean_legal_text(text: str) -> str:
    prompt = f"""
    You are a legal text cleaner. 
    Clean the following judgment by:
    - Removing page numbers, headers, repetitive boilerplate
    - Preserving all actual case content (arguments, judgments, reasoning)
    - Return only the cleaned text, no explanation
    
    Judgment:
    {text}
    """
    response = client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )
    return response.text.strip()

if __name__ == "__main__":
    input_folder = "supreme_court_cleaned_texts"
    output_folder = "cleaned/"

    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):
        if filename.endswith(".txt"):
            with open(os.path.join(input_folder, filename), "r", encoding="utf-8") as f:
                raw_text = f.read()

            cleaned_text = clean_legal_text(raw_text)

            with open(os.path.join(output_folder, filename), "w", encoding="utf-8") as f:
                f.write(cleaned_text)

            print(f"✅ Cleaned: {filename}")
