from flask import Flask, request, redirect, url_for, send_file
import pandas as pd
import pytz
import re
import os

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    if file.filename == '':
        return redirect(request.url)
    if file and file.filename.endswith('.csv'):
        filepath = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(filepath)
        cleaned_filepath = process_csv(filepath)
        return send_file(cleaned_filepath, as_attachment=True)
    return redirect(request.url)

def process_csv(filepath):
    df = pd.read_csv(filepath)

    # Convert the 'Time' column to datetime
    df['Time'] = pd.to_datetime(df['Time'])

    # Convert the 'Time' column to Pacific Time
    utc = pytz.utc
    pacific = pytz.timezone('America/Los_Angeles')
    df['Time'] = df['Time'].apply(lambda x: x.replace(tzinfo=utc).astimezone(pacific))

    # Format the 'Time' column
    df['Time'] = df['Time'].dt.strftime('%a, %b %d, %Y %I:%M %p')

    # cleaning code here
    df['Name'] = df['Por favor indique su nombre completo'].combine_first(df['Please enter your full name'])
    df['Phone numbers'] = df['Por favor proporcione su número de teléfono*'].combine_first(df['Please type your phone number.'])
    df['Email'] = df['What is your email address?'].combine_first(df['¿Ingrese su correo electrónico?'])
    df_cleaned = df[['Time', 'Name', 'Phone numbers', 'Email']]
    # df_cleaned = df_cleaned[df_cleaned['Completed'] != 'No']

    def clean_us_number(phone):
        phone = str(phone)
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if re.match(r'^\+1\d{10}$', cleaned_phone):
            return cleaned_phone
        elif re.match(r'^\+11\d{10}$', cleaned_phone):
            return '+1' + cleaned_phone[3:]
        return None

    df_cleaned['Phone numbers'] = df_cleaned['Phone numbers'].apply(lambda x: clean_us_number(x) if pd.notna(x) else x)
    df_cleaned = df_cleaned.dropna(subset=['Phone numbers', 'Email', 'Name'], how='all')
    df_cleaned = df_cleaned[df_cleaned['Phone numbers'].apply(lambda x: re.match(r'^\+1\d{10}$', str(x)) is not None)]
    df_cleaned = df_cleaned.drop_duplicates(subset=['Phone numbers'])

    def extract_name(text):
        if not isinstance(text, str):
            return text
        match = re.search(r'(Mi nombre es|Mi. Ombré es|Me llamo|Soy|My name is|I am|I\'m)\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑa-záéíóúñ]+)*)', text, re.IGNORECASE)
        if match:
            return match.group(2)
        match = re.search(r'\b(I am|I\'m)\s+([A-ZÁÉÍÓÚÑa-záéíóúñ]+(?: [A-ZÁÉÍÓÚÑa-záéíóúñ]+)*)', text, re.IGNORECASE)
        if match:
            return match.group(2)
        return text

    df_cleaned['Name'] = df_cleaned['Name'].apply(lambda x: extract_name(x) if extract_name(x) else x)

    def format_phone_number(phone):
        if pd.notna(phone) and re.match(r'^\+1\d{10}$', phone):
            return f"{phone[2:5]}-{phone[5:8]}-{phone[8:]}"
        return phone

    df_cleaned['Formatted Phone'] = df_cleaned['Phone numbers'].apply(format_phone_number)
    cleaned_filepath = os.path.join(PROCESSED_FOLDER, 'cleaned_' + os.path.basename(filepath))
    df_cleaned.to_csv(cleaned_filepath, index=False)
    return cleaned_filepath

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    # app.run(debug=True)
