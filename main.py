import google.generativeai as genai
from datetime import datetime
import json
import re
import os

# Configure Gemini API
genai.configure(api_key=api)  # Replace with your actual API key
model = genai.GenerativeModel("gemini-1.5-flash")

# File path for memory storage in Colab
MEMORY_FILE = "/content/memory.json"  # Local Colab storage
# For Google Drive (uncomment and mount Drive if preferred):
# from google.colab import drive
# drive.mount('/content/drive')
# MEMORY_FILE = "/content/drive/MyDrive/memory.json"

# Initialize memory and keys
memory = []
all_keys = set()

# Load memory from file if it exists
def load_memory():
    global memory, all_keys
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            memory = json.load(f)
            # Rebuild all_keys from loaded memory
            for entry in memory:
                for key in entry["key_value_pairs"].keys():
                    all_keys.add(key.lower())
        print("Loaded memory from file.")
    else:
        memory = []
        all_keys = set()
        print("No memory file found, starting fresh.")

# Save memory to file
def save_memory():
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=4)
    print("Saved memory to file.")

def is_statement(input_text):
    prompt = f"""
    Analyze the following input and determine if it is a statement (to store) or a question (to query).
    Return "statement" if it is a statement, otherwise return "question".
    Input: "{input_text}"
    """
    response = model.generate_content(prompt)
    return response.text.strip().lower() == "statement"

def extract_key_value_pairs(input_text):
    prompt = f"""
    Analyze the following input and extract key-value pairs in a JSON-like format.
    Identify entities (e.g., names, activities, objects, times, relationships) and assign them appropriate keys.
    Be proactive in inferring meaningful context even if the input isn’t explicitly structured.
    Examples:
    - Input: "My name is Ganesh" → {{"name": "Ganesh"}}
    - Input: "I live in New York" → {{"location": "New York"}}
    - Input: "I play Free Fire with my friend Anil" → {{"game": "Free Fire", "friend": "Anil"}}
    - Input: "I am going to watch a movie today" → {{"activity": "watching a movie", "time": "today"}}
    - Input: "today i went to class" → {{"activity": "went to class", "time": "today"}}
    Return an empty dict {{}} only if no meaningful key-value pairs can be inferred.
    Input: "{input_text}"
    """
    response = model.generate_content(prompt)
    # print("Gemini response:", response.text)
    try:
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if match:
            key_value_str = match.group(0)
            key_value_str = key_value_str.replace("'", '"')
            return json.loads(key_value_str)
        return {}
    except Exception as e:
        print(f"Error parsing key-value pairs: {e}")
        return {}

def add_to_memory(input_text):
    key_value_pairs = extract_key_value_pairs(input_text)
    if key_value_pairs:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        memory.append({
            "timestamp": timestamp,
            "input": input_text,
            "key_value_pairs": key_value_pairs
        })
        for key in key_value_pairs. keys():
            all_keys.add(key.lower())
        save_memory()  # Save to file after adding
        return True
    return False

def find_related_memory(input_text):
    prompt = f"""
    Analyze the following input and determine which keys from the list are relevant.
    Consider that questions about location ("where") might relate to activities or times that imply a place.
    Available keys: {", ".join(all_keys)}
    Return the keys as a comma-separated list.
    Examples:
    - Input: "where am I" with keys name, activity, time → activity, time (if activity implies a place)
    - Input: "what am I doing" with keys name, activity, time → activity
    Input: "{input_text}"
    """
    response = model.generate_content(prompt)
    # print("Relevant keys from Gemini:", response.text)
    relevant_keys = [key.strip().lower() for key in response.text.split(",")]

    related_info = []
    for entry in memory:
        for key, value in entry["key_value_pairs"].items():
            if key.lower() in relevant_keys:
                related_info.append(f"{key}: {value} (from '{entry['input']}' on {entry['timestamp']})")
    return related_info

def handle_input(input_text):
    input_text = input_text.replace("iam", "I am")  # Fix common typo
    related_info = find_related_memory(input_text)
    related_str = "\n".join(related_info) if related_info else "No related info found in memory."

    if is_statement(input_text):
        stored = add_to_memory(input_text)
        action_str = "I’ve stored that for you." if stored else "I couldn’t extract anything to store."
        prompt = f"""
        The user said: "{input_text}"
        Related info from memory:
        {related_str}
        Generate a natural language response to the user's input, incorporating the related info if available.
        """
        response = model.generate_content(prompt)
        return f"{response.text}"
    else:
        prompt = f"""
        The user asked: "{input_text}"
        Related info from memory:
        {related_str}
        Generate a natural language response to the user's question, incorporating the related info if available.
        If the question is about location ("where"), infer a possible place from activities or times if no direct location is stored.
        If no relevant info is found, admit the limitation but offer a helpful response.
        Current date: {datetime.now().strftime("%Y-%m-%d")}
        """
        response = model.generate_content(prompt)
        return response.text

# Load memory at the start
load_memory()

# Main loop
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye!")
        break
    response = handle_input(user_input)
    print("Bot:", response)
    # print("Memory:", memory)
    # print("All Keys:", all_keys)
