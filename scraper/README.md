# Telegram Message Scraper

A Python script that scans messages from Telegram channels or groups and extracts specific patterns (emails, URLs, or custom regex).

## Prerequisites

1. **Get Telegram API Credentials**:
   - Go to https://my.telegram.org/apps
   - Create a new application
   - Copy your `api_id` and `api_hash`

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the script:
```bash
python telegram_scraper.py
```

Follow the interactive prompts:
1. Enter your `api_id` (from my.telegram.org)
2. Enter your `api_hash`
3. Enter your phone number (with country code, e.g., +1234567890)
4. Select a channel or group from the list
5. Enter how many results you want to collect
6. Choose the pattern type (emails, URLs, or custom regex)

## Output

- **10 or fewer results**: Printed directly to the console
- **More than 10 results**: Saved to a timestamped TXT file

## Features

- Progress display while scanning
- Duplicate filtering
- Support for emails, URLs, and custom regex patterns
- Two-factor authentication support
- Session persistence (won't need to re-authenticate on subsequent runs)
