# Telegram Message Scraper - Specification

## 1. Project Overview

- **Project Name**: Telegram Message Pattern Extractor
- **Type**: Python CLI Tool
- **Core Functionality**: Scan messages from accessible Telegram channels/groups and extract specific patterns (emails, URLs) using Telethon
- **Target Users**: Users who need to extract data from Telegram conversations

## 2. Functionality Specification

### Core Features

1. **Telethon Integration**
   - Use Telethon library with API credentials (api_id, api_hash)
   - Support for interactive login via phone number
   - Handle session management for re-authentication

2. **User Input**
   - Prompt for api_id (integer)
   - Prompt for api_hash (string)
   - Prompt for phone number for authentication
   - Prompt for Telegram channel/group username or invite link
   - Prompt for number of results to collect
   - Prompt for pattern type selection (email, URL, or custom regex)

3. **Message Scanning**
   - Use `iter_messages()` with limit parameter
   - Display progress during scanning (message count, results found)
   - Handle large result sets efficiently

4. **Pattern Extraction**
   - Email pattern: standard email regex
   - URL pattern: standard URL regex
   - Custom regex: allow user-defined pattern

5. **Output Handling**
   - If results <= 10: Print directly to console in formatted output
   - If results > 10: Save to TXT file with timestamp
   - Avoid duplicates using a set

6. **Progress Display**
   - Show current message number being scanned
   - Show count of unique results found
   - Update display periodically (every 100 messages)

### User Interactions Flow

1. User runs script → Prompts for API credentials
2. User enters credentials → Authenticates with Telegram
3. Script shows accessible dialogs → User selects target
4. User enters result limit → Scanning begins
5. Progress displayed → Results collected
6. Results output → Console or file

### Edge Cases

- Invalid API credentials → Show error and exit
- Channel/group not accessible → Show error with explanation
- No matches found → Inform user
- Network errors → Handle gracefully with retry option

## 3. Acceptance Criteria

- [ ] Script requests all required credentials interactively
- [ ] Authentication works with valid credentials
- [ ] iter_messages() is used with limit parameter
- [ ] Progress is displayed while scanning
- [ ] Duplicates are properly filtered
- [ ] Results <= 10 print to console with formatting
- [ ] Results > 10 save to TXT file
- [ ] At least email and URL patterns work
- [ ] Code is clean with helpful comments
