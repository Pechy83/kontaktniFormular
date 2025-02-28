import sqlite3
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mail import Mail, Message
from dotenv import load_dotenv
import os
from flask_xcaptcha import XCaptcha
from flask import Flask, render_template

# ✅ Načtení proměnných z .env souboru
load_dotenv()

# ✅ Inicializace aplikace Flask
app = Flask(__name__, static_folder='static')
CORS(app)

# ✅ Konfigurace Flask-XCaptcha
app.config.update(
    XCAPTCHA_SITE_KEY='6LfTReMqAAAAAJa5oyYSVMAO8rzDb_C4iClD4tMt',
    XCAPTCHA_SECRET_KEY='6LfTReMqAAAAAOtY5mjv02tCWQgjMZ1I5l2ky6XI'
)
xcaptcha = XCaptcha(app)

# ✉️ Konfigurace Flask-Mail (Gmail SMTP)
app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER")
app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT"))
app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS") == "True"
app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
app.config["MAIL_DEFAULT_SENDER"] = os.getenv("MAIL_DEFAULT_SENDER")

mail = Mail(app)

# 📌 Vytvoření databáze, pokud neexistuje
def init_db():
    with sqlite3.connect("contacts.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
init_db()

# ✅ Validace e-mailu
def is_valid_email(email):
    return re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email)

# ✅ Validace telefonního čísla
def is_valid_phone(phone):
    return re.match(r"^\+420\d{9}$|^\d{9}$", phone)

# 🌱 Pomocné funkce pro odpovědi
def success_response(message):
    return jsonify({"success": True, "message": message}), 200

def error_response(message, status_code=400):
    return jsonify({"success": False, "error": message}), status_code

# 📤 Endpoint pro odeslání formuláře
@app.route('/submit_form', methods=['POST'])
def submit_form():
    try:
        data = request.json

        # Získání hodnot a jejich oříznutí od mezer
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()

        # Kontrola, zda nejsou prázdné
        if not name or not email or not phone or not message:
            return error_response("Všechna pole jsou povinná!")

        # Ověření e-mailu
        if not is_valid_email(email):
            return error_response("Neplatná e-mailová adresa!")

        # Ověření telefonního čísla
        if not is_valid_phone(phone):
            return error_response("Neplatné telefonní číslo!")

        # 📌 Uložení zprávy do databáze
        with sqlite3.connect("contacts.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (name, email, phone, message) VALUES (?, ?, ?, ?)",
                           (name, email, phone, message))
            conn.commit()

        # ✉️ Odeslání e-mailu
        try:
            msg = Message("Nová zpráva z kontaktního formuláře",
                          recipients=[os.getenv("MAIL_USERNAME")])
            msg.body = f"Jméno: {name}\nEmail: {email}\nTelefon: {phone}\n\nZpráva:\n{message}"
            mail.send(msg)
        except Exception as mail_error:
            return jsonify({"success": False, "error": "Zpráva byla uložena, ale e-mail se nepodařilo odeslat.", "mail_error": str(mail_error)}), 500

        return success_response("Zpráva byla úspěšně odeslána a e-mail doručen!")

    except Exception as e:
        return error_response(str(e), 500)

# ✅ endpoint pro reCAPTCHA
@app.route('/submit', methods=['POST'])
def submit():
    if xcaptcha.verify():
        # reCAPTCHA byla úspěšně ověřena
        return success_response("reCAPTCHA byla úspěšně ověřena!")
    else:
        # reCAPTCHA ověření selhalo
        return error_response("Ověření reCAPTCHA selhalo!")

@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)