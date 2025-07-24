from flask import Flask, flash, session,render_template, request, redirect, session, jsonify, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
import traceback
import vertexai
from datetime import datetime, UTC
from werkzeug.utils import secure_filename
from voice_matcher import enroll_user, identify_user
from pydub import AudioSegment
from pathlib import Path
from vertexai.generative_models import GenerativeModel
from google.cloud import translate_v2 as translate
from google.generativeai.types import GenerationConfig
from dotenv import load_dotenv
#from google import genai
from google.genai.types import HttpOptions

os.environ['GOOGLE_CLOUD_PROJECT']='my-voice-auth-demo-001'
os.environ['GOOGLE_CLOUD_LOCATION']='us-central1'
os.environ['GOOGLE_GENAI_USE_VERTEXAI']='True'
os.environ["GOOGLE_API_KEY"] = "AIzaSyDHr5sdvOWlSNUIQlV4O-u6oYtdSLy3Nnk"


#os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:/Users/Nikhil_PC/Downloads/Service_key.JSON"
translate_client = translate.Client()

config = GenerationConfig(
            temperature=0.3,
            top_k=20,
            top_p=0.7
        )
import json
import re

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY")

# Load API key from environment variable
genai.configure(api_key=("AIzaSyDHr5sdvOWlSNUIQlV4O-u6oYtdSLy3Nnk"))
model = genai.GenerativeModel("gemini-1.5-pro")

# Database config from environment
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}

# Path to store .wav files
UPLOAD_FOLDER = "uploads"
Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    print(f"[DB] Opened connection: {conn}")
    return conn

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password_hash = generate_password_hash(request.form["password"])

        # Convert DOB string to date
        dob_str = request.form.get("DOB")
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date() if dob_str else None

        profile_data = (
            username,
            password_hash,
            request.form.get("name"),
            request.form.get("gender"),
            dob,
            request.form.get("marital_status"),
            request.form.get("num_dependents"),
            request.form.get("spouse_name"),
            request.form.get("preferred_Language"),
            request.form.get("employer_name"),
            request.form.get("job_title"),
            request.form.get("annual_income"),
            request.form.get("Other_Income"),
            request.form.get("Bank_Balance"),
            request.form.get("Emergency_Fund"),
            request.form.get("Car_Value"),
            request.form.get("House_Value"),
            request.form.get("Other_Assets"),
            request.form.get("Employer_Benefit_401k_Percentage"),
            request.form.get("Annual_Employer_Pension"),
            request.form.get("Auto_Loan"),
            request.form.get("Personal_Loan"),
            request.form.get("Student_Loan"),
            request.form.get("Credit_Cards_Outstanding"),
            request.form.get("credit_score"),
            request.form.get("Investments_in_Crypto"),
            request.form.get("Investments_in_Brokerage"),
            request.form.get("Tax_Bracket"),
            request.form.get("Monthly_Expenses")
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO user_profile (
                           username, password_hash, name, gender, DOB, marital_status, num_dependents,
                           spouse_name, preferred_Language, employer_name, job_title, annual_income, Other_Income,
                           Bank_Balance, Emergency_Fund, Car_Value, House_Value, Other_Assets,
                           Employer_Benefit_401k_Percentage, Annual_Employer_Pension,
                           Auto_Loan, Personal_Loan, Student_Loan, Credit_Cards_Outstanding,
                           credit_score, Investments_in_Crypto, Investments_in_Brokerage, Tax_Bracket, Monthly_Expenses
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, profile_data)
        conn.commit()
        conn.close()
        flash("Registration successful! Please log in.")
        return redirect("/login")
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_profile WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["chat_history"] = []
            return redirect("/dashboard")
        else:
            return "Invalid credentials", 401
    return render_template("login.html")

@app.route("/onboarding", methods=["GET", "POST"])
def onboarding_page():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        audio = request.files.get("audio_data")

        if not username or not password or not audio:
            return "Missing required fields", 400

        # Verify user
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM user_profile WHERE username = %s", (username,))
        user = cursor.fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return "Invalid credentials", 401

        try:
            # Save audio + enroll
            filename = secure_filename(f"{username}_{datetime.now(UTC).timestamp()}.wav")
            raw_path = os.path.join(UPLOAD_FOLDER, f"raw_{filename}")
            audio.save(raw_path)

            converted_path = os.path.join(UPLOAD_FOLDER, filename)
            sound = AudioSegment.from_file(raw_path)
            sound = sound.set_channels(1).set_frame_rate(16000)
            sound.export(converted_path, format="wav")

            enroll_user(converted_path, username)
            os.remove(raw_path)

            return render_template("onboarding.html", success=True)

        except Exception as e:
            print("Error in enroll_user:", str(e))
            traceback.print_exc()
            return f"Voice enrollment failed: {str(e)}", 500

    return render_template("onboarding.html")

@app.route("/voice-login", methods=["POST"])
def voice_login():
    audio = request.files.get("audio_data")
    if not audio:
        return jsonify({"success": False, "error": "No audio uploaded"}), 400

    try:
        # Save raw upload
        timestamp = datetime.now(UTC).timestamp()
        filename = secure_filename(f"login_{timestamp}.wav")
        raw_path = os.path.join(UPLOAD_FOLDER, f"raw_{filename}")
        audio.save(raw_path)

        # Convert to WAV mono, 16kHz
        converted_path = os.path.join(UPLOAD_FOLDER, filename)
        sound = AudioSegment.from_file(raw_path)
        sound = sound.set_channels(1).set_frame_rate(16000)
        sound.export(converted_path, format="wav")

        # Voice identification
        username, score, success = identify_user(converted_path)

        # Clean up raw file
        os.remove(raw_path)
        if os.path.exists(converted_path):
            os.remove(converted_path)

        if success:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM user_profile WHERE username = %s", (username,))
            user = cursor.fetchone()
            conn.close()

            if user:
                session["user_id"] = user["id"]
                session["chat_history"] = []
                return jsonify({"success": True, "redirect": "/dashboard"})
            else:
                return jsonify({"success": False, "error": "User not found"}), 404
        else:
            return jsonify({"success": False, "error": "Voice not recognized"}), 401

    except Exception as e:
        import traceback
        print("Error in voice-login:", str(e))
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_profile WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return "User not found", 404

    return render_template("dashboard.html", user=user)


def calculate_derived_fields(user):
    #dob = datetime.strptime(user['DOB'], "%Y/%m/%d")
    dob = user['DOB']
    today = datetime.today()
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    total_income = user['annual_income'] + user['Other_Income']
    total_savings = user['Bank_Balance'] + user['Emergency_Fund']
    asset_value = user['Car_Value'] + user['House_Value'] + user['Other_Assets']
    loans = user['Auto_Loan'] + user['Personal_Loan'] + user['Student_Loan'] + user['Credit_Cards_Outstanding']
    employer_benefit_income = 0.01 * user['annual_income'] * user['Employer_Benefit_401k_Percentage']
    annual_employer_pension = user['Annual_Employer_Pension']

    return {
        'Age': age,
        'Gender': user['gender'],
        'Marital_Status': user['marital_status'],
        'Total_Income': total_income,
        'Total_Savings': total_savings,
        'Asset_Value': asset_value,
        'Loans': loans,
        'Investments': user['Investments_in_Crypto'] + user['Investments_in_Brokerage'],
        'Tax_Bracket': user['Tax_Bracket'],
        'Monthly_Expenses': user['Monthly_Expenses'],
        'Employer_Benefit_Income': employer_benefit_income + annual_employer_pension,
        'Preferred_Language': user['preferred_Language']
    }
def translate_to_en(text):
    translation = translate_client.translate(text, target_language="en")
    return translation["translatedText"], translation["detectedSourceLanguage"]

def translate_from_en(text, target_language):
    translation = translate_client.translate(text, target_language=target_language)
    return translation["translatedText"]


def extract_json_from_gemini_response(response):
    """
    Extract and parse JSON from Gemini model response that may include markdown formatting.
    """
    try:
        # Extract raw content text from response
        text = response.text.strip()

        # Remove code fences (e.g., ```json ... ```)
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except Exception as e:
        print("[ERROR] Failed to parse JSON from Gemini response:", e)
        return {}

def extract_json_from_gemini_response(response):
    """
    Extract and parse JSON from Gemini model response that may include markdown formatting.
    """
    try:
        # Extract raw content text from response
        text = response.text.strip()

        # Remove code fences (e.g., ```json ... ```)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except Exception as e:
        print("[ERROR] Failed to parse JSON from Gemini response:", e)
        return {}



def extract_json_from_gemini_response(response):
    """
    Extract and parse JSON from Gemini model response that may include markdown formatting.
    """
    try:
        # Extract raw content text from response
        text = response.text.strip()

        # Remove code fences (e.g., ```json ... ```)
        if text.startswith("```"):
            text = re.sub(r"^```(json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except Exception as e:
        print("[ERROR] Failed to parse JSON from Gemini response:", e)
        return {}

def extract_json_from_gemini_response(response):
    """
    Extract and parse JSON from Gemini model response that may include markdown formatting.
    """
    try:
        # Extract raw content text from response
        text = response.text.strip()

        # Remove code fences (e.g., ```json ... ```)
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except Exception as e:
        print("[ERROR] Failed to parse JSON from Gemini response:", e)
        return {}


@app.route("/ask", methods=["POST"])
def ask():
    if "user_id" not in session:
        print("[ASK] Unauthorized access attempt.")
        return jsonify({"response": "Unauthorized"}), 401

    prompt = request.json.get("prompt")
    
    # Detect intent using Gemini
    intent_prompt = f"""
    Classify the user’s intent based on their message.

    Categories:
    - financial_advice
    - update_user_details

    Respond in JSON like this:
    {{ "intent": "update_user_details" }}

    User message: \"\"\"{prompt}\"\"\"
    """
    intent_response = model.generate_content(intent_prompt)
    #intent_data = extract_json_from_gemini_response(intent_response)
    print("[INTENT] intent_response is", intent_response)
    print("[INTENT] supposed to be getting intent")
    #print("[INTENT] intent_data", intent_data)

    try:
        #intent_data = json.loads(intent_response.text)
        intent_data = extract_json_from_gemini_response(intent_response)
        print("[INTENT] intent_data", intent_data)
        intent = intent_data.get("intent")
        print("[INTENT] intent", intent)
    except Exception as e:
        print("[ASK] Failed to parse intent response:", e)
        intent = None

    print(f"[ASK] Received prompt: {prompt!r}")
    session.setdefault("chat_history", [])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_profile WHERE id = %s", (session["user_id"],)) #THIS LINE IS IMPORTANT
    user = cursor.fetchone()
    #print(f"[ASK] Loaded user profile for user_id={session['user_id']}: {user}")
    conn.close()

    # Call the calculate_derived_fields function here
    derived = calculate_derived_fields(user)
    #print(f"[ASK] Derived fields: {derived}")

    #context = f"""
#User Profile:
#Name: {user['name']}
#Annual Income: ${user['annual_income']}
#Credit Score: {user['credit_score']}
#Employer: {user['employer_name']} | Job Title: {user['job_title']}
 #   """
    context = f"""
Name: {user['name']}
Gender: {derived['Gender']}
Age: {derived['Age']}
Marital Status: {derived['Marital_Status']}
Preferred Language: {derived['Preferred_Language']}
Total Income: ${derived['Total_Income']:,}
Total Savings: ${derived['Total_Savings']:,}
Asset Value: ${derived['Asset_Value']:,}
Loans: ${derived['Loans']:,}
Employer Benefits: ${derived['Employer_Benefit_Income']:,}
Investments: ${derived['Investments']:,}
Tax Bracket: {derived['Tax_Bracket']}%
Monthly Expenses: ${derived['Monthly_Expenses']:,}
"""
    conversation = "\n".join(session["chat_history"])
    print(f"[ASK] Current conversation history:\n{conversation}")

    if intent == "update_user_details":
        print("[INTENT] has been successful")
        sql_prompt = f"""
        You are an assistant that extracts user account update information and generates parameterized SQL queries.

        The user is updating their financial profile stored in the `user_profile` table. The user may want to update **one or multiple fields** in a single request. Detect all fields mentioned in the user message and include them all in the update.

        Here are the allowed columns:
        - name
        - gender
        - marital_status
        - annual_income
        - Other_Income
        - Bank_Balance
        - Emergency_Fund
        - Car_Value
        - House_Value
        - Other_Assets
        - Auto_Loan
        - Personal_Loan
        - Student_Loan
        - Credit_Cards_Outstanding
        - Employer_Benefit_401k_Percentage
        - Annual_Employer_Pension
        - Investments_in_Crypto
        - Investments_in_Brokerage
        - Tax_Bracket
        - Monthly_Expenses
        - preferred_Language
        - DOB
        - credit_score
        - employer_name
        - job_title
        

        Output valid JSON like:
        {{
        "fields": {{
            "annual_income": "85000",
            "preferred_Language": "English"
        }},
        "sql": "UPDATE user_profile SET annual_income = %s, preferred_Language = %s WHERE id = %s;"
        }}

        User message: \"\"\"{prompt}\"\"\"
        Assume user_id = {session['user_id']}
        Only include fields that are mentioned in the user request. If multiple fields are mentioned, update them all in a single SQL statement using %s placeholders..
        """

        sql_response = model.generate_content(sql_prompt)
        print("sql_response", sql_response)

        try:
            #update_data = json.loads(sql_response.text)
            update_data = extract_json_from_gemini_response(sql_response)
            print("update_data", update_data)
            fields = update_data.get("fields", {})
            sql = update_data.get("sql", "")
            print(f"[ASK] SQL to execute: {sql} with fields {fields}")

            if sql and fields:
                conn = get_db_connection()
                cursor = conn.cursor()
                values = list(fields.values()) + [session["user_id"]]
                print("values", values)
                num_placeholders = sql.count('?')
                print("num_placeholders",num_placeholders)
                cursor.execute(sql, values)
                conn.commit()
                conn.close()
                return jsonify({
                    "response": f"Your profile has been updated: {', '.join(fields.keys())}.",
                    "suggestions": ["Change my phone number", "Update address", "What’s my tax bracket?"]
                })
        except Exception as e:
            print("[ASK] Failed to parse or execute SQL:", e)

    translated_input, source_lang = translate_to_en(prompt)
    prompt_en = translated_input

    conciseness_instruction = (
        "Respond concisely and directly to the user's question. "
        "Do not provide lengthy or generic explanations. "
        "If the user asks for more details, only then elaborate."
    )

    if not session["chat_history"]:
        full_prompt = (
            f"{context}\n\n"
            f"{conciseness_instruction}\n"
            "You are a financial coach that offers personalized guidance and recommendations based on user profiles, financial goals, and real-time insights. "
            "You should be accessible across all age groups, adapting to different financial systems and cultural contexts.\n\n"
            "Based on this, provide financial insights and suggestions(only if user asks) to improve this user's financial health. "
            "Recommend ways to reduce loans, improve investments, and better utilize employer benefits. "
            "Offer suggestions tailored to the current user profile. Use clear formatting.\n\n"
            f"User: {prompt_en}"
        )
    else:
        conversation = "\n".join(session["chat_history"])
        full_prompt = (
            f"{context}\n\n"
            f"Conversation so far:\n{conversation}\n\n"
            f"User: {prompt_en}\n"
        )
    chat_history = session.get("chat_history", [])
    print(f"[ASK] Chat History:\n{chat_history}")
    context_prompt = "\n".join(chat_history + [f"User: {full_prompt}", "AI:"])

    print(f"[ASK] Full prompt to model:\n{context_prompt}")
    response = model.generate_content(context_prompt)
    final_reply = translate_from_en(response.text, source_lang)
    print(f"[ASK] AI:Model response: {final_reply!r}")

    # Update session memory
    #session["chat_history"].append(f"User: {full_prompt}")
    #session["chat_history"].append(f"AI: {final_reply}")
    chat_history.append(f"User: {full_prompt}")
    chat_history.append(f"AI: {final_reply}")
    session["chat_history"] = chat_history
    print(f"[ASK] Updated chat_history: {session['chat_history']}")


    return jsonify({
        "response": final_reply,
        "suggestions": ["What can I do to increase savings?", "How to improve credit score?", "Can I afford a loan?"]
    })

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
def home():
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)