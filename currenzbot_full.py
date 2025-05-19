import os
import json
import logging
import threading
import datetime
import time
import re
import requests
from collections import defaultdict, Counter
from flask import Flask, render_template

# --- CONFIG SECTION ---
# You can replace these with your actual credentials
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # Replace with your bot token
WISE_REFERRAL_LINK = "https://wise.com/invite/dic/mdmonjuruli1"

# Emoji dictionary
EMOJI = {
    "sparkles": "✨",
    "exchange": "💱",
    "chart": "📊",
    "money": "💰",
    "globe": "🌏",
    "rocket": "🚀",
    "information": "ℹ️"
}

# Currency settings
DEFAULT_BASE_CURRENCY = "USD"
POPULAR_CURRENCIES = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "INR", "BTC"]

# Currency symbols
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
    "CAD": "C$",
    "AUD": "A$",
    "CHF": "Fr",
    "CNY": "¥",
    "INR": "₹",
    "BTC": "₿"
}

# --- LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- CURRENCY MODULE ---
# Exchange rates API URL
EXCHANGE_RATES_API_URL = "https://open.er-api.com/v6/latest/"

def get_currency_emoji(currency_code):
    """Get the emoji flag for a currency code."""
    # For most currency codes, the first two letters correspond to the country code
    # We can convert these to regional indicator symbols to get the flag emoji
    if len(currency_code) >= 2:
        country_code = currency_code[:2]
        # Convert to regional indicator symbols (127462 is the Unicode offset for these symbols)
        return "".join([chr(ord(c.upper()) + 127397) for c in country_code])
    return EMOJI['money']  # Default to a money emoji if no flag found

def get_exchange_rates(base_currency="USD"):
    """Get the latest exchange rates for the given base currency.
    This function uses the Open Exchange Rates API.
    """
    try:
        logger.info(f"Requesting URL: {EXCHANGE_RATES_API_URL}{base_currency}")
        response = requests.get(f"{EXCHANGE_RATES_API_URL}{base_currency}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('result') == 'success':
                return data.get('rates', {})
            else:
                logger.error(f"API error: {data.get('error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error getting exchange rates: {e}")
        return None

def convert_currency(amount, from_currency, to_currency):
    """Convert an amount from one currency to another."""
    try:
        # If from_currency is the same as to_currency, return the amount
        if from_currency == to_currency:
            return amount
        
        # Get the exchange rates with from_currency as the base
        rates = get_exchange_rates(from_currency)
        
        if rates and to_currency in rates:
            # Calculate the conversion
            return amount * rates[to_currency]
        else:
            logger.error(f"Currency not found: {to_currency}")
            return None
    except Exception as e:
        logger.error(f"Error converting currency: {e}")
        return None

def format_currency(amount, currency_code):
    """Format a currency amount with its symbol."""
    symbol = CURRENCY_SYMBOLS.get(currency_code, currency_code)
    return f"{symbol} {amount:.2f}"

def get_currency_comparison(base_currency, target_currencies=None):
    """Get a comparison of exchange rates for multiple currencies."""
    try:
        # If no target currencies specified, use a default list
        if not target_currencies:
            target_currencies = ["USD", "EUR", "GBP", "JPY", "CNY"]
        
        # Get the exchange rates
        rates = get_exchange_rates(base_currency)
        
        if rates:
            # Filter for only the requested target currencies
            comparison = {}
            for currency in target_currencies:
                if currency in rates:
                    comparison[currency] = rates[currency]
            
            return comparison
        else:
            logger.error(f"Could not get rates for {base_currency}")
            return None
    except Exception as e:
        logger.error(f"Error comparing currencies: {e}")
        return None

def get_supported_currencies():
    """Get a list of supported currencies with their emojis."""
    try:
        # Get the exchange rates for USD to see all supported currencies
        rates = get_exchange_rates("USD")
        
        if rates:
            # Create a dictionary of currency codes and their names (hardcoded for now)
            currencies = {
                "USD": "US Dollar",
                "EUR": "Euro",
                "GBP": "British Pound",
                "JPY": "Japanese Yen",
                "AUD": "Australian Dollar",
                "CAD": "Canadian Dollar",
                "CHF": "Swiss Franc",
                "CNY": "Chinese Yuan",
                "HKD": "Hong Kong Dollar",
                "NZD": "New Zealand Dollar",
                "SEK": "Swedish Krona",
                "KRW": "South Korean Won",
                "SGD": "Singapore Dollar",
                "NOK": "Norwegian Krone",
                "MXN": "Mexican Peso",
                "INR": "Indian Rupee",
                "RUB": "Russian Ruble",
                "ZAR": "South African Rand",
                "TRY": "Turkish Lira",
                "BRL": "Brazilian Real",
                "TWD": "Taiwan Dollar",
                "DKK": "Danish Krone",
                "PLN": "Polish Zloty",
                "THB": "Thai Baht",
                "IDR": "Indonesian Rupiah",
                "HUF": "Hungarian Forint",
                "CZK": "Czech Koruna",
                "ILS": "Israeli Shekel",
                "CLP": "Chilean Peso",
                "PHP": "Philippine Peso",
                "AED": "UAE Dirham",
                "COP": "Colombian Peso",
                "SAR": "Saudi Riyal",
                "MYR": "Malaysian Ringgit",
                "RON": "Romanian Leu",
                "BTC": "Bitcoin"
            }
            
            # For any currencies in the rates that are not in our hardcoded list,
            # add them with a generic name
            for currency in rates.keys():
                if currency not in currencies:
                    currencies[currency] = f"{currency} Currency"
            
            return currencies
        else:
            logger.error("Could not get supported currencies")
            return None
    except Exception as e:
        logger.error(f"Error getting supported currencies: {e}")
        return None

# --- ANALYTICS MODULE ---
# Path to the analytics data file
ANALYTICS_FILE = 'user_analytics.json'

class BotAnalytics:
    """Class to handle bot usage analytics."""
    
    def __init__(self):
        """Initialize the analytics system."""
        self.data = self._load_data()
        
    def _load_data(self):
        """Load analytics data from the JSON file."""
        if os.path.exists(ANALYTICS_FILE):
            try:
                with open(ANALYTICS_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError) as e:
                logger.error(f"Error loading analytics data: {e}")
                return self._get_empty_data()
        else:
            return self._get_empty_data()
    
    def _get_empty_data(self):
        """Create an empty analytics data structure."""
        return {
            "users": {},
            "commands": {},
            "conversions": [],
            "first_seen": {}
        }
    
    def _save_data(self):
        """Save analytics data to the JSON file."""
        try:
            with open(ANALYTICS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving analytics data: {e}")
    
    def track_user(self, user_id, username=None, first_name=None):
        """Track a user interaction."""
        user_id = str(user_id)  # Convert to string for JSON compatibility
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "interactions": 0,
                "first_seen": today,
                "last_seen": today,
                "username": username,
                "first_name": first_name,
                "monthly_usage": {}
            }
            self.data["first_seen"][user_id] = today
        
        # Update user data
        self.data["users"][user_id]["interactions"] += 1
        self.data["users"][user_id]["last_seen"] = today
        
        # Update username and first_name if provided
        if username:
            self.data["users"][user_id]["username"] = username
        if first_name:
            self.data["users"][user_id]["first_name"] = first_name
        
        # Update monthly usage
        month_key = datetime.datetime.now().strftime('%Y-%m')
        if month_key not in self.data["users"][user_id]["monthly_usage"]:
            self.data["users"][user_id]["monthly_usage"][month_key] = 0
        self.data["users"][user_id]["monthly_usage"][month_key] += 1
        
        self._save_data()
        
    def track_command(self, command, user_id=None):
        """Track a command usage."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        if command not in self.data["commands"]:
            self.data["commands"][command] = {
                "count": 0,
                "users": [],
                "by_date": {}
            }
        
        self.data["commands"][command]["count"] += 1
        
        if user_id:
            user_id = str(user_id)
            if user_id not in self.data["commands"][command]["users"]:
                self.data["commands"][command]["users"].append(user_id)
        
        if today not in self.data["commands"][command]["by_date"]:
            self.data["commands"][command]["by_date"][today] = 0
        self.data["commands"][command]["by_date"][today] += 1
        
        self._save_data()
    
    def track_conversion(self, from_currency, to_currency, amount, user_id=None):
        """Track a currency conversion."""
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        
        conversion = {
            "date": today,
            "from": from_currency,
            "to": to_currency,
            "amount": amount
        }
        
        if user_id:
            conversion["user_id"] = str(user_id)
        
        self.data["conversions"].append(conversion)
        self._save_data()
    
    def get_monthly_users(self, month=None):
        """Get number of monthly active users."""
        if not month:
            month = datetime.datetime.now().strftime('%Y-%m')
        
        monthly_users = set()
        for user_id, user_data in self.data["users"].items():
            if "monthly_usage" in user_data and month in user_data["monthly_usage"]:
                monthly_users.add(user_id)
        
        return {
            "count": len(monthly_users),
            "users": list(monthly_users)
        }
    
    def get_new_users(self, month=None):
        """Get number of new users in the given month."""
        if not month:
            month = datetime.datetime.now().strftime('%Y-%m')
        
        new_users = []
        for user_id, first_seen in self.data["first_seen"].items():
            if first_seen.startswith(month):
                new_users.append(user_id)
        
        return {
            "count": len(new_users),
            "users": new_users
        }
    
    def get_top_commands(self, limit=5):
        """Get the most used commands."""
        commands = [(cmd, data["count"]) for cmd, data in self.data["commands"].items()]
        return sorted(commands, key=lambda x: x[1], reverse=True)[:limit]
    
    def get_popular_conversions(self, limit=5):
        """Get the most popular currency conversions."""
        pairs = [(conv["from"], conv["to"]) for conv in self.data["conversions"]]
        counts = Counter(pairs)
        return counts.most_common(limit)
    
    def get_user_count(self):
        """Get the total number of users."""
        return len(self.data["users"])
    
    def get_monthly_stats(self, month=None):
        """Get comprehensive monthly statistics."""
        if not month:
            month = datetime.datetime.now().strftime('%Y-%m')
        
        active_users = self.get_monthly_users(month)
        new_users = self.get_new_users(month)
        
        # Count conversions in this month
        conversions_count = 0
        for conv in self.data["conversions"]:
            if conv["date"].startswith(month):
                conversions_count += 1
        
        # Count commands in this month
        commands_count = 0
        for cmd, data in self.data["commands"].items():
            for date, count in data["by_date"].items():
                if date.startswith(month):
                    commands_count += count
        
        return {
            "month": month,
            "active_users": active_users["count"],
            "new_users": new_users["count"],
            "total_users": self.get_user_count(),
            "total_commands": commands_count,
            "total_conversions": conversions_count
        }

# Initialize the analytics system
analytics = BotAnalytics()

# --- KEEP ALIVE MODULE ---
# Track the bot's start time for uptime display
start_time = datetime.datetime.now()

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "currenzbot-secret-key")

@app.route('/')
def home():
    """Home page to show the bot is alive."""
    # Calculate uptime
    uptime = datetime.datetime.now() - start_time
    days, remainder = divmod(uptime.total_seconds(), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    uptime_str = f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes"
    
    return render_template('index.html', 
                          uptime=uptime_str, 
                          last_updated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/ping')
def ping():
    """Endpoint for pinging the server to keep it alive."""
    return "Pong! Bot is alive."

@app.route('/analytics')
def analytics_dashboard():
    """Display bot analytics dashboard."""
    try:
        # Get current month and year
        current_month = datetime.datetime.now().strftime('%Y-%m')
        
        # Get monthly stats
        monthly_stats = analytics.get_monthly_stats(current_month)
        
        # Get top commands
        top_commands = analytics.get_top_commands(limit=5)
        
        # Get popular conversions
        popular_conversions = analytics.get_popular_conversions(limit=5)
        
        # Calculate uptime
        uptime = datetime.datetime.now() - start_time
        days, remainder = divmod(uptime.total_seconds(), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{int(days)} days, {int(hours)} hours, {int(minutes)} minutes"
        
        return render_template('analytics.html',
                              monthly_stats=monthly_stats,
                              top_commands=top_commands,
                              popular_conversions=popular_conversions,
                              uptime=uptime_str,
                              current_month=current_month)
    except Exception as e:
        logger.error(f"Error loading analytics: {str(e)}")
        return f"Error loading analytics: {str(e)}", 500

def run_flask():
    """Run the Flask app in a separate thread."""
    logger.info("Starting Flask server for keep-alive mechanism")
    app.run(host='0.0.0.0', port=5000, debug=False)

def ping_server():
    """Ping the server every 5 minutes to keep it alive."""
    # Try to get Replit domain from environment, or use localhost for testing
    host = os.environ.get("REPLIT_DOMAIN", "localhost:5000")
    
    # Use HTTPS for Replit domain, HTTP for localhost
    url = f"https://{host}/ping" if "replit" in host else "http://localhost:5000/ping"
    
    logger.info(f"Keep-alive pinger will ping: {url}")
    
    while True:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            response = requests.get(url)
            logger.info(f"[{current_time}] Ping status: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"[{current_time}] Error pinging server: {str(e)}")
        
        # Sleep for 5 minutes (300 seconds)
        # This helps keep the Replit instance alive on the free tier
        time.sleep(300)

def start_keep_alive():
    """Start the keep-alive web server and pinger in separate threads."""
    # Start web server thread
    web_thread = threading.Thread(target=run_flask)
    web_thread.daemon = True  # Set daemon to True so it exits when the main thread exits
    web_thread.start()
    logger.info("Keep-alive web server started")
    
    # Start pinger thread
    pinger_thread = threading.Thread(target=ping_server)
    pinger_thread.daemon = True
    pinger_thread.start()
    logger.info("Keep-alive pinger started")

# --- TELEGRAM BOT MODULE ---
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Updater, CommandHandler, MessageHandler, CallbackQueryHandler,
        CallbackContext, ConversationHandler, Filters
    )
except ImportError:
    # Handle case where python-telegram-bot isn't installed
    logger.error("python-telegram-bot not installed. Please install it with 'pip install python-telegram-bot==13.15'")
    # Define mock classes to avoid errors in the code below
    class Update: pass
    class CallbackContext: pass
    class ConversationHandler:
        END = 0
    # Exit with error
    import sys
    print("ERROR: python-telegram-bot not installed. Please install it with 'pip install python-telegram-bot==13.15'")
    if not os.environ.get("TESTING") == "1":
        sys.exit(1)

# Conversation states
SELECTING_BASE, SELECTING_TARGET, ENTERING_AMOUNT = range(3)

# User data storage
user_conversion_state = {}

def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the command /start is issued."""
    user = update.effective_user
    
    # Track user analytics
    analytics.track_user(
        user.id, 
        username=user.username, 
        first_name=user.first_name
    )
    analytics.track_command('start', user.id)
    
    welcome_message = (
        f"{EMOJI['sparkles']} *Welcome to CurrenzBot!* {EMOJI['sparkles']}\n\n"
        f"Hello {user.first_name}! I'm your currency exchange assistant. {EMOJI['exchange']}\n\n"
        f"Here's what I can do for you:\n"
        f"{EMOJI['chart']} Check exchange rates\n"
        f"{EMOJI['money']} Convert between currencies\n"
        f"{EMOJI['globe']} View supported currencies\n\n"
        f"*Quick Tip:* You can directly type your conversion request like:\n"
        f"`100 USD to EUR` or `50 USDT to BDT`\n\n"
        f"Use /help to see all available commands."
    )
    
    # Create a keyboard with the Wise referral button
    keyboard = [
        [InlineKeyboardButton(
            f"{EMOJI['rocket']} Convert currency with best rate", 
            url=WISE_REFERRAL_LINK
        )]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_markdown_v2(welcome_message, reply_markup=reply_markup)

def help_command(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /help is issued."""
    user = update.effective_user
    
    # Track analytics
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    analytics.track_command('help', user.id)
    
    help_text = (
        f"{EMOJI['information']} *CurrenzBot Help* {EMOJI['information']}\n\n"
        f"Here are the commands you can use:\n\n"
        f"/start - Start the bot and get a welcome message\n"
        f"/help - Show this help message\n"
        f"/rates [currency] - Get exchange rates for a base currency\n"
        f"/convert - Start currency conversion wizard\n"
        f"/currencies - List all supported currencies\n"
        f"/compare [currency] [target1] [target2] ... - Compare a base currency to others\n\n"
        f"*Direct Conversion:*\n"
        f"Simply type your request in this format:\n"
        f"`amount from_currency to to_currency`\n"
        f"Example: `100 USD to EUR` or `50 USDT in BDT`"
    )
    
    update.message.reply_markdown_v2(help_text)

def rates_command(update: Update, context: CallbackContext) -> None:
    """Get exchange rates for a base currency."""
    user = update.effective_user
    
    # Track analytics
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    analytics.track_command('rates', user.id)
    
    base_currency = DEFAULT_BASE_CURRENCY
    
    # Check if a base currency was provided
    if context.args and len(context.args) > 0:
        base_currency = context.args[0].upper()
    
    update.message.reply_text(f"Fetching exchange rates for {base_currency}...")
    
    try:
        # Get the exchange rates
        rates = get_exchange_rates(base_currency)
        
        if rates:
            # Create the response message
            response = f"{get_currency_emoji(base_currency)} *{base_currency} Exchange Rates*\n\n"
            
            # Add popular currencies first
            response += "*Popular Currencies:*\n"
            for currency in POPULAR_CURRENCIES:
                if currency != base_currency and currency in rates:
                    emoji = get_currency_emoji(currency)
                    response += f"{emoji} *{currency}*: {rates[currency]:.4f}\n"
            
            # Add other currencies
            response += "\n*Other Currencies:*\n"
            for currency, rate in rates.items():
                if currency not in POPULAR_CURRENCIES and currency != base_currency:
                    emoji = get_currency_emoji(currency)
                    response += f"{emoji} *{currency}*: {rate:.4f}\n"
            
            # Add Wise referral button
            keyboard = [
                [InlineKeyboardButton(
                    f"{EMOJI['rocket']} Convert {base_currency} with best rate", 
                    url=WISE_REFERRAL_LINK
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_markdown_v2(response, reply_markup=reply_markup)
        else:
            update.message.reply_text(
                f"Sorry, I couldn't get exchange rates for {base_currency}. "
                "Please try a different currency code."
            )
    except Exception as e:
        logger.error(f"Error in rates_command: {e}")
        update.message.reply_text(
            f"Sorry, there was an error getting exchange rates. "
            "Please try again later."
        )

def currencies_command(update: Update, context: CallbackContext) -> None:
    """List supported currencies."""
    user = update.effective_user
    
    # Track analytics
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    analytics.track_command('currencies', user.id)
    
    update.message.reply_text("Fetching supported currencies...")
    
    try:
        currencies = get_supported_currencies()
        
        if currencies:
            # Create the response message
            response = f"{EMOJI['globe']} *Supported Currencies*\n\n"
            
            # Add popular currencies first
            response += "*Popular Currencies:*\n"
            for currency in POPULAR_CURRENCIES:
                emoji = get_currency_emoji(currency)
                name = currencies.get(currency, "")
                response += f"{emoji} *{currency}* - {name}\n"
            
            # Add other currencies
            response += "\n*Other Currencies:*\n"
            for currency, name in currencies.items():
                if currency not in POPULAR_CURRENCIES:
                    emoji = get_currency_emoji(currency)
                    response += f"{emoji} *{currency}* - {name}\n"
            
            update.message.reply_markdown_v2(response)
        else:
            update.message.reply_text(
                "Sorry, I couldn't get the list of supported currencies. "
                "Please try again later."
            )
    except Exception as e:
        logger.error(f"Error in currencies_command: {e}")
        update.message.reply_text(
            "Sorry, there was an error getting the currency list. "
            "Please try again later."
        )

def compare_command(update: Update, context: CallbackContext) -> None:
    """Compare a base currency to target currencies."""
    user = update.effective_user
    
    # Track analytics
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    analytics.track_command('compare', user.id)
    
    # Check if arguments were provided
    if not context.args or len(context.args) < 2:
        update.message.reply_text(
            "Please provide a base currency and at least one target currency to compare.\n"
            "Example: /compare USD EUR GBP JPY"
        )
        return
    
    base_currency = context.args[0].upper()
    target_currencies = [currency.upper() for currency in context.args[1:]]
    
    update.message.reply_text(
        f"Comparing {base_currency} to {', '.join(target_currencies)}..."
    )
    
    try:
        # Get the comparison
        comparison = get_currency_comparison(base_currency, target_currencies)
        
        if comparison:
            # Create the response message
            response = (
                f"{EMOJI['chart']} *Currency Comparison*\n\n"
                f"Base currency: {get_currency_emoji(base_currency)} *{base_currency}*\n\n"
            )
            
            for currency, rate in comparison.items():
                emoji = get_currency_emoji(currency)
                response += f"{emoji} *{currency}*: {rate:.4f}\n"
            
            # Add Wise referral button
            keyboard = [
                [InlineKeyboardButton(
                    f"{EMOJI['rocket']} Convert {base_currency} with best rate", 
                    url=WISE_REFERRAL_LINK
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_markdown_v2(response, reply_markup=reply_markup)
        else:
            update.message.reply_text(
                f"Sorry, I couldn't compare {base_currency} to the target currencies. "
                "Please check the currency codes and try again."
            )
    except Exception as e:
        logger.error(f"Error in compare_command: {e}")
        update.message.reply_text(
            "Sorry, there was an error comparing the currencies. "
            "Please try again later."
        )

def convert_command(update: Update, context: CallbackContext) -> int:
    """Start the conversion process by asking for the base currency."""
    user = update.effective_user
    
    # Track analytics
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    analytics.track_command('convert', user.id)
    
    # Reset user's conversion state
    user_conversion_state[update.effective_user.id] = {}
    
    # Get supported currencies
    currencies = get_supported_currencies()
    
    if not currencies:
        update.message.reply_text(
            "Sorry, I couldn't get the list of supported currencies. "
            "Please try again later."
        )
        return ConversationHandler.END
    
    # Create inline keyboard with popular currencies
    keyboard = []
    row = []
    for i, currency in enumerate(POPULAR_CURRENCIES):
        emoji = get_currency_emoji(currency)
        row.append(InlineKeyboardButton(f"{emoji} {currency}", callback_data=currency))
        if (i + 1) % 3 == 0 or i == len(POPULAR_CURRENCIES) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        f"Please select the base currency (from):",
        reply_markup=reply_markup
    )
    
    return SELECTING_BASE

def handle_base_selection(update: Update, context: CallbackContext) -> int:
    """Handle the selection of the base currency."""
    query = update.callback_query
    query.answer()
    
    user_id = update.effective_user.id
    user_conversion_state[user_id]['base_currency'] = query.data
    
    # Get supported currencies
    currencies = get_supported_currencies()
    
    # Create inline keyboard with popular currencies
    keyboard = []
    row = []
    for i, currency in enumerate(POPULAR_CURRENCIES):
        emoji = get_currency_emoji(currency)
        row.append(InlineKeyboardButton(f"{emoji} {currency}", callback_data=currency))
        if (i + 1) % 3 == 0 or i == len(POPULAR_CURRENCIES) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        f"Base currency: {get_currency_emoji(query.data)} {query.data}\n\n"
        f"Now, please select the target currency (to):",
        reply_markup=reply_markup
    )
    
    return SELECTING_TARGET

def handle_target_selection(update: Update, context: CallbackContext) -> int:
    """Handle the selection of the target currency."""
    query = update.callback_query
    query.answer()
    
    user_id = update.effective_user.id
    user_conversion_state[user_id]['target_currency'] = query.data
    
    base_currency = user_conversion_state[user_id]['base_currency']
    
    query.edit_message_text(
        f"Base currency: {get_currency_emoji(base_currency)} {base_currency}\n"
        f"Target currency: {get_currency_emoji(query.data)} {query.data}\n\n"
        f"Please enter the amount to convert:"
    )
    
    return ENTERING_AMOUNT

def handle_amount_entry(update: Update, context: CallbackContext) -> int:
    """Handle the entry of the amount to convert."""
    user_id = update.effective_user.id
    
    try:
        # Parse the amount
        amount = float(update.message.text.strip())
        
        # Get the conversion currencies
        base_currency = user_conversion_state[user_id]['base_currency']
        target_currency = user_conversion_state[user_id]['target_currency']
        
        # Track conversion in analytics
        analytics.track_conversion(base_currency, target_currency, amount, user_id)
        
        update.message.reply_text(f"Converting {amount} {base_currency} to {target_currency}...")
        
        # Perform the conversion
        result = convert_currency(amount, base_currency, target_currency)
        
        if result is not None:
            # Create the response message
            response = (
                f"{EMOJI['exchange']} *Currency Conversion*\n\n"
                f"{amount:.2f} {get_currency_emoji(base_currency)} *{base_currency}* = "
                f"{result:.2f} {get_currency_emoji(target_currency)} *{target_currency}*\n\n"
                f"Exchange rate: 1 {base_currency} = {result/amount:.4f} {target_currency}"
            )
            
            # Add Wise referral button
            keyboard = [
                [InlineKeyboardButton(
                    f"{EMOJI['rocket']} Convert with best rate", 
                    url=WISE_REFERRAL_LINK
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_markdown_v2(response, reply_markup=reply_markup)
        else:
            update.message.reply_text(
                f"Sorry, I couldn't convert {base_currency} to {target_currency}. "
                "Please check the currency codes and try again."
            )
    except ValueError:
        update.message.reply_text(
            "Please enter a valid number for the amount."
        )
        return ENTERING_AMOUNT
    except Exception as e:
        logger.error(f"Error in handle_amount_entry: {e}")
        update.message.reply_text(
            "Sorry, there was an error converting the currencies. "
            "Please try again later."
        )
    
    # Clear the user's conversion state
    if user_id in user_conversion_state:
        del user_conversion_state[user_id]
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext) -> int:
    """Cancel the conversation."""
    update.message.reply_text(
        "Conversion cancelled. If you need anything else, just ask!"
    )
    
    # Clear the user's conversion state
    user_id = update.effective_user.id
    if user_id in user_conversion_state:
        del user_conversion_state[user_id]
    
    return ConversationHandler.END

def handle_unknown(update: Update, context: CallbackContext) -> None:
    """Handle unknown commands or messages.
    Tries to parse natural language conversion requests like '100 USD to EUR'
    """
    message_text = update.message.text.strip()
    user = update.effective_user
    
    # Track user
    analytics.track_user(user.id, username=user.username, first_name=user.first_name)
    
    # Try to match natural language conversion patterns
    # Pattern 1: "100 USD to EUR" or "100 USD in EUR"
    pattern1 = r'(\d+(?:\.\d+)?)\s+([A-Za-z]{3,4})\s+(?:to|in|into)\s+([A-Za-z]{3,4})'
    match1 = re.search(pattern1, message_text, re.IGNORECASE)
    
    # Pattern 2: "Convert 100 USD to EUR" or "Change 100 USD to EUR"
    pattern2 = r'(?:convert|change|exchange)\s+(\d+(?:\.\d+)?)\s+([A-Za-z]{3,4})\s+(?:to|in|into)\s+([A-Za-z]{3,4})'
    match2 = re.search(pattern2, message_text, re.IGNORECASE)
    
    if match1:
        # Extract amount and currencies from pattern 1
        amount_str, from_currency, to_currency = match1.groups()
        
        # Clean and normalize currencies
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        try:
            amount = float(amount_str)
            
            # Track command
            analytics.track_command('natural_conversion', user.id)
            
            # Process the conversion
            process_natural_conversion(update, amount, from_currency, to_currency)
            
            return
        except ValueError:
            pass
    
    elif match2:
        # Extract amount and currencies from pattern 2
        amount_str, from_currency, to_currency = match2.groups()
        
        # Clean and normalize currencies
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        try:
            amount = float(amount_str)
            
            # Track command
            analytics.track_command('natural_conversion', user.id)
            
            # Process the conversion
            process_natural_conversion(update, amount, from_currency, to_currency)
            
            return
        except ValueError:
            pass
    
    # If no pattern matched, reply with help
    update.message.reply_text(
        "I'm not sure what you mean. Here are some examples of what you can ask:\n\n"
        "• 100 USD to EUR\n"
        "• 50 USDT in BDT\n"
        "• Convert 200 JPY to CAD\n\n"
        "Or use /help to see all available commands."
    )

def process_natural_conversion(update, amount, from_currency, to_currency):
    """Process currency conversion from natural language input."""
    
    # Track conversion in analytics
    analytics.track_conversion(from_currency, to_currency, amount, update.effective_user.id)
    
    update.message.reply_text(f"Converting {amount} {from_currency} to {to_currency}...")
    
    try:
        # Perform the conversion
        result = convert_currency(amount, from_currency, to_currency)
        
        if result is not None:
            # Create the response message
            response = (
                f"{EMOJI['exchange']} *Currency Conversion*\n\n"
                f"{amount:.2f} {get_currency_emoji(from_currency)} *{from_currency}* = "
                f"{result:.2f} {get_currency_emoji(to_currency)} *{to_currency}*\n\n"
                f"Exchange rate: 1 {from_currency} = {result/amount:.4f} {to_currency}"
            )
            
            # Add Wise referral button
            keyboard = [
                [InlineKeyboardButton(
                    f"{EMOJI['rocket']} Convert with best rate", 
                    url=WISE_REFERRAL_LINK
                )]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            update.message.reply_markdown_v2(response, reply_markup=reply_markup)
        else:
            update.message.reply_text(
                f"Sorry, I couldn't convert {from_currency} to {to_currency}. "
                "Please check the currency codes and try again."
            )
    except Exception as e:
        logger.error(f"Error in process_natural_conversion: {e}")
        update.message.reply_text(
            "Sorry, there was an error converting the currencies. "
            "Please try again later."
        )

def create_application():
    """Create and configure the bot application."""
    
    logger.info("Starting CurrenzBot")
    
    # Check if the bot token is available
    if not TELEGRAM_TOKEN:
        logger.error("No Telegram token provided!")
        return None
    
    try:
        # Create the Updater and pass it the bot's token
        updater = Updater(TELEGRAM_TOKEN)
        
        # Get the dispatcher to register handlers
        dispatcher = updater.dispatcher
        
        # Create the conversation handler for currency conversion
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('convert', convert_command)],
            states={
                SELECTING_BASE: [CallbackQueryHandler(handle_base_selection)],
                SELECTING_TARGET: [CallbackQueryHandler(handle_target_selection)],
                ENTERING_AMOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_amount_entry)]
            },
            fallbacks=[CommandHandler('cancel', cancel)]
        )
        
        # Register handlers
        dispatcher.add_handler(CommandHandler('start', start))
        dispatcher.add_handler(CommandHandler('help', help_command))
        dispatcher.add_handler(CommandHandler('rates', rates_command))
        dispatcher.add_handler(CommandHandler('currencies', currencies_command))
        dispatcher.add_handler(CommandHandler('compare', compare_command))
        dispatcher.add_handler(conv_handler)
        
        # Add handler for unknown messages or commands
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_unknown))
        
        # Log errors
        def error_handler(update, context):
            """Log Errors caused by Updates."""
            logger.error(f"Update {update} caused error {context.error}")
        
        dispatcher.add_error_handler(error_handler)
        
        # Start the bot
        logger.info("Starting bot polling")
        
        # For testing purposes, we can return a mock updater for non-polling
        if os.environ.get("TESTING") == "1":
            class MockUpdater:
                def start_polling(self): pass
                def idle(self): pass
            return MockUpdater()
        
        return updater
    
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        return None

# --- MAIN FUNCTION ---
def main():
    """Start the bot and the keep-alive server."""
    # Start the keep-alive web server to prevent the bot from sleeping
    start_keep_alive()
    
    # Create and start the bot
    application = create_application()
    
    if application:
        # Start the bot
        application.start_polling()
        
        # Run the bot until the user presses Ctrl-C
        application.idle()
    else:
        logger.error("Failed to create bot application. Check your settings and try again.")

if __name__ == "__main__":
    main()