from flask import Flask, render_template, request, jsonify
import PyPDF2
import re
import google.generativeai as genai
import json
import os
import csv

app = Flask(__name__)

# Configure Google Gemini API
genai.configure(api_key='AIzaSyCymClOfe4v7yG-_fmFx0r_KKuKhB9TlXw')  # Replace with your actual API key

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

MCQ_JSON_PATH = os.path.join(UPLOAD_FOLDER, 'mcq.json')
MCQ_CSV_PATH = os.path.join(UPLOAD_FOLDER, 'mcqs.csv')


# Step 1: Extract Text from PDF
def extract_text_from_pdf(pdf_path):
    text = ''
    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ''  # Ensure no NoneType error
    return text.strip()


# Step 2: Preprocess the Text
def preprocess_text(text):
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with a single space
    text = re.sub(r'[^\w\s.]', '', text)  # Remove special characters except periods
    return text


# Step 3: Generate MCQs using Google Gemini
def generate_mcq(text, num_questions=5):
    model = genai.GenerativeModel('gemini-1.5-flash')  # Ensure correct model version

    prompt = f"""
    Generate {num_questions} multiple-choice questions (MCQs) based on the following text:

    {text}

    Format each question as:
    Q: [Question]
    A: [Correct Answer]
    B: [Option 1]
    C: [Option 2]
    D: [Option 3]
    """

    try:
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

    questions = []
    lines = mcq_text.split('\n')

    for i in range(0, len(lines), 5):
        if i + 4 < len(lines):  # Ensure proper MCQ format
            question = {
                "question": lines[i].replace("Q: ", "").strip(),
                "options": [
                    lines[i+1].replace("A: ", "").strip(),
                    lines[i+2].replace("B: ", "").strip(),
                    lines[i+3].replace("C: ", "").strip(),
                    lines[i+4].replace("D: ", "").strip()
                ],
                "correct_answer": lines[i+1].replace("A: ", "").strip()
            }
            questions.append(question)

    return questions


# Step 5: Save MCQs to JSON
def save_mcq_to_json(questions):
    with open(MCQ_JSON_PATH, 'w') as f:
        json.dump(questions, f, indent=4)


# Step 6: Save MCQs to CSV
def save_mcq_to_csv(questions):
    with open(MCQ_CSV_PATH, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Question", "Option A (Correct)", "Option B", "Option C", "Option D"])

        for q in questions:
            writer.writerow([q["question"], q["options"][0], q["options"][1], q["options"][2], q["options"][3]])


# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save the uploaded file
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    # Step 1: Extract text from PDF
    text = extract_text_from_pdf(file_path)

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

    return jsonify(questions)


if __name__ == '__main__':
    app.run(debug=True)
