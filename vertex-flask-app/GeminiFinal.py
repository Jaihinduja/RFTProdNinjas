from flask import Flask, render_template, request, redirect, session, jsonify, url_for
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import google.generativeai as genai
import os
from datetime import datetime
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Load API key from environment variable
genai.configure(api_key=("AIzaSyDHr5sdvOWlSNUIQlV4O-u6oYtdSLy3Nnk"))
model = genai.GenerativeModel("gemini-1.5-pro")

# Database config from environment
DB_CONFIG = {
    "host": "104.197.224.109",
    "user": os.getenv("DB_USER", "flask_user"),
    "password": os.getenv("DB_PASSWORD", "test123"),
    "database": os.getenv("DB_NAME", "user_profiles_db")
}

def get_db_connection():
    conn = mysql.connector.connect(**DB_CONFIG)
    print(f"[DB] Opened connection: {conn}")
    return conn

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        profile_data = (
            username, password,
            request.form.get("name"),
            request.form.get("age"),
            request.form.get("gender"),
            request.form.get("location"),
            request.form.get("marital_status"),
            request.form.get("num_dependents"),
            request.form.get("spouse_name"),
            request.form.get("annual_income"),
            request.form.get("credit_score"),
            request.form.get("existing_loans"),
            request.form.get("savings_balance"),
            request.form.get("employment_status"),
            request.form.get("employer_name"),
            request.form.get("job_title"),
            request.form.get("years_of_experience")
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO users (
                           username, password_hash, name, age, gender, location,
                           marital_status, num_dependents, spouse_name, annual_income,
                           credit_score, existing_loans, savings_balance,
                           employment_status, employer_name, job_title, years_of_experience
                       ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                       """, profile_data)
        conn.commit()
        conn.close()
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

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_profile WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    conn.close()
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

@app.route("/ask", methods=["POST"])
def ask():
    if "user_id" not in session:
        print("[ASK] Unauthorized access attempt.")
        return jsonify({"response": "Unauthorized"}), 401

    prompt = request.json.get("prompt")
    print(f"[ASK] Received prompt: {prompt!r}")
    session.setdefault("chat_history", [])

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM user_profile WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    print(f"[ASK] Loaded user profile for user_id={session['user_id']}: {user}")
    conn.close()

    # Call the calculate_derived_fields function here
    derived = calculate_derived_fields(user)
    print(f"[ASK] Derived fields: {derived}")

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
    if not session["chat_history"]:
        full_prompt = (
            f"{context}\n\n"
            "You are a financial coach that offers personalized guidance and recommendations based on user profiles, financial goals, and real-time insights. "
            "You should be accessible across all age groups, adapting to different financial systems and cultural contexts.\n\n"
            "Based on this, provide detailed financial insights and suggestions to improve this user's financial health. "
            "Recommend ways to reduce loans, improve investments, and better utilize employer benefits. "
            "Offer suggestions tailored to the current income, age, and expenses. Use clear formatting.\n\n"
            f"User: {prompt}\nAI:"
        )
    else:
        conversation = "\n".join(session["chat_history"])
        full_prompt = (
            f"{context}\n\n"
            f"Conversation so far:\n{conversation}\n\n"
            f"User: {prompt}\nAI:"
        )

    print(f"[ASK] Full prompt to model:\n{full_prompt}")
    response = model.generate_content(full_prompt)
    print(f"[ASK] Model response: {response.text!r}")

    # Update session memory
    session["chat_history"].append(f"User: {prompt}")
    session["chat_history"].append(f"AI: {response.text}")
    print(f"[ASK] Updated chat_history: {session['chat_history']}")

    return jsonify({
        "response": response.text,
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