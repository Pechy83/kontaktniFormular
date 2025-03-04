import os
import re
import sqlite3

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from flask_mail import Mail, Message
from flask_xcaptcha import XCaptcha
from whitenoise import WhiteNoise
from datetime import datetime
import requests

# ✅ Načtení proměnných z .env souboru
load_dotenv()

# ✅ Inicializace aplikace Flask
app = Flask(__name__)
CORS(app)

# ✅ Konfigurace Flask-XCaptcha
app.config.update(
    XCAPTCHA_SITE_KEY=os.getenv("RECAPTCHA_SITE_KEY"),
    XCAPTCHA_SECRET_KEY=os.getenv("RECAPTCHA_SECRET_KEY")
)
xcaptcha = XCaptcha(app)

# API klíč a Place ID z environmentálních proměnných
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PLACE_ID = os.getenv("PLACE_ID")

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
        return jsonify({"success": True, "message": "reCAPTCHA byla úspěšně ověřena!"}), 200
    else:
        print("❌ reCAPTCHA ověření selhalo!")  # Debug info do logu
        return jsonify({"success": False, "message": "Ověření reCAPTCHA selhalo!"}), 400

@app.route('/')
def index():
    return render_template('index.html')

# Konfigurace WhiteNoise
app.wsgi_app = WhiteNoise(app.wsgi_app, root='static/')
app.wsgi_app.add_files('js/', prefix='js/')
app.wsgi_app.add_files('images/', prefix='images/')

mail_port = os.getenv("MAIL_PORT")
if mail_port:
    app.config["MAIL_PORT"] = int(mail_port)
else:
    app.config["MAIL_PORT"] = 587  # Výchozí port

#rezence z Google

@app.route('/reviews', methods=['GET'])
def get_reviews():
    # Kontrola, zda jsou API klíč a PLACE_ID nastaveny
    if not GOOGLE_API_KEY or not PLACE_ID:
        return jsonify({"error": "Chybí API klíč nebo PLACE ID"}), 500
    # Sestavení URL pro Google Places API
    url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={PLACE_ID}&fields=name,reviews,rating&key={GOOGLE_API_KEY}"

    try:
        # Odeslání GET požadavku
        response = requests.get(url)
        data = response.json()

        # Kontrola, jestli je odpověď správná
        if response.status_code != 200:
            return jsonify({"error": "Chyba při načítání dat z Google Places API"}), response.status_code

        # Zpracování recenzí
        if "result" in data and "reviews" in data["result"]:
            reviews = [
                {
                    "author": review["author_name"],
                    "text": review["text"],
                    "rating": review["rating"],
                    "date": datetime.datetime.utcfromtimestamp(review.get("time", 0)).strftime('%Y-%m-%d %H:%M:%S')
                }
                for review in data["result"]["reviews"]
            ]
            return jsonify(reviews)

        return jsonify({"error": "No reviews found"}), 404

    except requests.exceptions.RequestException as e:
        # Chyby spojené s požadavkem
        return jsonify({"error": f"Chyba sítě: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)