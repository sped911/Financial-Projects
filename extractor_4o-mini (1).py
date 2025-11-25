import os
import json
import time
import logging
import shutil
from collections import defaultdict
from datetime import datetime
import openai

# Set your OpenAI API key here
OPENAI_API_KEY = 'YOUR API KEY'
openai.api_key = OPENAI_API_KEY

def setup_logging(log_path):
    """Set up logging to file and console."""
    log_file = os.path.join(log_path, "process_log.txt")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info("Logging initialized.")

def read_json_prompts(file_path):
    """Reads prompts from the specified JSON file."""
    try:
        logging.info(f"Reading prompts from JSON file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        logging.error(f"Error reading JSON file: {e}")
        return None

def get_prompt_for_folder(prompts_data, folder_name):
    """Matches folder with the corresponding prompt in the JSON data."""
    for item in prompts_data:
        if item['prompt_name'] == folder_name:
            return item['prompt_name'], item['prompt']
    
    print(f"No matching prompt found for folder: {folder_name}")
    logging.warning(f"No matching prompt found for folder: {folder_name}")
    return None, None

def send_to_gpt4(prompt, content):
    """Sends a request to OpenAI's GPT-4 Mini API using the correct endpoint and structure."""
    messages = [
        {"role": "system", "content": "You are an assistant. First, replace the literal string '\\n' with an actual newline, Please provide only the necessary fields in the exact format, as JSON."},
        {"role": "user", "content": f"{prompt}\n\n{content}"}
    ]
    
    try:
        start_time = datetime.now()
        logging.info("Sending request to GPT-4o mini...")
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  
            messages=messages,
            #max_tokens=4096,
            temperature=0.7,
        )
        duration = datetime.now() - start_time
        logging.info(f"Received response in {duration.total_seconds()} seconds.")
        
        response_data = response['choices'][0]['message']['content']
        parsed_data = json.loads(response_data)
        return parsed_data

    except Exception as e:
        print(f"Error sending request to GPT-4o Mini: {e}")
        logging.error(f"Error sending request to GPT-4o Mini: {e}")
        return None

def process_text_files(folder_path, prompts_data):
    """Process text files in the specified folder and subfolders using prompts from the JSON data."""
    
    if not os.path.exists(folder_path):
        logging.error(f"Folder does not exist: {folder_path}")
        print(f"Error: The folder path '{folder_path}' does not exist.")
        return
    
    text_files = []
    subfolder_summary = defaultdict(int)
    total_processing_time = 0
    total_files_processed = 0

    overall_start_time = time.time()

    for root, dirs, files in os.walk(folder_path):
        if root == folder_path or 'Processed' in root:
            continue

        for file in files:
            if file.endswith('.txt'):
                text_files.append(os.path.join(root, file))
                subfolder_summary[os.path.basename(root)] += 1
    
    if not text_files:
        print(f"Skipping folder: {folder_path}. No text files found.")
        logging.info(f"Skipping folder: {folder_path}. No text files found.")
        return
    
    logging.info(f"Found {len(text_files)} text files to process in folder: {folder_path}")
    print(f"Found {len(text_files)} text files to process in folder: {folder_path}")

    for file_path in text_files:
        try:
            start_time = time.time()
            with open(file_path, 'r', encoding='utf-8') as file:
                file_content = file.read()
                file_content = '\n'.join([line for line in file_content.split('\n') if line.strip()])

            folder_name = os.path.basename(os.path.dirname(file_path))
            prompt_name, prompt_text = get_prompt_for_folder(prompts_data, folder_name)

            if prompt_name and prompt_text:
                logging.info(f"Processing file: {file_path} with prompt: {prompt_name}")
                response = send_to_gpt4(prompt_text, file_content)
                if response:
                    save_response_as_json(response, file_path)
                    move_to_processed(file_path)
                else:
                    print(f"No response for file: {file_path}")
            else:
                print(f"No prompt found for folder: {folder_name}")
                logging.warning(f"No prompt found for folder: {folder_name}")

            end_time = time.time()
            processing_time = end_time - start_time
            total_processing_time += processing_time
            total_files_processed += 1
            logging.info(f"File processed in {processing_time:.2f} seconds.")

        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
    
    overall_duration = time.time() - overall_start_time

    logging.info("Processed Summary:")
    for folder_name, file_count in subfolder_summary.items():
        logging.info(f"{folder_name} | - {file_count}")

    if total_files_processed > 0:
        average_time = total_processing_time / total_files_processed
        logging.info(f"Average processing time per file: {average_time:.2f} seconds.")
    else:
        logging.info("No files processed.")

    logging.info(f"Total processing duration: {overall_duration:.2f} seconds.")

def save_response_as_json(response, file_path):
    """Saves the GPT-4 response to a JSON file in the same folder."""
    output_file = os.path.splitext(file_path)[0] + "_result.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            json.dump({"response": response}, outfile, ensure_ascii=False, indent=4)
        logging.info(f"Response saved to: {output_file}")
        print(f"Response saved: {output_file}")
    except Exception as e:
        logging.error(f"Error saving response for file {file_path}: {e}")
        print(f"Error saving response for file {file_path}: {e}")

def move_to_processed(file_path):
    """Moves the processed text file to a 'Processed' folder."""
    processed_folder = os.path.join(os.path.dirname(file_path), 'Processed')
    os.makedirs(processed_folder, exist_ok=True)
    try:
        shutil.move(file_path, processed_folder)
        logging.info(f"Moved file to: {processed_folder}")
        print(f"Moved file to: {processed_folder}")
    except Exception as e:
        logging.error(f"Error moving file {file_path} to 'Processed' folder: {e}")
        print(f"Error moving file {file_path} to Processed folder: {e}")

def main():
    """Main function to process text files based on user-provided folder path."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(current_dir, 'prompt_011.json')

    if not os.path.exists(json_file_path):
        logging.error(f"JSON file 'prompt.json' not found in {current_dir}.")
        print(f"Error: The JSON file 'prompt.json' was not found in {current_dir}.")
        return

    folder_path = input("Enter the path to the folder: ").strip()
    setup_logging(folder_path)

    if not os.path.exists(folder_path):
        logging.error(f"Folder does not exist: {folder_path}")
        print(f"Error: The folder path '{folder_path}' does not exist.")
        return

    prompts_data = read_json_prompts(json_file_path)

    if prompts_data is not None:
        process_text_files(folder_path, prompts_data)
    else:
        print("Could not read prompts. Exiting.")
        logging.error("Failed to read prompts from JSON. Exiting.")

if __name__ == '__main__':
    main()
