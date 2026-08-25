import anthropic
import json 
from textwrap import dedent
# Load ANTHROPIC_API_KEY from .env file
from dotenv import load_dotenv
load_dotenv()

client = anthropic.Anthropic() # Initialize the Anthropic client with the API key from the environment variable.

N = 20 # N = number of tickets to generate
categories = ["Access", "Software", "Hardware"] # Define the three categories for the tickets.

def ticket_gen(category):
    """
    This function will be called in a loop N times to generate the content of two fields for N tickets based on three categories.
    What goes in: category parameter for the prompt.
    What comes out: Dictionary with `body`, `input_tokens`, and `output_tokens` fields. The model used is `claude-haiku-4-5`. `body` is not guaranteed to parse.
        The `body` holds a list of content blocks with JSON keys in the `text` block for `short_description` (ticket issue) and `description` (detailed explanation).
        The `input_tokens` and `output_tokens` are integers for the number of tokens used in the request and response, respectively.
    What happens when it fails: raises whatever the SDK raises since individual tickets are skipped if an API or parsing exception is hit. 
    """
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": dedent(f"""\
                    Generate a JSON object with the `short_description` and `description` fields for one customer support ticket with an issue related to the {category} category.
                    The `short_description` should be a concise summary of the issue, while the `description` should provide a detailed explanation of the `short_description` and any relevant context.
                    The output should be valid JSON in the format below, with no additional text or explanation. Do not add preamble or markdown fences. 
                    JSON format: 
                    {{
                    "short_description": "<short description here>",
                    "description": "<description here>"
                    }}
                """),
            },
            {
                "role": "assistant",
                "content": "{" # Prefill, for JSON parsing.
            }
        ],
    )
    llm_output = {
            "body": message.content,
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens
        }
    return llm_output

tickets = []
tokens_data = []
total_input = 0
total_output = 0

for i in range(0, N):
    ticket_id = i + 1
    cat = categories[i % len(categories)] # Cycle through the three categories for each ticket.
    json_body = {}
    
    # Catch-all for unexpected Anthropic API errors.
    try:
        output = ticket_gen(cat) # Run the ticket_gen function with the current category.
    except anthropic.APIError as e:
        print(f"skipping ticket: {ticket_id}: {e}")
        continue
    
    # Get and assemble the token data for this ticket.
    input_tokens = output["input_tokens"]
    output_tokens = output["output_tokens"]
    tokens = {"ticket_id": ticket_id, "category": cat, "input_tokens": input_tokens, "output_tokens": output_tokens}
    tokens_data.append(tokens)
    total_input += input_tokens
    total_output += output_tokens

    # Catch invalid JSON from the model's output when parsed into Python dict. 
    try:
        for block in output["body"]:
            if block.type == "text":
                json_body = json.loads("{" + block.text)
    except json.JSONDecodeError as e: 
        print(f"skipping ticket: {ticket_id}: {e}")
        continue

    # Catch missing short_description/description JSON keys.
    if "short_description" not in json_body or "description" not in json_body:
        print(f"skipping ticket: {ticket_id}: missing `short_description` and/or `description` key(s)")
        continue

    # Assemble the ticket content for this ticket.
    current_ticket = {
        "ticket_id": ticket_id,
        "category": cat,
        "body": json_body
    }
    tickets.append(current_ticket) # Add the ticket content to the list of tickets to be written to the JSON file.

# Assemble the token usage data with total input and output tokens, and tokens per ticket.
token_usage = {
    "total_input_tokens": total_input,
    "total_output_tokens": total_output,
    "tokens_per_ticket": tokens_data
}

# Parse the Python dicts into JSON and write to files.
with open("tickets.json", "w") as file:
    json.dump(tickets, file, indent=4)

with open("token_usage.json", "w") as file:
    json.dump(token_usage, file, indent=4)