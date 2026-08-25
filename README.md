# synthetic-ticket-generator

The `ticket_gen.py` script writes a JSON file containing `N` AI-generated, customer support tickets and writes a JSON file with the model token usage per ticket and total. 

- Note: The `first_contact.py` script in this repo was created for testing and is unrelated to `ticket_gen.py`. 

## Output example

- Truncated sample of `tickets.json` below. The file is an array of `N` with categories rotating. 

```json
[
    {
        "ticket_id": 1,
        "category": "Access",
        "body": {
            "short_description": "Unable to access account after password reset",
            "description": "Customer reports that they successfully completed a password reset through the 'Forgot Password' feature, but are unable to log in with their new credentials. The reset confirmation email was received and the new password meets all requirements (minimum 8 characters, includes uppercase, lowercase, numbers, and special characters). Customer has attempted logging in multiple times from different browsers and devices without success, receiving an 'Invalid credentials' error message each time. Account was last successfully accessed 3 days ago. Customer needs immediate access restored to complete urgent business operations."
        }
    }
]
```

- Truncated sample of `token_usage.json` below. 

```json
{
    "total_input_tokens": 2740,
    "total_output_tokens": 2894,
    "tokens_per_ticket": [
        {
            "ticket_id": 1,
            "category": "Access",
            "input_tokens": 137,
            "output_tokens": 137
        }
    ]
}
```

## Prerequisites

This project uses [uv](https://docs.astral.sh/uv/), a fast Python package and environment manager written in Rust.

### Install uv, if needed

* macOS / Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
* Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after installation to ensure `uv` is available in your PATH.

## Setup

1. Clone the repository:
```bash
git clone https://github.com/chrisnobis/synthetic-ticket-generator
cd synthetic-ticket-generator
```

2. Create and activate a virtual environment: 
```bash 
uv venv 
source .venv/bin/activate # On Windows use: .venv\Scripts\activate 
```
- Developed on Python 3.13.14 (Pinned via `.python-version` so that `uv venv` selects this version) 

3. Install required dependencies:
```bash
uv pip install -r requirements.txt
```

4. Create a `.env` file in the root directory. 

5. Add your API key to the newly created `.env` file:
```env
ANTHROPIC_API_KEY=your_api_key_here
```

*Note: Never commit `.env` file to version control.*

## Usage

The script loads the `.env` using `python-dotenv` with the following:
```python
from dotenv import load_dotenv
load_dotenv()
```

Run the file (from the project directory with `.venv` activated):
```bash
python3 ticket_gen.py
```

To change the number of loop iterations, change the `N` variable to a positive integer:
```python
N = 20 # = 20 tickets generated
```

## Design decisions

- The model used is Anthropic API `claude-haiku-4-5` and was chosen because it is fastest, cheapest, and is capable of producing the quality and consistency for this purpose. 
- The `category` parameter is the ground-truth label since it is something chosen by the user, not reported by the model. The prompt tells the model to generate the `short_description` and `description` fields based on the `category` parameter. 
- The `category` parameter values are `Access` (logging in, tool access), `Software` (local or cloud-based tools and applications), and `Hardware` (physical devices and accessories). This taxonomy is non-exhaustive by decision and v0 does not generate tickets outside of the three defined categories.
- The script produces nearly-even coverage per `category` by design. At `N=20` the intended totals are 7/7/6, respective to the three categories, but skipped tickets can change the distribution. The ticket output does not need to mimic real-world distribution, but is intended to run against a labeled test set for scoring on how the system fails.
- `textwrap.dedent` keeps the prompt visually indented without the model reading the leading whitespaces. The `\` after `"""` tells Python to ignore the leading line break.
- `token_usage.json` is overwritten on every script run, whether or not it hits APIError to prevent confusion with the previous run and confirms whether or not the API was called and charged.
	- Tickets that fail the API call do not get token usage recorded, but tickets that fail JSON parsing do, so `token_usage.json` can list more tickets than `tickets.json` contains. 

## Known limitations

- The model's output is not guaranteed to parse since the prompt cannot guarantee the model's output format. 
- IDs collide across runs because `ticket_id` = the run number. 
	- Multi-run collisions are not an issue for v0 because its job is to "loop N times to generate N tickets" and the file will be overwritten each run. No accumulating dataset where multi-run collisions would need to be accounted for.
- v0 skips individual tickets if an API or parsing exception is hit, or the expected JSON keys are missing. The console prints the skipped `ticket_id` with the error message or indicates a key is missing. 
- v0 generates unambiguous tickets, which means accuracy against this set will be biased, and closing that gap is a v1 item. A ticket is ambiguous when it has vague language, missing scope, no timeline. 
- The diversification of issues within categories is limited since the prompt is called independently of the previously generated tickets and their topics. The sample of twenty tickets has roughly seven distinct underlying issues. 

### `N=20` Sample Category/Issue Distribution

- Access

| Issue          | Amount |
| -------------- | ------ |
| Password reset | 7      |

- Software

| Issue                    | Amount |
| ------------------------ | ------ |
| App crash when exporting | 6      |
| App crash on startup     | 1      |

- Hardware

| Issue                 | Amount |
| --------------------- | ------ |
| Keyboard unresponsive | 1      |
| Visual bugs           | 1      |
| Laptop won't power on | 2      |
| Monitor unresponsive  | 2      |

## Failure log

- `content[0]` assumed to be text and `message.content[0].text` broke when adaptive thinking put a `ThinkingBlock` there instead of `TextBlock`.
	- Fix: `for` loop to get the function output where `.type == "text"`.
- The API returns only the continuation of the response. Prefill is not echoed back. 
	- Saw: `Extra data: line 2 column 22` error from `JSONDecodeError` which meant `json.loads` parsed something, then found more characters. 
	- Fix: the `{` must be reattached before parsing. Prefill the model's assistant response with opening curly bracket `{` to force the continuation immediately following the `{` as parseable JSON. 
- Markdown fences added to the model's output despite the prompt forbidding them.
	- The model's output is not guaranteed to parse.
	- Fix: the prompt contains the expected JSON format for the fields, wrapped in double braces (`{{...}}`), and instructs the model to not add text, preamble or markdown fences. 
	- Note: Use double literal braces (`{{...}}`) in f-strings to prevent variable evaluation and inlining the literal JSON, and ensure double quotes are used so Python doesn't output single-quoted, invalid JSON.
- `json.loads` handed a dict when it expects a string. 
	- `json.loads(s)` — text **in**, Python object out. Parse.
	- `json.dump(obj, f)` — Python object in, text out to a file. Serialize.
	- Fix: use `json.loads` to convert the model's output text to Python dict, then `json.dump` to format the Python objects for the output files.
- Token counts overwritten each iteration so only the usage of the last individual run would be written to the file.
	- Fix: declare `tokens_data = []` outside the loop to collect the `input_tokens` and `output_tokens` for each `ticket_id`. 
- `json_body` is assigned inside the inner block loop. If a response comes back with no text block, it silently carries over the previous ticket's body.
	- Fix: declare `json_body = {}` inside the loop to reset `json_body` each iteration. 