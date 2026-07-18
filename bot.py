
import os
import logging
from collections import defaultdict, deque
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from openai import OpenAI

# Configuration
TELEGRAM_BOT_TOKEN = "8917248329:AAHxStUTxlsE8vaLpknjd9hrb_kUH_i5SMI"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE")
OPENAI_MODEL = "gpt-5-mini"  # Using gpt-5-mini as per model check
MAX_CONVERSATION_MEMORY = 15
MAX_MESSAGE_LENGTH = 4096

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE)

# Conversation memory for each user
conversation_memory = defaultdict(lambda: deque(maxlen=MAX_CONVERSATION_MEMORY))

SYSTEM_PROMPT = (
    "You are a helpful, warm, and direct AI assistant built for Telegram.\n\n"
    "Personality:\n"
    "- Reply in a natural mix of Bangla and English (Banglish) when the user writes that way; otherwise match their language.\n"
    "- Be concise by default — Telegram messages should be scannable, not essays. Expand only when the user asks for detail.\n"
    "- Be proactive: if something is ambiguous, make a reasonable assumption and say so briefly, rather than asking multiple clarifying questions.\n"
    "- Be honest and direct — don't over-praise or hedge excessively.\n"
    "- Use a friendly, respectful tone (like talking to a colleague), avoid being robotic or overly formal.\n"
    "- Format with Telegram-friendly markdown (bold, bullet points) instead of long paragraphs.\n"
    "- If you don't know something or it requires current info, say so plainly instead of guessing."
)

async def start_command(update: Update, context) -> None:
    """Sends a friendly welcome message when the command /start is issued."""
    user = update.effective_user
    welcome_message = f"Hello {user.mention_html()}! I'm your AI assistant. How can I help you today?" # noqa: E501
    await update.message.reply_html(welcome_message)

async def help_command(update: Update, context) -> None:
    """Sends a help message when the command /help is issued."""
    help_text = (
        "*Available Commands:*\n"
        "/start - Start the conversation and get a welcome message.\n"
        "/help - Get information about available commands.\n"
        "/clear - Clear our conversation history.\n\n"
        "Just send me a message, and I'll do my best to assist you!"
    )
    await send_message(update, help_text, parse_mode='Markdown')

async def clear_command(update: Update, context) -> None:
    """Clears the conversation history for the user."""
    user_id = update.effective_user.id
    if user_id in conversation_memory:
        conversation_memory[user_id].clear()
        await send_message(update, "Conversation history cleared! We can start fresh now.")
    else:
        await send_message(update, "No conversation history to clear.")

async def handle_message(update: Update, context) -> None:
    """Handles a regular message, sends it to OpenAI, and replies."""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Add user message to conversation memory
    conversation_memory[user_id].append({"role": "user", "content": user_message})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(list(conversation_memory[user_id]))

    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1000,
        )
        ai_response_content = response.choices[0].message.content

        if not ai_response_content:
            ai_response_content = "Sorry, I couldn't generate a response. Please try again."

        # Add AI response to conversation memory
        conversation_memory[user_id].append({"role": "assistant", "content": ai_response_content})

        # Split long messages
        for i in range(0, len(ai_response_content), MAX_MESSAGE_LENGTH):
            chunk = ai_response_content[i:i + MAX_MESSAGE_LENGTH]
            await send_message(update, chunk, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error communicating with OpenAI: {e}")
        await send_message(update, "Apologies, I'm having trouble connecting to my brain right now. Please try again later.")

async def send_message(update: Update, text: str, parse_mode: str = None) -> None:
    """Helper function to send messages, trying Markdown first, then plain text."""
    try:
        if parse_mode == 'Markdown':
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(text)
    except Exception as e:
        logger.warning(f"Failed to send message with Markdown: {e}. Sending as plain text.")
        try:
            await update.message.reply_text(text)
        except Exception as e2:
            logger.error(f"Failed to send plain text: {e2}")

def main() -> None:
    """Starts the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    main()
