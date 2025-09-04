import re
import os

def clean_legal_text(text: str) -> str:
    """Specialized cleaner for Indian legal documents"""
    
    # Remove case headers and references (keep only first meaningful occurrence)
    text = re.sub(r'2024 INSC \d+', '', text)
    text = re.sub(r'(NON[\s-]?REPORTABLE|REPORTABLE|Non-reportable)', '', text, flags=re.IGNORECASE)
    
    # Remove page numbers and headers
    text = re.sub(r'Page \d+ of \d+', '', text)
        
    # Keep the first occurrence of case headers but remove duplicates
    case_patterns = [
        r'CIVIL APPEAL NO\.?\s*\d+\s*OF\s*\d+',
        r'CRIMINAL APPEAL NO\.?\s*\d+\s*OF\s*\d+',
        r'SPECIAL LEAVE PETITION.*?NO\.?\s*\d+\s*OF\s*\d+'
    ]
    
    for pattern in case_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            first_match = matches[0].group(0)
            # Remove all occurrences
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
            # Reinsert the first one before "VERSUS" if it exists
            text = re.sub(r'(\n\s*)?VERSUS', f'{first_match}\n\nVERSUS', text, count=1)
    
    # Standardize VERSUS formatting
    text = re.sub(r'\n+VERSUS\n+', '\n\nVERSUS\n\n', text, flags=re.IGNORECASE)
    
    # Remove digital signature blocks completely - improved patterns
    text = re.sub(r'Digitally signed by.*?Signature Not Verified', '', text, flags=re.DOTALL)
    text = re.sub(r'Date:\s*\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}\s*IST\s*Reason:', '', text)
    text = re.sub(r'\d{4}\.\d{2}\.\d{2}\s*\d{2}:\d{2}:\d{2}\s*IST\s*Reason:', '', text)
    text = re.sub(r'Signature Not Verified.*', '', text)
    
    # Remove standalone names that are likely signatories (common Indian names after digital signature removal)
    signature_names = [
        r'\b[A-Z][a-z]+ [A-Z][a-z]+\s*\n\s*Date:',
        r'\b(SWETA BALODI|Anita Malhotra|Deepak Guglani|Narendra Prasad)\b'
    ]
    for pattern in signature_names:
        text = re.sub(pattern, '', text)
    
    # Remove various citation patterns - comprehensive legal citation patterns
    # AIR, SCC, MANU, JT, SCR, etc.
    text = re.sub(r'\d+\s+(AIR|SCC|SCR|JT|MANU)\s+[A-Z]*\s*\d+.*?\d*', '', text)
    text = re.sub(r'\d{4}\s+SCC OnLine\s+[A-Z]+\s+\d+', '', text)
    text = re.sub(r'\(\d{4}\)\s+\d+\s+SCC\s+\d+', '', text)
    
    # Remove "For short" abbreviations
    text = re.sub(r'For short,?\s*["""][^"""]*["""]\.?', '', text)
    
    # Remove standalone footnote numbers and isolated numbered lines
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\(\w+\)\s*$', '', text, flags=re.MULTILINE)
    
    # Remove common legal procedural phrases
    text = re.sub(r'\b(Per contra|Crl\.|arising out of)\b', '', text, flags=re.IGNORECASE)
    text = re.sub(r'@\s*[A-Z][A-Z\s]*', '', text)  # Remove @ followed by names/titles
    
    # Remove empty brackets and parentheses from OCR artifacts
    text = re.sub(r'\(\s*\)', '', text)
    text = re.sub(r'\[\s*\]', '', text)
    
    # Remove "J U D G M E N T" headers with spacing
    text = re.sub(r'J\s+U\s+D\s+G\s+M\s+E\s+N\s+T', 'JUDGMENT', text)
    text = re.sub(r'O\s+R\s+D\s+E\s+R', 'ORDER', text)
    
    # Clean up excessive punctuation and spacing artifacts
    text = re.sub(r'\.{3,}', '...', text)  # Normalize ellipses
    text = re.sub(r'[-_]{3,}', '', text)   # Remove long dashes/underscores
    
    # Remove case-specific artifacts like "(D) TH. LRS" (deceased through legal representatives)
    text = re.sub(r'\(D\)\s*TH\.\s*LRS\.?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'…(APPELLANT|RESPONDENT)\(S\)', '', text)
    
    # Standardize judge and court formatting
    text = re.sub(r'PRESENT:\s*\n+', 'JUDGES:\n', text, flags=re.IGNORECASE)
    text = re.sub(r'HON[\'"]BLE\s+MR?S?\.?\s+JUSTICE', 'Justice', text, flags=re.IGNORECASE)
    
    # Remove counsel representation sections (often verbose and repetitive)
    text = re.sub(r'For Petitioner\(s\):.*?(?=JUDGMENT)', '', text, flags=re.DOTALL|re.IGNORECASE)
    
    # Remove excessive whitespace and normalize - improved normalization
    text = re.sub(r'[ \t]+', ' ', text)  # Normalize horizontal whitespace
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)  # Remove excessive line breaks (preserve paragraph structure)
    text = re.sub(r'^\s*\n+', '', text)  # Remove leading newlines
    text = re.sub(r'\n+\s*$', '', text)  # Remove trailing newlines
    
    # Fix common formatting issues
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)  # Remove space before punctuation
    text = re.sub(r'([.!?])\s*\n\s*([a-z])', r'\1 \2', text)  # Fix broken sentences
    
    return text.strip()


def clean_text_files_in_folder(input_folder: str, output_folder: str):
    """Cleans text files in the input folder and saves them to the output folder."""
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
        print(f"Created output folder: {output_folder}")

    files_processed = 0
    files_with_errors = 0
    
    for filename in sorted(os.listdir(input_folder)):  # Sort for consistent processing
        if filename.endswith(".txt"):
            input_path = os.path.join(input_folder, filename)
            try:
                with open(input_path, 'r', encoding='utf-8') as f:
                    text = f.read()

                original_length = len(text)
                cleaned_text = clean_legal_text(text)
                cleaned_length = len(cleaned_text)

                output_path = os.path.join(output_folder, filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_text)
                
                files_processed += 1
                reduction_percent = ((original_length - cleaned_length) / original_length) * 100 if original_length > 0 else 0
                
                if files_processed % 50 == 0:  # Progress update every 50 files
                    print(f"Processed {files_processed} files...")
                    
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                files_with_errors += 1
    
    print(f"\nProcessing complete!")
    print(f"Files processed successfully: {files_processed}")
    print(f"Files with errors: {files_with_errors}")
    print(f"Output saved to: {output_folder}")


def test_cleaning_on_sample(input_folder: str, output_folder: str, sample_files: list = None):
    """Test cleaning on a small sample of files for demonstration."""
    
    if sample_files is None:
        sample_files = ['1.txt', '10.txt', '25.txt', '50.txt']
    
    if not os.path.exists(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return
    
    test_output = output_folder + '_test'
    if not os.path.exists(test_output):
        os.makedirs(test_output)
    
    print(f"Testing cleaning on sample files: {sample_files}")
    
    for filename in sample_files:
        input_path = os.path.join(input_folder, filename)
        if os.path.exists(input_path):
            try:
                with open(input_path, 'r', encoding='utf-8') as f:
                    original_text = f.read()
                
                cleaned_text = clean_legal_text(original_text)
                
                output_path = os.path.join(test_output, filename)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_text)
                
                original_length = len(original_text)
                cleaned_length = len(cleaned_text)
                reduction = ((original_length - cleaned_length) / original_length) * 100
                
                print(f"{filename}: {original_length} → {cleaned_length} chars ({reduction:.1f}% reduction)")
                
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
        else:
            print(f"File {filename} not found in input folder")
    
    print(f"Test results saved to: {test_output}")


if __name__ == "__main__":
    input_folder = '../supreme_court_texts'
    output_folder = '../supreme_court_cleaned_texts'
    
    print("Starting legal document cleaning process...")
    print(f"Input folder: {input_folder}")
    print(f"Output folder: {output_folder}")
    
    # Test on sample files first to demonstrate improvements
    test_cleaning_on_sample(input_folder, output_folder)
    
    print("\nStarting full processing of all files...")
    clean_text_files_in_folder(input_folder, output_folder)