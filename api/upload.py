from flask import Flask, request, jsonify
import PyPDF2
import re
import google.generativeai as genai
import json
import os
import csv

app = Flask(__name__)

# Configure Google Gemini API
genai.configure(api_key='AIzaSyCwdWwRAXv75Qjc7baDaV4iR6D8F95HZi4')  # Replace with your actual API key

# Define the upload and static folders
UPLOAD_FOLDER = '/tmp/uploads'  # Use /tmp for writable storage in Vercel
STATIC_FOLDER = '/tmp/static/mcqs'  # Use /tmp for static files

# Ensure folders exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

MCQ_JSON_PATH = os.path.join(UPLOAD_FOLDER, 'mcq.json')
MCQ_CSV_PATH = os.path.join(STATIC_FOLDER, 'mcqs.csv')  # Save CSV in the /tmp folder

# Step 1: Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    text = ''
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ''  # Ensure no NoneType error
        return text.strip()
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return None

# Step 2: Preprocess the Text
def preprocess_text(text):
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    text = re.sub(r'[^\w\s.]', '', text)  # Remove special characters except periods
    return text

# Step 3: Generate MCQs using Google Gemini
def generate_mcq(text, num_questions=5):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"Generate {num_questions} multiple-choice questions (MCQs) based on the following text:\n\n{text}\n\nFormat each question as:\nQ: [Question]\nA: [Correct Answer]\nB: [Option 1]\nC: [Option 2]\nD: [Option 3]"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error generating MCQs: {e}")
        return None

# Step 4: Parse and Format MCQs into JSON
def parse_mcq(mcq_text):
    questions = []
    lines = [line.strip() for line in mcq_text.split('\n') if line.strip()]  # Remove empty lines

    current_question = None
    options = []

    for line in lines:
        if line.startswith("Q:"):
            # If there's a previous question, save it before starting a new one
            if current_question and len(options) == 4:
                questions.append({
                    "question": current_question,
                    "options": options,
                    "correct_answer": options[0]  # Assuming first option is correct
                })
            # Start new question
            current_question = line.replace("Q: ", "").strip()
            options = []
        elif line.startswith(("A:", "B:", "C:", "D:")):
            options.append(line.split(": ", 1)[1].strip())  # Extract text after label

    # Save the last question
    if current_question and len(options) == 4:
        questions.append({
            "question": current_question,
            "options": options,
            "correct_answer": options[0]  # Assuming first option is correct
        })

    return questions

# Step 5: Save MCQs to JSON
def save_mcq_to_json(questions):
    try:
        with open(MCQ_JSON_PATH, 'w') as f:
            json.dump(questions, f, indent=4)
    except Exception as e:
        print(f"Error saving MCQs to JSON: {e}")

# Step 6: Save MCQs to CSV
def save_mcq_to_csv(questions):
    try:
        with open(MCQ_CSV_PATH, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Question", "Option A (Correct)", "Option B", "Option C", "Option D"])

            for q in questions:
                writer.writerow([q["question"], q["options"][0], q["options"][1], q["options"][2], q["options"][3]])
    except Exception as e:
        print(f"Error saving MCQs to CSV: {e}")

# Flask Routes
@app.route('/upload', methods=['POST'])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Check file size (5 MB limit)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)  # Reset file pointer
        if file_size > 5 * 1024 * 1024:  # 5 MB
            return jsonify({"error": "File size exceeds 5 MB limit"}), 413

        # Save the uploaded file
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        # Step 1: Extract text from PDF
        text = extract_text_from_pdf(file_path)
        if not text:
            return jsonify({"error": "Failed to extract text from PDF"}), 500

        # Step 2: Preprocess the text
        processed_text = preprocess_text(text)

        # Step 3: Generate MCQs
        mcq_text = generate_mcq(processed_text, num_questions=5)
        if not mcq_text:
            return jsonify({"error": "Failed to generate MCQs"}), 500

        # Step 4: Parse MCQs into structured format
        questions = parse_mcq(mcq_text)

        # Step 5: Save MCQs to JSON & CSV
        save_mcq_to_json(questions)
        save_mcq_to_csv(questions)

        # Return the CSV file content directly
        with open(MCQ_CSV_PATH, 'r') as f:
            csv_content = f.read()

        return jsonify({
            "questions": questions,
            "csv_content": csv_content
        })

    except Exception as e:
        print(f"Error in upload route: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)