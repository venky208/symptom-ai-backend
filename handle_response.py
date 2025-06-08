from typing import Dict, List, Tuple
import re

# Greetings and response mapping
GREETINGS = {
    'casual': ["hi", "hey", "what's up", "yo"],
    'formal': ["hello", "good morning", "good afternoon", "good evening"],
    'polite': ["greetings", "how do you do", "pleasure to meet you"]
}

# Keywords to track for symptom analysis
TRACKED_KEYWORDS = {
    'symptoms': [],
    'severity': ['high', 'medium', 'low'],
    'time': ['day', 'week', 'month', 'year', 'ago']
}

# Temporary storage for user keywords
user_keywords = {
    'current_user': {
        'symptoms': [],
        'severity': None,
        'time': None,
        'other': []
    }
}

def handle_greeting(message: str) -> Tuple[str, bool]:
    """Handle different types of greetings with appropriate responses"""
    message_lower = message.lower()
    
    # Match greetings only as whole words
    for greeting_type, greetings in GREETINGS.items():
        for greeting in greetings:
            pattern = rf"\b{re.escape(greeting)}\b"
            if re.search(pattern, message_lower):
                if greeting_type == 'casual':
                    return "Hey there! How can I help with your symptoms today?", True
                elif greeting_type == 'formal':
                    return "Hello! I'm here to assist with your health concerns.", True
                else:  # polite
                    return "Greetings! I'm ready to help analyze your symptoms.", True
    return "", False

def track_keywords(user_id: str, message: str, current_phase: str) -> None:
    """Track and store relevant keywords from user messages"""
    message_lower = message.lower()
    
    # Track symptoms
    symptom_words = [word for word in message_lower.split() 
                     if word in TRACKED_KEYWORDS['symptoms']]
    user_keywords[user_id]['symptoms'].extend(symptom_words)
    
    # Track severity if in severity phase
    if current_phase == 'severity':
        for level in TRACKED_KEYWORDS['severity']:
            if re.search(rf"\b{level}\b", message_lower):
                user_keywords[user_id]['severity'] = level
                break
    
    # Track time references
    time_words = [word for word in message_lower.split()
                  if any(time_word in word for time_word in TRACKED_KEYWORDS['time'])]
    if time_words:
        user_keywords[user_id]['time'] = ' '.join(time_words)
    
    # Track other keywords not matching our categories
    if not (symptom_words or time_words or 
            any(re.search(rf"\b{level}\b", message_lower) for level in TRACKED_KEYWORDS['severity'])):
        user_keywords[user_id]['other'].append(message)

def handle_unrelated_input(message: str) -> str:
    """Handle inputs not related to symptoms or analysis"""
    return "I'm designed to help with symptom prediction. Please describe your symptoms."

def get_response(user_id: str, message: str, current_phase: str) -> Tuple[str, str]:
    """
    Main function to handle all responses
    Returns: (response_message, next_phase)
    """
    # Track keywords first
    track_keywords(user_id, message, current_phase)
    
    # Handle greetings
    greeting_response, is_greeting = handle_greeting(message)
    if is_greeting:
        return greeting_response, current_phase
    
    # Handle unrelated inputs
    if current_phase == 'symptoms' and not any(
        word in message.lower() for word in TRACKED_KEYWORDS['symptoms']
    ):
        return handle_unrelated_input(message), current_phase
    
    # Default case - let brain.py handle phase-specific logic
    return "", current_phase

def normalize_input(text: str) -> str:
    return re.sub(r'\s+', '', text).lower()
