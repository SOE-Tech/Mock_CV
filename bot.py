import os
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import requests

# 1. Read token from environment variable (on Render) or fallback to your token (local)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "9131337534:AAHkWrcF0d6FJ6Ds3FRzMNMUabV0tVO_bzU")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

DEXSCREENER_API_URL = "https://api.dexscreener.com/latest/dex/search?q="

def get_token_data(query: str):
    """Fetches pair and price information from DexScreener API."""
    try:
        response = requests.get(f"{DEXSCREENER_API_URL}{query}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            pairs = data.get("pairs")
            if pairs and len(pairs) > 0:
                # Return the highest liquidity pair
                return pairs[0]
        return None
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "🤖 <b>Welcome to Meta Crypto Tracker Bot!</b>\n\n"
        "Use this bot to get real-time token metrics from any chain (Base, Solana, Ethereum, etc.).\n\n"
        "<b>Available Commands:</b>\n"
        "• <code>/price &lt;symbol or contract&gt;</code> - Get instant live price, volume, and chart.\n"
        "• <code>/ping</code> - Check if the bot is live.\n\n"
        "<i>Example:</i> <code>/price PEPE</code> or <code>/price 0x...</code>"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['ping'])
def ping(message):
    bot.reply_to(message, "🟢 <b>Bot is online and active!</b>")

@bot.message_handler(commands=['price'])
def handle_price(message):
    args = message.text.split()[1:]
    if not args:
        bot.reply_to(
            message, 
            "⚠️ <b>Please specify a token or contract address.</b>\nExample: <code>/price VIRTUAL</code> or <code>/price 0x...</code>"
        )
        return

    query = args[0]
    bot.send_chat_action(message.chat.id, 'typing')
    
    pair = get_token_data(query)
    if not pair:
        bot.reply_to(message, f"❌ No liquidity pair found on DexScreener for <code>{query}</code>.")
        return

    # Extract metrics safely
    base_token = pair.get("baseToken", {})
    token_name = base_token.get("name", "Unknown")
    token_symbol = base_token.get("symbol", "UNKNOWN")
    price_usd = pair.get("priceUsd", "0.00")
    chain_id = pair.get("chainId", "unknown").upper()
    dex_id = pair.get("dexId", "unknown").capitalize()
    
    # 24h stats
    price_change_24h = pair.get("priceChange", {}).get("h24", 0)
    change_emoji = "🟢" if float(price_change_24h or 0) >= 0 else "🔴"
    
    volume_24h = pair.get("volume", {}).get("h24", 0)
    liquidity_usd = pair.get("liquidity", {}).get("usd", 0)
    fdv = pair.get("fdv", 0)
    pair_url = pair.get("url", "https://dexscreener.com")

    # Format numbers cleanly
    formatted_vol = f"${volume_24h:,.0f}" if volume_24h else "N/A"
    formatted_liq = f"${liquidity_usd:,.0f}" if liquidity_usd else "N/A"
    formatted_fdv = f"${fdv:,.0f}" if fdv else "N/A"

    msg = (
        f"📊 <b>{token_name} ({token_symbol})</b> | <code>{chain_id}</code>\n"
        f"DEX: <b>{dex_id}</b>\n\n"
        f"💵 <b>Price:</b> <code>${float(price_usd):,.6f}</code>\n"
        f"{change_emoji} <b>24h Change:</b> <code>{price_change_24h}%</code>\n"
        f"💧 <b>Liquidity:</b> <code>{formatted_liq}</code>\n"
        f"📈 <b>24h Volume:</b> <code>{formatted_vol}</code>\n"
        f"💎 <b>FDV / Market Cap:</b> <code>{formatted_fdv}</code>\n\n"
        f"🔗 <a href='{pair_url}'>View Live Chart on DexScreener</a>"
    )
    
    bot.reply_to(message, msg, disable_web_page_preview=False)

# --- DUMMY HTTP SERVER FOR RENDER FREE WEB SERVICE ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Telegram Bot is running!")

    def log_message(self, format, *args):
        return  # Suppress excessive health check logs

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

if __name__ == '__main__':
    print("Starting background web server for Render...")
    threading.Thread(target=run_health_server, daemon=True).start()

    print("Bot is starting polling...")
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=20)
        except Exception as e:
            print(f"Connection issue: {e}. Retrying in 5 seconds...")
            time.sleep(5)