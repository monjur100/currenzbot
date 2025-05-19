# CurrenzBot - Telegram Currency Exchange Bot

CurrenzBot is a Telegram bot that provides real-time currency exchange rates with an eye-catching emoji interface and a Wise referral button.

## Features

- 💱 **Real-time Exchange Rates**: Get up-to-date currency exchange rates
- 📊 **Compare Currencies**: Compare a base currency to multiple target currencies
- 🌍 **Support for Multiple Currencies**: Wide range of supported currencies with flag emojis
- 💰 **Currency Conversion**: Convert amounts between different currencies
- 🚀 **Transfer Options**: Convert currency with best rates using Wise

## Bot Commands

- `/start` - Start the bot and see welcome message
- `/help` - Show this help message
- `/rates [currency]` - Get exchange rates (default: USD)
- `/convert` - Start currency conversion
- `/currencies` - List supported currencies
- `/compare [base] [target1] [target2]...` - Compare a base currency to others

## Examples

- `/rates EUR` - Show rates with EUR as base
- `/compare USD EUR GBP JPY` - Compare USD to EUR, GBP, and JPY

## Technical Information

- Built with Python using the python-telegram-bot library
- Uses exchangeratesapi.io for currency data
- Includes a Flask web server with keep-alive mechanism
- Automatic ping every 5 minutes to prevent the bot from sleeping

## Try the Bot

The bot is hosted on Replit and can be accessed via Telegram:
[CurrenzBot on Telegram](https://t.me/CurrenzBot)

## Web Interface

A simple web interface is available that shows the bot status and basic information.