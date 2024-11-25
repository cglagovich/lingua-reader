from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import json
import httpx
from datetime import datetime, timedelta

app = FastAPI()

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Ensure our data directories exist
os.makedirs("data/texts", exist_ok=True)
os.makedirs("data/vocab", exist_ok=True)

# Initialize or load vocabulary list
VOCAB_FILE = "data/vocab/vocabulary.json"
if not os.path.exists(VOCAB_FILE):
    with open(VOCAB_FILE, "w") as f:
        json.dump([], f)

# Update vocabulary structure
def init_word_data(word, translation):
    return {
        "word": word,
        "translation": translation,
        "easiness_factor": 2.5,
        "interval": 0,
        "repetition_count": 0,
        "last_review_date": None,
        "next_review_date": datetime.now().isoformat(),
    }

@app.get("/")
async def home(request: Request):
    # Get list of uploaded texts
    texts = os.listdir("data/texts")
    return templates.TemplateResponse("index.html", {"request": request, "texts": texts})

@app.post("/upload")
async def upload_file(file: UploadFile):
    # Save uploaded file
    file_path = f"data/texts/{file.filename}"
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)
    return {"filename": file.filename}

@app.get("/text/{filename}")
async def get_text(filename: str):
    with open(f"data/texts/{filename}", "r") as f:
        content = f.read()
    return {"content": content}

@app.post("/vocab")
async def add_vocab(word: str = Form(...)):
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    
    # Check if word exists
    existing_words = [item["word"] if isinstance(item, dict) else item for item in vocab_list]
    if word not in existing_words:
        # Get translation using existing get_translation function
        translations = get_translation(word)
        word_data = init_word_data(word, translations)
        vocab_list.append(word_data)
        
        with open(VOCAB_FILE, "w") as f:
            json.dump(vocab_list, f)
    
    return {"status": "success"}

@app.get("/vocab")
async def get_vocab():
    # Return vocabulary list
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    # Extract just the words from vocab objects
    word_list = [item["word"] if isinstance(item, dict) else item for item in vocab_list]
    return {"vocab": word_list}

@app.delete("/vocab/{word}")
async def delete_vocab(word: str):
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    
    print(f'deleting {word} from {vocab_list}')
    # Find and remove word by matching the word field in vocab objects
    for item in vocab_list:
        if isinstance(item, dict) and item["word"] == word:
            vocab_list.remove(item)
            print(f'new list: {vocab_list}')
            with open(VOCAB_FILE, "w") as f:
                json.dump(vocab_list, f)
            return {"status": "success"}
    
    return {"status": "error", "message": "Word not found in vocabulary"}

@app.post("/load-url")
async def load_url(url: str = Form(...)):
    print(f'loading url: {url}')
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text
            
            # Generate a filename from the URL
            filename = url.split('/')[-1] or 'url-text.txt'
            filepath = os.path.join("data/texts", filename)  # Changed TEXTS_DIR to "data/texts"
            
            # Save the content
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return {"filename": filename, "content": content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get('/api/translate/de-en/{word}')
async def translate_german_to_english(word: str):
    """
    API endpoint to translate German word to English
    
    Args:
        word (str): German word to translate
        
    Returns:
        dict: Response containing translations and status
    """
    try:
        translations = get_translation(word)
        
        if translations:
            return {
                'success': True,
                'word': word,
                'translations': translations
            }
        else:
            return {
                'success': False,
                'word': word,
                'error': 'No translation found',
                'translations': []
            }, 404
            
    except Exception as e:
        return {
            'success': False,
            'word': word,
            'error': str(e),
            'translations': []
        }, 500
    
def get_translation(german_word, dict_path='data/dict/de-en.txt'):
    """
    Get English translation(s) for a German word
    
    Args:
        german_word (str): German word to translate
        dict_path (str): Path to dictionary file
        
    Returns:
        list: List of English translations from all matching entries
    """
    try:
        all_translations = []
        with open(dict_path, 'r', encoding='utf-8') as f:
            for line in f:
                # Skip comments and empty lines
                if line.startswith('#') or not line.strip():
                    continue
                    
                # Split into German and English parts
                parts = line.strip().split('::')
                if len(parts) != 2:
                    continue
                    
                german_part, english_part = parts
                
                # Split German variants (separated by ;)
                german_terms = [term.strip() for term in german_part.split(';')]
                
                # Remove grammatical markers and context tags
                clean_terms = []
                for term in german_terms:
                    # Remove content in curly braces like {m}, {f}, {n}, {pl}
                    term = ' '.join(word for word in term.split() if not (word.startswith('{') and word.endswith('}')))
                    # Remove content in square brackets like [med.], [tech.]
                    term = ' '.join(word for word in term.split() if not (word.startswith('[') and word.endswith(']')))
                    # Remove variants after |
                    term = term.split('|')[0].strip()
                    clean_terms.append(term)
                
                # Check if search word matches any German term
                if german_word in clean_terms:
                    # Get English translations (split by ;)
                    translations = [t.strip() for t in english_part.split(';')]
                    # Remove variants after |
                    translations = [t.split('|')[0].strip() for t in translations]
                    all_translations.extend(translations)
                    
        return all_translations  # Return all found translations
        
    except FileNotFoundError:
        print(f"Dictionary file not found: {dict_path}")
        return []
    except Exception as e:
        print(f"Error reading dictionary: {e}")
        return []

# Add new endpoints for spaced repetition
@app.get("/api/review/due")
async def get_due_reviews():
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    
    now = datetime.now()
    due_words = [
        word for word in vocab_list 
        if isinstance(word, dict) and 
        word.get("next_review_date") and 
        datetime.fromisoformat(word["next_review_date"]) <= now
    ]
    
    return {"due_words": due_words}

@app.post("/api/review/submit")
async def submit_review(word: str = Form(...), quality: int = Form(...)):
    if quality not in range(6):  # 0 to 5
        raise HTTPException(status_code=400, detail="Quality must be between 0 and 5")
        
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    
    # Find and update the word
    for item in vocab_list:
        if isinstance(item, dict) and item["word"] == word:
            # Apply SM-2 algorithm
            if quality >= 3:
                if item["repetition_count"] == 0:
                    item["interval"] = 1
                elif item["repetition_count"] == 1:
                    item["interval"] = 6
                else:
                    item["interval"] *= item["easiness_factor"]
                
                item["repetition_count"] += 1
            else:
                item["interval"] = 1
                item["repetition_count"] = 0
            
            # Update easiness factor
            item["easiness_factor"] += (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
            item["easiness_factor"] = max(1.3, item["easiness_factor"])
            
            # Update dates
            item["last_review_date"] = datetime.now().isoformat()
            next_review = datetime.now() + timedelta(days=int(item["interval"]))
            item["next_review_date"] = next_review.isoformat()
            
            break
    
    with open(VOCAB_FILE, "w") as f:
        json.dump(vocab_list, f)
    
    return {"status": "success"}

@app.get("/review")
async def review_page(request: Request):
    return templates.TemplateResponse("review.html", {"request": request})

@app.get("/api/review/stats")
async def get_review_stats():
    try:
        with open(VOCAB_FILE, "r") as f:
            vocab_list = json.load(f)
            
        total_words = len(vocab_list)
        mastered_words = sum(1 for word in vocab_list 
                           if word["easiness_factor"] >= 2.5 and word["repetition_count"] >= 3)
        learning_words = total_words - mastered_words
        
        # Calculate average recall (from last review of each word)
        reviews_count = sum(1 for word in vocab_list if word["last_review_date"])
        if reviews_count > 0:
            avg_recall = round(sum(word["easiness_factor"] for word in vocab_list 
                                 if word["last_review_date"]) / reviews_count, 1)
        else:
            avg_recall = 0
            
        return {
            "total_words": total_words,
            "mastered_words": mastered_words,
            "learning_words": learning_words,
            "avg_recall": avg_recall,
            "words_due_today": sum(1 for word in vocab_list 
                if word.get("next_review_date") and 
                datetime.fromisoformat(word["next_review_date"]) <= datetime.now())
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "total_words": 0,
            "mastered_words": 0,
            "learning_words": 0,
            "avg_recall": 0,
            "words_due_today": 0
        }

@app.get("/vocab-manager")
async def vocab_manager(request: Request):
    return templates.TemplateResponse("vocab_manager.html", {"request": request})

@app.get("/api/vocab/all")
async def get_all_vocab():
    try:
        with open(VOCAB_FILE, "r") as f:
            vocab_list = json.load(f)
        return vocab_list
    except (FileNotFoundError, json.JSONDecodeError):
        return []

@app.post("/api/vocab/edit")
async def edit_vocab(
    old_word: str = Form(...),
    new_word: str = Form(...),
    translation: str = Form(...)
):
    with open(VOCAB_FILE, "r") as f:
        vocab_list = json.load(f)
    
    # Find and update the word
    for item in vocab_list:
        if item["word"] == old_word:
            item["word"] = new_word
            item["translation"] = translation.split(", ")
            break
    
    with open(VOCAB_FILE, "w") as f:
        json.dump(vocab_list, f)
    
    return {"status": "success"}

@app.get("/api/vocab/practice")
async def get_practice_words():
    """Get all words for practice mode, shuffled"""
    try:
        with open(VOCAB_FILE, "r") as f:
            vocab_list = json.load(f)
        # Shuffle the list for random practice
        import random
        vocab_list = random.sample(vocab_list, len(vocab_list))
        print(f'practice words: {vocab_list}')
        return {"due_words": vocab_list}
    except (FileNotFoundError, json.JSONDecodeError):
        return {"due_words": []}

