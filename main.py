from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
from datetime import datetime
import re
from typing import Optional
from handle_response import get_response, user_keywords

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with Netlify domain for security: ["https://your-app.netlify.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load data files
with open('symptoms.json') as f:
    symptoms_data = json.load(f)
    from handle_response import TRACKED_KEYWORDS
    TRACKED_KEYWORDS['symptoms'] = [symptom.lower() for symptom in symptoms_data['symptoms']]

with open('database.json') as f:
    disease_data = json.load(f)

# Initialize user data storage
try:
    with open('user_data.json', 'r') as f:
        user_data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    user_data = {}

def save_user_data():
    with open('user_data.json', 'w') as f:
        json.dump(user_data, f, indent=2)

class ChatRequest(BaseModel):
    message: str
    phase: str
    user_id: Optional[str] = "current_user"

def parse_time_input(time_str: str) -> Optional[int]:
    time_str = time_str.lower().strip()
    days_match = re.search(r'(\d+)\s*days?', time_str)
    if days_match:
        return int(days_match.group(1))
    weeks_match = re.search(r'(\d+)\s*weeks?', time_str)
    if weeks_match:
        return int(weeks_match.group(1)) * 7
    try:
        symptom_date = datetime.strptime(time_str, '%Y-%m-%d')
        return (datetime.now() - symptom_date).days
    except ValueError:
        return None

def get_severity(duration_days: int) -> str:
    if duration_days >= 45:
        return "🔴 High severity: Symptoms ongoing for over 1.5 months."
    elif duration_days >= 30:
        return "🟠 Medium severity: Symptoms ongoing for over 1 month."
    else:
        return "🟢 Low severity: Symptoms ongoing for less than 1 month."

def predict_disease(symptoms_text: str) -> list:
    symptoms = [s.strip().lower() for s in re.split(',|and', symptoms_text.lower())]
    symptoms = [s for s in symptoms if s.strip()]
    
    disease_matches = []
    for disease in disease_data['diseases']:
        common_symptoms = [s.lower() for s in disease['symptoms']]
        matched = [s for s in symptoms if s in common_symptoms]
        if matched:
            match_percentage = (len(matched) / len(common_symptoms)) * 100
            disease_matches.append({
                'name': disease['name'],
                'match_percentage': round(match_percentage, 1),
                'description': disease['description'],
                'recommendation': disease['recommendation'],
                'matched_symptoms': matched
            })
    return sorted(disease_matches, key=lambda x: x['match_percentage'], reverse=True)[:3]

def normalize_input(text: str) -> str:
    return re.sub(r'\W+', '', text.lower())

@app.post("/chat")
async def chat(chat_request: ChatRequest):
    try:
        user_message = chat_request.message.strip()
        current_phase = chat_request.phase
        user_id = chat_request.user_id

        print(f"📩 Incoming request from {user_id} in phase {current_phase}: {user_message}")
        
        response, next_phase = get_response(user_id, user_message, current_phase)

        if not response:
            if user_id not in user_data:
                user_data[user_id] = {
                    'symptoms': '',
                    'time': '',
                    'severity': '',
                    'additional_info': '',
                    'other_data': []
                }

            if current_phase == 'symptoms':
                if any(word in user_message.lower() for word in TRACKED_KEYWORDS['symptoms']):
                    user_data[user_id]['symptoms'] = user_message
                    response = "When did you notice these symptoms? (e.g., '3 days ago')"
                    next_phase = 'time'
                else:
                    response = "I need symptoms to help you. Please describe how you're feeling."

            elif current_phase == 'time':
                days = parse_time_input(user_message)
                if days is not None:
                    severity = get_severity(days)
                    user_data[user_id]['time'] = user_message
                    user_data[user_id]['severity'] = severity
                    response = f"{severity}\nHow would you rate the severity? (High/Medium/Low)"
                    next_phase = 'severity'
                elif any(word in user_message.lower() for word in TRACKED_KEYWORDS['symptoms']):
                    user_data[user_id]['symptoms'] += f", {user_message}"
                    response = "Added symptom. When did symptoms start? (e.g., '3 days ago')"
                else:
                    response = "Please enter when symptoms started (e.g., '2 days ago')"

            elif current_phase == 'severity':
                if user_keywords[user_id]['severity']:
                    user_data[user_id]['severity_rating'] = user_keywords[user_id]['severity']
                    response = "Is there anything else? Type 'prediction' for analysis."
                    next_phase = 'final'
                else:
                    response = "Please choose: High, Medium, or Low severity"

            elif current_phase == 'final':
                normalized_input = normalize_input(user_message)

                if 'prediction' in normalized_input:
                    matches = predict_disease(user_data[user_id]['symptoms'])
                    if not matches:
                        response = "❌ No matching conditions found."
                    else:
                        response = "🔍 Possible conditions:\n\n" + "\n\n".join( 
                            f"{i}. 🏥 {m['name']} ({m['match_percentage']}%)\n"
                            f"   📝 {m['description']}\n"
                            f"   💊 {m['recommendation']}\n"
                            f"   ✅ Matching symptoms: {', '.join(m['matched_symptoms'])}"
                            for i, m in enumerate(matches, 1)
                        ) + "\n\n⚠️ Consult a healthcare professional."

                elif 'mydata' in normalized_input:
                    response = (
                        "📋 Your information:\n"
                        f"🤒 Symptoms: {user_data[user_id]['symptoms']}\n"
                        f"⏰ Onset: {user_data[user_id]['time']}\n"
                        f"⚠️ Severity: {user_data[user_id]['severity']}\n"
                        f"📝 Additional info: {user_data[user_id]['additional_info'].replace('hi', '')}"
                    )
                else:
                    response = "Type 'prediction' for analysis or 'my data' to review."

        save_user_data()
        print(f"✅ Response to {user_id}: {response}")
        return {"response": response, "nextPhase": next_phase}

    except Exception as e:
        print(f"❌ Error processing chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
