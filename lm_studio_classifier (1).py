import os
import pandas as pd
import requests
import glob
import json
import shutil

# Constants
LM_STUDIO_BASE_URL = 'http://localhost:1234/v1'
PROMPT_SHEET_NAME = 'Prompt'


def read_excel_prompts(file_path):
    """Reads prompts from the specified Excel file."""
    try:
        return pd.read_excel(file_path, sheet_name=PROMPT_SHEET_NAME)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        return None


def get_prompt_for_folder(df, root):
    """Matches folder with the corresponding prompt in the DataFrame."""
    folder_name = os.path.basename(root)
    classified_match = df[df['Classified Folder'] == folder_name]
    unclassified_match = df[df['UnClassified Folder'] == folder_name]

    if not classified_match.empty:
        match = classified_match
    elif not unclassified_match.empty:
        match = unclassified_match
    else:
        print(f"No matching prompt found for folder: {folder_name}")
        return None, None

    return match['Prompt Name'].values[0], match['Prompt'].values[0]


def send_to_lm_studio(prompt, content):
    """Sends a request to LM Studio's local inference endpoint."""
    max_tokens = 4096 - len(prompt.split())  # Account for tokens in the prompt
    content_tokens = content.split()

    # Split content into smaller chunks if necessary
    if len(content_tokens) > max_tokens:
        content_chunks = [content_tokens[i:i + max_tokens] for i in range(0, len(content_tokens), max_tokens)]
    else:
        content_chunks = [content_tokens]

    responses = []
    for chunk in content_chunks:
        chunk_content = ' '.join(chunk)
        payload = {
            "model": "gemma-2-2b-it",  # Specify the model
            "messages": [
                {"role": "system", "content": "You are a Public Records Analyst. kindly analyze the given  document and extract the specified information verbatim, exactly as it appears in the document. If any field is not present or cannot be confidently determined, leave it blank."},
                {"role": "user", "content": f"{prompt}{chunk_content}"}
            ],
            "temperature": 0.7,
            "max_tokens": -1,  # Unlimited token generation
            "stream": False
        }

        try:
            response = requests.post(
                f"{LM_STUDIO_BASE_URL}/chat/completions",
                headers={"Content-Type": "application/json"},
                data=json.dumps(payload)
            )
            if response.status_code == 200:
                response_data = response.json().get('choices', [{}])[0].get('message', {}).get('content')
                responses.append(response_data)

                print (f"Parsing the response into valid JSON")
                try:
                    parsed_data = json.loads(response_data)

                    if isinstance(parsed_data, dict):
                        return parsed_data
                    else:
                        print("Parsed response is not a valid JSON object.")
                        return None
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    return None
                        
            else:
                print(f"Error: Received status code {response.status_code}")
                print(f"Response: {response.text}")
                return None
        except Exception as e:
            print(f"Error sending request to LM Studio: {e}")
            return None

    return ' '.join(parsed_data)  # Combine responses from all chunks

def process_text_files(folder_path, df):
    """Process text files in the specified folder and subfolders using prompts from the DataFrame,
    excluding folders named 'Processed'."""
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"Error: The folder path '{folder_path}' does not exist.")
        return
    
    # Use os.walk to traverse the folder and its subfolders
    text_files = []
    for root, dirs, files in os.walk(folder_path):
        # Skip the 'Processed' folder and its subfolders
        if 'Processed' in root:
            continue

        for file in files:
            if file.endswith('.txt'):
                text_files.append(os.path.join(root, file))
    
    # Skip folder if no text files are found
    if not text_files:
        print(f"Skipping folder: {folder_path}. No text files found.")
        return
    
    # Print the count of text files to be processed
    print(f"Found {len(text_files)} text files to process in folder: {folder_path}")

    # Process each text file found
    for file_path in text_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                # Read the file content and remove empty lines
                file_content = file.read()
                file_content = '\n'.join([line for line in file_content.split('\n') if line.strip()])
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            continue

        # Get the prompt for the folder
        prompt_name, prompt_text = get_prompt_for_folder(df, os.path.dirname(file_path))
        if prompt_name and prompt_text:
            # Send the file content to LM Studio and process the response
            print(f"Sending request to LM Studio with prompt name {prompt_name}.... ")
            response = send_to_lm_studio(prompt_text, file_content)
            if response:
                # Save the response as a JSON file
                save_response_as_json(response, file_path)
                # Move the processed file to the 'Processed' folder
                move_to_processed(file_path)
            else:
                print(f"No response for file: {file_path}")
        else:
            print(f"No prompt found for folder: {os.path.dirname(file_path)}")




def save_response_as_json(response, file_path):
    """Saves the LM Studio response to a JSON file in the same folder."""
    output_file = os.path.splitext(file_path)[0] + "_result.json"
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            json.dump({"response": response}, outfile, ensure_ascii=False, indent=4)
        print(f"Response saved: {output_file}")
    except Exception as e:
        print(f"Error saving response for file {file_path}: {e}")


def move_to_processed(file_path):
    """Moves the processed text file to a 'Processed' folder, overwriting if necessary."""
    processed_folder = os.path.join(os.path.dirname(file_path), 'Processed')
    os.makedirs(processed_folder, exist_ok=True)
    destination_path = os.path.join(processed_folder, os.path.basename(file_path))
    
    try:
        # If a file with the same name exists, remove it
        if os.path.exists(destination_path):
            os.remove(destination_path)
        shutil.move(file_path, destination_path)
        print(f"Moved file to: {destination_path}")
    except Exception as e:
        print(f"Error moving file {file_path} to Processed folder: {e}")


def main():
    """Main function to process text files based on user-provided folder path."""
    # Determine the location of the Excel file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    excel_file_path = os.path.join(current_dir, 'Prompt - Copy.xlsx')

    # Check if the Excel file exists
    if not os.path.exists(excel_file_path):
        print(f"Error: The Excel file 'Prompt - Copy.xlsx' was not found in {current_dir}.")
        return

    # Ask the user for a folder path
    folder_path = input("Enter the path to the folder: ").strip()

    # Verify folder existence
    if not os.path.exists(folder_path):
        print(f"Error: The folder path '{folder_path}' does not exist.")
        return

    # Determine folder type based on keywords
    folder_type = None
    if "Classified" in folder_path:
        folder_type = "Classified"
    elif "UnClassified" in folder_path:
        folder_type = "UnClassified"
    else:
        print("Error: Folder name must contain either 'Classified' or 'UnClassified'.")
        return

    # Base URL for LM Studio
    lm_studio_base_url = 'http://localhost:1234/v1'

    # Read prompts from Excel
    prompts_df = read_excel_prompts(excel_file_path)

    if prompts_df is not None:
        # Process the folder
        process_text_files(folder_path, prompts_df)
    else:
        print("Could not read prompts. Exiting.")


if __name__ == '__main__':
    main()
