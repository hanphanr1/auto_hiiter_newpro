"""
Telegram Channel Data Scanner

Production-quality tool for scanning Telegram channels and extracting patterns.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
    ApiIdInvalidError,
)
from telethon.tl.types import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Default regex patterns
DEFAULT_PATTERNS = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "url": r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*",
}

# Config file path
CONFIG_FILE = "config.json"


def load_config() -> Optional[dict]:
    """Load API credentials from config file."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                logger.info("Loaded credentials from config file")
                return config
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")
    return None


def save_config(api_id: int, api_hash: str, phone: str) -> None:
    """Save API credentials to config file."""
    config = {
        "api_id": api_id,
        "api_hash": api_hash,
        "phone": phone,
    }
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        logger.info("Credentials saved to config file")
    except Exception as e:
        logger.warning(f"Failed to save config: {e}")


def get_credentials() -> tuple:
    """
    Get API credentials from user or config file.
    
    Returns:
        Tuple of (api_id, api_hash, phone)
    """
    # Try to load from config
    config = load_config()

    if config:
        print("\n--- Saved Credentials Found ---")
        print(f"API ID: {config.get('api_id')}")
        print(f"Phone: {config.get('phone')}")
        print("-" * 30)
        print("1. Use saved credentials")
        print("2. Enter new credentials")
        print("3. Delete saved credentials")

        while True:
            try:
                choice = input("Enter choice (1-3): ").strip()
                if choice in ["1", "2", "3"]:
                    break
                print("Enter 1, 2, or 3")
            except ValueError:
                print("Invalid input")

        if choice == "1":
            return config["api_id"], config["api_hash"], config["phone"]
        elif choice == "3":
            if os.path.exists(CONFIG_FILE):
                os.remove(CONFIG_FILE)
                logger.info("Config file deleted")
            print("Config deleted. Please enter new credentials.\n")

    # Get new credentials
    print("\n--- API Credentials ---")

    while True:
        try:
            api_id = int(input("Enter your api_id: ").strip())
            break
        except ValueError:
            print("Invalid input. Please enter a numeric api_id.")

    api_hash = input("Enter your api_hash: ").strip()
    phone = input("Enter phone number (with country code): ").strip()

    # Ask to save
    save = input("Save credentials for next time? (y/n): ").strip().lower()
    if save == "y":
        save_config(api_id, api_hash, phone)

    return api_id, api_hash, phone


class TelegramScanner:
    """Main scanner class for Telegram channel data extraction."""

    def __init__(self, api_id: int, api_hash: str, session_name: str = "scanner_session"):
        """Initialize the scanner with Telegram API credentials."""
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client: Optional[TelegramClient] = None
        self.entity = None

    async def connect_telegram(self, phone: str) -> bool:
        """
        Connect to Telegram and authenticate the user.
        
        Args:
            phone: User's phone number with country code (e.g., +1234567890)
            
        Returns:
            True if connection and authentication successful, False otherwise
        """
        logger.info("Initializing Telegram client...")
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

        try:
            await self.client.connect()
            logger.info("Connected to Telegram")

            # Check if already authorized
            if await self.client.is_user_authorized():
                logger.info("User already authorized")
                return True

            # Send verification code
            logger.info("Sending verification code...")
            await self.client.send_code_request(phone)

            # Get the code from user
            code = input("Enter the code you received on Telegram: ").strip()

            try:
                await self.client.sign_in(phone, code)
                logger.info("Successfully signed in")
                return True
            except SessionPasswordNeededError:
                # Two-factor authentication
                password = input("Enter your 2FA password: ").strip()
                await self.client.sign_in(password=password)
                logger.info("Successfully signed in with 2FA")
                return True

        except PhoneNumberInvalidError:
            logger.error("Invalid phone number format")
            return False
        except ApiIdInvalidError:
            logger.error("Invalid API ID or hash")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def resolve_channel(self, channel_input: str) -> Optional[object]:
        """
        Resolve a channel from user input.
        
        Supports:
        - Numeric channel ID (e.g., -100xxxxxxxxxx)
        - Username with @ prefix
        - Invite links (t.me/joinchat/...)
        - Dialog selection
        
        Args:
            channel_input: User-provided channel identifier
            
        Returns:
            Telegram entity object or None if resolution fails
        """
        logger.info(f"Resolving channel: {channel_input}")

        if not self.client:
            logger.error("Client not connected")
            return None

        try:
            # Try direct resolution first
            # Handle numeric IDs
            if channel_input.lstrip("-").isdigit():
                channel_id = int(channel_input)
                entity = await self.client.get_entity(channel_id)
                logger.info(f"Resolved channel by ID: {entity.title}")
                self.entity = entity
                return entity

            # Handle t.me links
            if "t.me/" in channel_input:
                channel_input = channel_input.split("t.me/")[-1]
                if channel_input.startswith("joinchat/"):
                    channel_input = channel_input.replace("joinchat/", "+")

            # Remove @ prefix if present
            if channel_input.startswith("@"):
                channel_input = channel_input[1:]

            # Try to get entity
            entity = await self.client.get_entity(channel_input)
            logger.info(f"Resolved channel: {entity.title}")
            self.entity = entity
            return entity

        except Exception as e:
            logger.error(f"Failed to resolve channel: {e}")
            return None

    async def select_channel_from_dialogs(self) -> Optional[object]:
        """
        Display a list of accessible channels/groups for user selection.
        
        Returns:
            Selected channel entity or None
        """
        if not self.client:
            logger.error("Client not connected")
            return None

        logger.info("Fetching dialogs...")
        try:
            dialogs = await self.client.get_dialogs(limit=100)
        except Exception as e:
            logger.error(f"Failed to fetch dialogs: {e}")
            return None

        # Filter for channels and groups
        channels_and_groups = []
        for dialog in dialogs:
            entity = dialog.entity

            # Determine entity type
            if hasattr(entity, "broadcast") and entity.broadcast:
                channels_and_groups.append((entity, entity.title, "Channel"))
            elif hasattr(entity, "megagroup") and entity.megagroup:
                channels_and_groups.append((entity, entity.title, "Supergroup"))
            elif hasattr(entity, "participants_count"):
                channels_and_groups.append((entity, entity.title, "Group"))

        if not channels_and_groups:
            logger.warning("No channels or groups found")
            return None

        # Display options
        print("\n" + "=" * 50)
        print("Available Channels and Groups:")
        print("=" * 50)
        for i, (entity, title, gtype) in enumerate(channels_and_groups, 1):
            print(f"{i}. {title} ({gtype})")
        print("=" * 50)

        # Get selection
        while True:
            try:
                choice = int(input("\nSelect channel/group (number): "))
                if 1 <= choice <= len(channels_and_groups):
                    selected = channels_and_groups[choice - 1][0]
                    logger.info(f"Selected: {channels_and_groups[choice - 1][1]}")
                    self.entity = selected
                    return selected
                print(f"Enter 1-{len(channels_and_groups)}")
            except ValueError:
                print("Invalid input")

    async def scan_messages(
        self,
        limit: int,
        pattern: str,
        entity: Optional[object] = None,
    ) -> list:
        """
        Scan messages from a channel and extract matching patterns.
        
        Optimized for large channels - uses generator and stops when
        enough results are collected.
        
        Args:
            limit: Maximum number of results to collect
            pattern: Regex pattern to match
            entity: Optional entity to scan (uses self.entity if not provided)
            
        Returns:
            List of unique matches
        """
        target_entity = entity or self.entity
        if not target_entity:
            logger.error("No entity specified for scanning")
            return []

        logger.info(f"Starting scan for pattern: {pattern}")
        logger.info(f"Target: {getattr(target_entity, 'title', 'Unknown')}")

        matches: set = set()
        scanned_count = 0
        regex = re.compile(pattern)
        
        # Scan ALL messages in channel
        async for message in self.client.iter_messages(target_entity, limit=None):
            scanned_count += 1

            # Progress update every 100 messages
            if scanned_count % 100 == 0:
                logger.info(
                    f"Scanned {scanned_count} messages, found {len(matches)} matches..."
                )

            # Skip messages without text
            if not message.message:
                continue

            # Extract matches
            found = regex.findall(message.message)
            if found:
                matches.update(found)
                logger.debug(f"Found {len(found)} matches in message {message.id}")

            # Early stop if we have enough results
            if len(matches) >= limit:
                logger.info(f"Collected {limit} results, stopping scan")
                break

        logger.info(f"Scan complete. Scanned {scanned_count} messages, found {len(matches)} unique matches")
        return list(matches)

    def extract_patterns(self, messages: list, pattern: str) -> set:
        """
        Extract patterns from a list of messages.
        
        Note: This is kept for compatibility but scan_messages
        now handles extraction directly for efficiency.
        
        Args:
            messages: List of message objects
            pattern: Regex pattern
            
        Returns:
            Set of unique matches
        """
        matches = set()
        regex = re.compile(pattern)

        for message in messages:
            if isinstance(message, Message) and message.message:
                found = regex.findall(message.message)
                matches.update(found)

        return matches

    def output_results(self, results: list, output_file: Optional[str] = None) -> str:
        """
        Output results based on quantity.
        
        Args:
            results: List of extracted data
            output_file: Optional custom output filename
            
        Returns:
            Path to output file or "console" if printed
        """
        if not results:
            logger.warning("No results to output")
            return "No results"

        # Check if we should save to file
        if len(results) > 10:
            return self._save_to_file(results, output_file)
        else:
            self._print_to_console(results)
            return "console"

    def _save_to_file(self, results: list, custom_filename: Optional[str] = None) -> str:
        """Save results to a timestamped TXT file in the data folder."""
        # Get source name for filename
        source_name = getattr(self.entity, "title", "Unknown") if self.entity else "Unknown"
        
        # Sanitize channel name for filename (remove invalid characters)
        sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', source_name)
        
        # Create timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Determine filename
        if custom_filename:
            filename = custom_filename
        else:
            filename = f"{sanitized_name}_{timestamp}.txt"
        
        # Create data folder if it doesn't exist
        data_folder = "data"
        os.makedirs(data_folder, exist_ok=True)
        
        # Full path
        filepath = os.path.join(data_folder, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("Telegram Scanner Results\n")
                f.write("=" * 40 + "\n\n")
                f.write(f"Source: {source_name}\n")
                f.write(f"Total results: {len(results)}\n")
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n" + "-" * 40 + "\n\n")

                for i, result in enumerate(results, 1):
                    f.write(f"{i}. {result}\n")

            logger.info(f"Results saved to: {os.path.abspath(filepath)}")
            return os.path.abspath(filepath)

        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            raise

    def _print_to_console(self, results: list) -> None:
        """Print results directly to console."""
        print("\n" + "=" * 50)
        print("RESULTS")
        print("=" * 50)
        for i, result in enumerate(results, 1):
            print(f"{i}. {result}")
        print("=" * 50)
        print(f"Total: {len(results)} matches found.\n")

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self.client:
            await self.client.disconnect()
            logger.info("Disconnected from Telegram")


async def main():
    """Main entry point for the scanner."""
    print("=" * 50)
    print("Telegram Channel Data Scanner")
    print("=" * 50)

    # Get API credentials (from config or user input)
    api_id, api_hash, phone = get_credentials()

    # Initialize scanner
    scanner = TelegramScanner(api_id, api_hash)

    # Connect to Telegram
    if not await scanner.connect_telegram(phone):
        logger.error("Failed to connect to Telegram")
        return

    print("\n--- Select Channel ---")
    print("1. Enter channel ID (e.g., -100xxxxxxxxxx)")
    print("2. Enter username (e.g., @channelname)")
    print("3. Enter invite link")
    print("4. Select from your dialogs")

    while True:
        try:
            choice = int(input("Enter choice (1-4): ").strip())
            if choice in [1, 2, 3, 4]:
                break
            print("Enter 1, 2, 3, or 4")
        except ValueError:
            print("Invalid input")

    # Resolve channel
    entity = None

    if choice == 1:
        channel_id = input("Enter channel ID: ").strip()
        entity = await scanner.resolve_channel(channel_id)
    elif choice == 2:
        username = input("Enter username (with @): ").strip()
        entity = await scanner.resolve_channel(username)
    elif choice == 3:
        link = input("Enter invite link: ").strip()
        entity = await scanner.resolve_channel(link)
    else:
        entity = await scanner.select_channel_from_dialogs()

    if not entity:
        logger.error("Could not resolve channel")
        await scanner.disconnect()
        return

    # Get scan settings
    print("\n--- Scan Settings ---")

    while True:
        try:
            limit = int(input("How many results to collect? ").strip())
            if limit > 0:
                break
            print("Enter a positive number")
        except ValueError:
            print("Invalid input")

    # Select pattern
    print("\nSelect pattern type:")
    print("1. Email addresses")
    print("2. URLs")
    print("3. Custom regex")

    while True:
        try:
            pattern_choice = int(input("Enter choice (1-3): ").strip())
            if pattern_choice in [1, 2, 3]:
                break
            print("Enter 1, 2, or 3")
        except ValueError:
            print("Invalid input")

    if pattern_choice == 1:
        pattern = DEFAULT_PATTERNS["email"]
        pattern_name = "emails"
    elif pattern_choice == 2:
        pattern = DEFAULT_PATTERNS["url"]
        pattern_name = "URLs"
    else:
        pattern = input("Enter regex pattern: ").strip()
        pattern_name = "matches"

    print(f"\nScanning for {pattern_name}...")
    print("-" * 40)

    # Scan messages
    results = await scanner.scan_messages(limit=limit, pattern=pattern)

    # Output results
    if not results:
        print("\nNo matches found.")
    else:
        print(f"\nFound {len(results)} unique {pattern_name}!")
        output_path = scanner.output_results(results)
        if output_path != "console":
            print(f"Results saved to: {output_path}")

    # Cleanup
    await scanner.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
