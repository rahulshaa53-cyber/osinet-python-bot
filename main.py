"""
Telegram OSINT lookup bot setup.
Install: pip install pyTelegramBotAPI requests
Configure environment variables before running:
  BOT_TOKEN, ADMIN_ID, CHANNELS, API_URL, API_KEY

For privacy, /num is admin-only by default. Only use the lookup API for
lawful, authorized purposes and avoid sharing personal data without consent.
"""

import os
import re
import logging
import requests
import telebot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
CHANNELS = [
    item.strip()
    for item in os.getenv("CHANNELS", "@osinttovdhvd").split(",")
    if item.strip()
]
API_URL = os.getenv("API_URL", "https://ayaanmods.site/number.php").strip()
API_KEY = os.getenv("API_KEY", "").strip()

if not BOT_TOKEN:
    raise SystemExit("Missing BOT_TOKEN environment variable.")
if not ADMIN_ID_RAW.isdigit():
    raise SystemExit("Set ADMIN_ID to your numeric Telegram user ID.")
if not API_URL.startswith(("https://", "http://")):
    raise SystemExit("API_URL must start with http:// or https://")

ADMIN_ID = int(ADMIN_ID_RAW)
bot = telebot.TeleBot(BOT_TOKEN, parse_mode=None)


def is_joined(user_id: int) -> bool:
    """Return False if the user has not joined any required channel."""
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                return False
        except Exception:
            logger.exception("Could not verify channel membership: %s", channel)
            return False
    return True


def join_prompt() -> str:
    lines = ["🚫 Please join all required channels first:"]
    for channel in CHANNELS:
        clean_name = channel.lstrip("@")
        lines.append(f"https://t.me/{clean_name}")
    lines.append("\nThen send /start again.")
    return "\n".join(lines)


@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    if not is_joined(user_id):
        bot.reply_to(message, join_prompt())
        return

    bot.reply_to(
        message,
        "✅ Welcome!\n"
        "Use /num 9876543210 to perform an authorized lookup.\n"
        "Use /admin to check admin access.",
    )


@bot.message_handler(commands=["num"])
def num_lookup(message):
    user_id = message.from_user.id

    if not is_joined(user_id):
        bot.reply_to(message, "🚫 Join the required channel(s) first. Use /start.")
        return

    # Lookups can return personal information, so keep this command admin-only.
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ This lookup command is restricted to the bot admin.")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        bot.reply_to(message, "Usage: /num 9876543210")
        return

    number = re.sub(r"[\s()+-]", "", parts[1])
    if not number.isdigit() or not 7 <= len(number) <= 15:
        bot.reply_to(message, "❌ Enter a valid phone number containing 7–15 digits.")
        return

    if not API_KEY:
        bot.reply_to(message, "⚠️ API_KEY is not configured by the bot owner.")
        return

    try:
        response = requests.get(
            API_URL,
            params={"key": API_KEY, "number": number},
            timeout=10,
        )
        if response.status_code == 200:
            # Avoid sending an unbounded API response to Telegram.
            result = response.text.strip()
            if not result:
                result = "(The API returned an empty response.)"
            bot.reply_to(message, "📊 Result:\n" + result[:3500])
        else:
            logger.warning("Lookup API returned HTTP %s", response.status_code)
            bot.reply_to(message, "❌ API error. Please try again later.")
    except requests.RequestException:
        logger.exception("Lookup API request failed")
        bot.reply_to(message, "⚠️ Request failed. Please try again later.")


@bot.message_handler(commands=["admin"])
def admin(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ Not allowed.")
        return
    bot.reply_to(
        message,
        "👑 Admin panel active.\n"
        f"Required channels: {len(CHANNELS)}\n"
        f"API configured: {'yes' if API_KEY else 'no'}",
    )


if __name__ == "__main__":
    print("Bot running...")
    # Skip pending updates on startup and automatically retry transient polling errors.
    bot.infinity_polling(skip_pending=True, timeout=30, long_polling_timeout=30)
