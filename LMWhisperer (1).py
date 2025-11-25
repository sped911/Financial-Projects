from unstract.llmwhisperer import LLMWhispererClientV2
from unstract.llmwhisperer.client_v2 import LLMWhispererClientException
import json
import time
# Provide the base URL and API key explicitly
client = LLMWhispererClientV2(
    base_url="https://llmwhisperer-api.us-central.unstract.com/api/v2",
    api_key="YOUR API KEY"  # Replace with your actual API key
)

# Get usage info
usage_info = client.get_usage_info()
print(json.dumps(usage_info, indent=2))

# The client will return with a whisper hash which can be used to check the status and retrieve the result
whisper_result = client.whisper(file_path="D:\[{USER}\Python\LLMWhisperer\TEST 1392 12.23 - 6.23_Part3.pdf")

while True:
    whisper_hash = whisper_result["whisper_hash"]
    combined = {
        **usage_info,  # usage_info must be a dictionary
        "whisper_hash": whisper_hash
    }
    print(json.dumps(combined, indent=2))

    status = client.whisper_status(whisper_result["whisper_hash"])  # Replace with your actual whisper_hash)
    state = status.get("status")
    print(f"Current status: {state}")

    if state == "processed":
        break
    elif state in ("processing", "ingestion_done", "ingesting"):
        # still working — wait and retry
        time.sleep(5)
        continue
    else:
        # some unexpected terminal state
        raise RuntimeError(f"Whisper failed with status: {state}")


whisper_output = client.whisper_retrieve(whisper_hash)
print(json.dumps(whisper_output.get("extraction", {}).get("result_text"), indent=2))  