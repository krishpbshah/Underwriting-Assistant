from flask import Flask, request, jsonify, render_template, make_response
from PyPDF2 import PdfReader
import requests
import os
import logging
from dotenv import load_dotenv

app = Flask(__name__)

# Replace with your actual API key
load_dotenv()

# Get the API key from environment variables
API_KEY = os.getenv('API_KEY')


# Ensure the uploads folder exists
UPLOAD_FOLDER = 'pdfs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load PDF files
guide_files = {
    'Canada Protection Plan': 'CPP.pdf',
    'RBC': 'RBC.pdf',
    'Orange Benefit Fund': 'OBF.pdf',
    'Industrial Alliance': 'IA.pdf',
    'UV Insurance': 'UV.pdf',
    'Empire Life': 'EL.pdf',
    'Assumption Life': 'AL.pdf',
    'BMO': 'BMO.pdf',
    'IVARI': 'ivari.pdf',
    'Desjardins': 'DS.pdf',
    'Foresters': 'FOR.pdf',
    'Specialty Life Insurance': 'SLI.pdf',
    'Beneva': 'Beneva.pdf',
}

pdf_texts = {}
for name, file_path in guide_files.items():
    pdf_path = os.path.join(UPLOAD_FOLDER, file_path)
    if os.path.exists(pdf_path):
        reader = PdfReader(pdf_path)
        pages_text = []
        for page_number, page in enumerate(reader.pages):
            page_text = page.extract_text()
            pages_text.append((page_number + 1, page_text))
        pdf_texts[name] = pages_text

# Maintain conversation context
conversation_history = []

def fetch_gpt_completion(messages):
    url = 'https://api.openai.com/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'gpt-3.5-turbo',
        'messages': messages,
        'max_tokens': 2048,  # Adjust the max tokens to accommodate longer responses
        'temperature': 0.7
    }
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code != 200:
        logging.error(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()
    
    return response.json()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_insurer', methods=['POST'])
def select_insurer():
    data = request.json
    insurers = data.get('insurers')
    if not insurers or not all(insurer in pdf_texts for insurer in insurers):
        return jsonify({'success': False, 'error': 'One or more insurers not found'})

    conversation_history.clear()  # Clear previous conversation
    conversation_history.append({"role": "system", "content": f"Selected insurers: {', '.join(insurers)}"})

    response = make_response(jsonify({'success': True, 'message': f'Insurers {", ".join(insurers)} selected'}))
    response.set_cookie('insurers', ','.join(insurers))
    return response

@app.route('/applicant_details', methods=['POST'])
def applicant_details():
    data = request.json
    insurers = request.cookies.get('insurers')
    if not insurers:
        return jsonify({'success': False, 'error': 'No insurer selected or insurer not found'})
    insurers = insurers.split(',')

    try:
        age = data.get('age')
        gender = data.get('gender')
        height = data.get('height')
        weight = data.get('weight')
        smoking_status = data.get('smoking_status')
        health_conditions = data.get('health_conditions', [])

        applicant_info = f"""
        Applicant Details:
        - Age: {age}
        - Gender: {gender}
        - Height: {height} cm
        - Weight: {weight} kg
        - Smoking Status: {smoking_status}
        - Health Conditions: {health_conditions}
        """

        # Extract relevant sections from each selected insurer's guide with page numbers
        def extract_relevant_sections(pages_text, conditions, max_length=1000):
            """ Extract relevant sections of text based on health conditions with page numbers """
            relevant_text = ""
            for page_number, text in pages_text:
                for condition in conditions:
                    if condition.lower() in text.lower():
                        start_idx = text.lower().find(condition.lower())
                        end_idx = text.find("\n", start_idx + max_length)  # Extract around 1000 characters for context
                        if end_idx == -1:
                            end_idx = len(text)
                        relevant_text += f"Page {page_number}: {text[start_idx:end_idx]}\n\n"
                        if len(relevant_text) > max_length:
                            break
                if len(relevant_text) > max_length:
                    break
            return relevant_text

        # Prepare and send prompts for each insurer individually
        responses = []
        for insurer in insurers:
            combined_text = extract_relevant_sections(pdf_texts[insurer], health_conditions)
            if len(insurers) == 1:
                prompt = f"""
                You are a world class life insurance underwriting expert. You are skilled at reading any insurers’ underwriting guide, which provides information on how that insurance company determines if an applicant for insurance is approved/denied and under what conditions. You job is to help life insurance brokers the information they need to determine if a client will get approved/denied for life insurance. You do this by analyzing insurers’ underwriting guides in detail and providing specific and concise and relevant information from the guides to the insurance broker. This way they don’t have to read these dozens of pages guides, they can rely on you as the expert. Based on the provided details and the underwriting guidelines of {insurer}, here's an analysis for the applicant:
                

                Applicant Details:
                {applicant_info}

                Underwriting Guidelines:
                {combined_text}

                Please provide the following information:

                **Step 1: Type of Health Condition** - Description of the condition and its characteristics. Do not break up the condition names into individual letters.
                **Step 2: Details to Provide with Application** - Information needed for the application.
                **Step 3: Expected Requirements** - Any additional documentation required.
                **Step 4: Likely Underwriting Decisions** - Decisions and percentage ratings (Percentages ratings must be sourced directly from the guide and they must be given) based on the severity of the condition. Percentages must be sourced directly from the guide, accurate and must be unique for each insurer. The ratings need to be there and with percentages. Include what the rating means.
                **Step 5: Assessment for the Applicant** - Analysis of the applicant’s condition based on their details.
                **Step 6: Recommendation** - Likely assessment and rating for the applicant.
                **Step 7: Most Suited Life Insurance Products** - Provide the most suited life insurance products/policies from the guide based on user needs. Must provide a specific insurance product.
                **Step 8: Final Assessment** - Overall assessment and documentation needed.
                **If medication is included, please include that in the assessment and how it affects the ratings and selected products, as well as information about the medication in Step 1.**
                """
            else:
                prompt = f"""
                You are a world class life insurance underwriting expert. You are skilled at reading any insurers’ underwriting guide, which provides information on how that insurance company determines if an applicant for insurance is approved/denied and under what conditions. You job is to help life insurance brokers the information they need to determine if a client will get approved/denied for life insurance. You do this by analyzing insurers’ underwriting guides in detail and providing specific and concise and relevant information from the guides to the insurance broker. This way they don’t have to read these dozens of pages guides, they can rely on you as the expert. Based on the provided details and the underwriting guidelines of {insurer}, here's an analysis for the applicant:

                Applicant Details:
                {applicant_info}

                Underwriting Guidelines:
                {combined_text}

                Please provide the following information:

                **Step 1: Type of Health Condition** - Description of the condition and its characteristics. Do not break up the condition names into individual letters.
                **Step 2: Details to Provide with Application** - Information needed for the application.
                **Step 3: Expected Requirements** - Any additional documentation required.
                **Step 4: Likely Underwriting Decisions** - Decisions and percentage ratings (Percentages ratings must be sourced directly from the guide and they must be given) based on the severity of the condition. Percentages must be sourced directly from the guide, accurate and must be unique for each insurer. The ratings need to be there and with percentages. Include what the rating means.
                **Step 5: Assessment for the Applicant** - Analysis of the applicant’s condition based on their details.
                **Step 6: Recommendation** - Likely assessment and rating for the applicant.
                **Step 7: Most Suited Life Insurance Products** - Provide the most suited life insurance products/policies from the guide based on user needs. Must provide a specific insurance product.
                **Step 8: Final Assessment** - Overall assessment and documentation needed.
                Compare the selected insurers and provide which of the mentioned products is the best and why.
                **If medication is included, please include that in the assessment and how it affects the ratings and selected products, as well as information about the medication in Step 1.**
                """

            conversation_history.append({"role": "user", "content": prompt})
            gpt_response = fetch_gpt_completion(conversation_history)
            response_content = gpt_response['choices'][0]['message']['content'] if 'choices' in gpt_response else 'Error processing request.'
            conversation_history.append({"role": "assistant", "content": response_content})
            responses.append(f"**Underwriting results for {insurer}:**\n\n{response_content}")

        if len(insurers) > 1:
            comparison_text = "Based on the provided information, here's a comparison of the insurers:\n\n"
            for insurer in insurers:
                comparison_text += f"**{insurer}**\n{responses[insurers.index(insurer)]}\n\n"
            response_content = comparison_text

        response_content = "\n\n".join(responses)
    except Exception as e:
        logging.error(f"Error processing applicant data: {e}")
        response_content = f"Error processing applicant data: {e}"

    return jsonify({'success': True, 'response': response_content})


@app.route('/ask_question', methods=['POST'])
def ask_question():
    data = request.json
    question = data.get('question')
    if not question:
        return jsonify({'success': False, 'error': 'No question provided'})

    insurers = request.cookies.get('insurers')
    if not insurers:
        return jsonify({'success': False, 'error': 'No insurer selected or insurer not found'})

    conversation_history.append({"role": "user", "content": f"Question about {insurers}: {question}"})

    try:
        gpt_response = fetch_gpt_completion(conversation_history)
        response_content = gpt_response['choices'][0]['message']['content'] if 'choices' in gpt_response else 'Error processing request.'
        conversation_history.append({"role": "assistant", "content": response_content})
    except requests.exceptions.HTTPError as e:
        logging.error(f"Error communicating with OpenAI API: {e}")
        response_content = f"Error communicating with OpenAI API: {e}"

    return jsonify({'success': True, 'response': response_content})

@app.route('/new_search', methods=['POST'])
def new_search():
    global conversation_history
    conversation_history = [msg for msg in conversation_history if msg['role'] == 'system']
    return jsonify({'success': True, 'message': 'New search started. Please select an insurer to begin.'})


@app.route('/find_insurer', methods=['POST'])
def find_insurer():
    data = request.json

    try:
        age = data.get('age')
        gender = data.get('gender')
        height = data.get('height')
        weight = data.get('weight')
        smoking_status = data.get('smoking_status')
        health_conditions = data.get('health_conditions', [])

        applicant_info = f"""
        Applicant Details:
        - Age: {age}
        - Gender: {gender}
        - Height: {height} cm
        - Weight: {weight} kg
        - Smoking Status: {smoking_status}
        - Health Conditions: {health_conditions}
        """

        prompt = f"""
        Based on the following applicant details, provide the best suited life insurance options from the available insurers:

        {applicant_info}

        Available Insurers:
        - Canada Protection Plan
        - RBC
        - Orange Benefit Fund
        - Industrial Alliance
        - UV Insurance
        - Empire Life
        - Assumption Life
        - BMO
        - IVARI
        - Desjardins
        - Foresters
        - Specialty Life Insurance
        - Beneva

        If medication is included, please include that in the assesment and how it affects the ratings and ectera.

        Please provide the following information:

        **Step 1: Best Suited Insurers** - List of insurers that best match the applicant's profile, provide at  least three from the avaliable ones and access to the underwriting guides.
        **Step 2: Details for Each Insurer** - Brief description of why each insurer is a good match.
        **Step 4: Likely Underwriting Decisions** - Decisions from each insurer and percentage ratings (Percentages ratings must be sourced directly from the individual insurer's guides, dont use the same one for each insurer) based on the severity of the condition. Ensure percentages are given and accurate.
        **Step 3: Recommended Policies** - Specific insurance products or policies recommended for the applicant from each of the insurers.
        **Step 4: Final Recommendation** - Give the best two overall specific products from two separate insurers based on the applicant’s details. Give reason why it’s the best and stay confident in your response. Incorporate the Likely Underwriting Decisions into your final decision, taking into account both how likely the applicant is to be approved based on your analysis, and what insurer/product will give the lowest rating

    
        """

        conversation_history.append({"role": "user", "content": prompt})
        gpt_response = fetch_gpt_completion(conversation_history)
        response_content = gpt_response['choices'][0]['message']['content'] if 'choices' in gpt_response else 'Error processing request.'
        conversation_history.append({"role": "assistant", "content": response_content})
    except Exception as e:
        logging.error(f"Error processing applicant data: {e}")
        response_content = f"Error processing applicant data: {e}"

    return jsonify({'success': True, 'response': response_content})

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    app.run(debug=True)
