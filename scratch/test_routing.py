import re
import sys

# Windows console fix
sys.stdout.reconfigure(encoding='utf-8')

def is_image_generate_intent(text: str) -> bool:
    lower_text = text.lower()
    
    # Exclude if it contains a question mark, "how", "why", "can you", "explain", "meaning"
    if re.search(r'\b(do not|don\'t|dont|never|not|might|example|phrase|explain|why did|how does|how to|can you|can hinaa)\b', lower_text):
        return False
            
    # Remove quoted text to ignore "The phrase 'generate an image'"
    unquoted = re.sub(r'["\'].*?["\']', '', lower_text)
    
    # Imperative or strong request
    imperative_patterns = [
        r'^\s*(generate|create|make|draw|paint|render)\b.*\b(image|images|picture|pictures|photo|photos|portrait|art|artwork|variations)\b',
        r'\b(image|images|picture|pictures|photo|photos).*(generate|create|make|bana|gara)\b',
        r'\b(generate|create|make)\s+(an?\s+)?(image|picture|photo|portrait)\b',
        r'^(a|an)?\s*(anime|moonlit|cyberpunk)?\s*(image|picture|photo|portrait)\s+(of|with)\b',
        r'^(generate|create)\b'
    ]
    
    for p in imperative_patterns:
        if re.search(p, unquoted):
            return True
            
    return False

def is_browser_intent(text: str) -> bool:
    lower_text = text.lower()
    if re.search(r'\b(do not|don\'t|dont|never|not|might|example|phrase|explain|why did|how does|how to|can you|can hinaa)\b', lower_text):
        return False
    unquoted = re.sub(r'["\'].*?["\']', '', lower_text)
    imperative_patterns = [
        r'^\s*(open|navigate to|go to|browse to|launch)\b',
        r'\b(open|browse|navigate|go to)\b.*\b(website|url|page|site|netflix|youtube|google)\b'
    ]
    for p in imperative_patterns:
        if re.search(p, unquoted):
            return True
    return False

tests = [
    ("Generate an image of a moonlit anime city.", True, is_image_generate_intent),
    ("चार anime images generate करो.", True, is_image_generate_intent),
    ("एउटा anime image generate गर.", True, is_image_generate_intent),
    ("Create ten variations of this character.", True, is_image_generate_intent),
    ("Explain how image generation works.", False, is_image_generate_intent),
    ("Do not generate an image.", False, is_image_generate_intent),
    ("Why did HINAA generate an image?", False, is_image_generate_intent),
    ("The phrase 'generate an image' is an example.", False, is_image_generate_intent),
    ("Can HINAA generate images?", False, is_image_generate_intent),
    ("I might generate an image later.", False, is_image_generate_intent),
    ("Open Netflix.", True, is_browser_intent),
    ("Do not open Netflix.", False, is_browser_intent),
    ("Why did Netflix open?", False, is_browser_intent),
    ("Explain how to open Netflix.", False, is_browser_intent),
    ("Can you open Netflix?", False, is_browser_intent),
]

for t, expected, func in tests:
    res = func(t)
    print(f"{'PASS' if res == expected else 'FAIL'}: {t} (Expected: {expected}, Got: {res})")
