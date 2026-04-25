from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, date
import os
import requests

load_dotenv()
app = FastAPI()

API_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MODELS_TO_TRY = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
]

sent_today = {}

def is_duplicate(symbol: str, signal: str) -> bool:
    key = f"{symbol}_{signal}"
    today = date.today()
    if key in sent_today and sent_today[key] == today:
        print(f"Duplicate blocked: {key}")
        return True
    sent_today[key] = today
    return False

class TradingAlert(BaseModel):
    symbol: str
    company: str = ""
    price: str
    signal: str
    timeframe: str = ""
    open: str = ""
    high: str = ""
    low: str = ""
    close: str = ""
    volume: str = ""
    avg_volume: str = ""
    ema20: str = ""
    ema50: str = ""
    ema200: str = ""
    rsi: str = ""
    rsi_signal: str = ""
    macd: str = ""
    macd_signal: str = ""
    macd_hist: str = ""
    stoch_k: str = ""
    stoch_d: str = ""
    bb_upper: str = ""
    bb_middle: str = ""
    bb_lower: str = ""
    atr: str = ""
    atr_percent: str = ""
    support: str = ""
    resistance: str = ""
    week52_high: str = ""
    week52_low: str = ""
    candle_pattern: str = ""
    buy_score: str = ""
    sell_score: str = ""


def build_prompt(alert: TradingAlert, display_name: str) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Score info
    score = alert.buy_score if "BUY" in alert.signal.upper() else alert.sell_score
    score_int = int(float(score)) if score else 0
    quality = "قوية جداً 🔥" if score_int >= 80 else "جيدة ✅" if score_int >= 60 else "متوسطة ⚠️"

    indicators = []
    if alert.rsi:
        indicators.append(f"RSI(14): {alert.rsi}" + (f" ({alert.rsi_signal})" if alert.rsi_signal else ""))
    if alert.macd and alert.macd_signal:
        indicators.append(f"MACD: {alert.macd} | Signal: {alert.macd_signal}" + (f" | Hist: {alert.macd_hist}" if alert.macd_hist else ""))
    if alert.stoch_k and alert.stoch_d:
        indicators.append(f"Stochastic: K={alert.stoch_k} D={alert.stoch_d}")
    if alert.ema20:
        indicators.append(f"EMA20: {alert.ema20}")
    if alert.ema50:
        indicators.append(f"EMA50: {alert.ema50}")
    if alert.ema200:
        indicators.append(f"EMA200: {alert.ema200}")
    if alert.bb_upper and alert.bb_lower:
        indicators.append(f"Bollinger: {alert.bb_lower} <- {alert.bb_middle} -> {alert.bb_upper}")
    if alert.atr:
        indicators.append(f"ATR: {alert.atr}" + (f" ({alert.atr_percent}%)" if alert.atr_percent else ""))
    if alert.volume:
        vol_line = f"Volume: {alert.volume}"
        if alert.avg_volume:
            vol_line += f" | Avg: {alert.avg_volume}"
        indicators.append(vol_line)
    if alert.support:
        indicators.append(f"Support: {alert.support}")
    if alert.resistance:
        indicators.append(f"Resistance: {alert.resistance}")
    if alert.candle_pattern:
        indicators.append(f"Candle Pattern: {alert.candle_pattern}")

    indicators_text = "\n".join(f"  - {i}" for i in indicators) if indicators else "  - لا توجد مؤشرات"

    prompt = f"""أنت محلل أسهم أمريكية متخصص في السوينج تريدنج.
الوقت: {now}

البيانات:
السهم: {display_name}
السعر: {alert.price}
الإشارة: {alert.signal}
الفريم: {alert.timeframe}
OHLC: O:{alert.open} H:{alert.high} L:{alert.low} C:{alert.close if alert.close else alert.price}
نقاط جودة الإشارة: {score}/100 - {quality}

المؤشرات:
{indicators_text}

رد بهذا الشكل الحرفي فقط، لا تضيف أي شي إضافي:

🎯 الإشارة: [وصف مختصر جداً]
📊 جودة الإعداد: [{score}/100] - [{quality}]
🔑 الدخول: [السعر]  |  الستوب: [السعر] ([%]%)  |  الهدف: [السعر] ([%]%)
📈 R:R: 1:[النسبة]
⏳ القرار: [ادخل الآن 🟢 / انتظر تأكيد 🟡 / تجنب 🔴]
📝 ملاحظة: [جملة واحدة فقط]"""
    return prompt


def ask_claude(prompt: str):
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    for model_name in MODELS_TO_TRY:
        body = {
            "model": model_name,
            "max_tokens": 400,
            "system": (
                "أنت محلل أسهم أمريكية محترف متخصص في السوينج تريدنج. "
                "ردودك دائماً بالعربية، مختصرة جداً، ومبنية على البيانات المعطاة فقط. "
                "لا تضيف أي شي خارج الشكل المطلوب."
            ),
            "messages": [{"role": "user", "content": prompt}]
        }
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=60
            )
            data = r.json()
            if "error" in data:
                print(f"خطأ من {model_name}: {data['error']}")
                continue
            if "content" in data:
                text = "".join(
                    item.get("text", "")
                    for item in data["content"]
                    if item.get("type") == "text"
                )
                return model_name, text.strip()
        except Exception as e:
            print(f"Exception مع {model_name}: {e}")
            continue
    return None, "تعذر التحليل"


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    body = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    resp = requests.post(url, json=body, timeout=30)
    if not resp.ok:
        print(f"Telegram Error: {resp.text}")


@app.get("/")
def home():
    return {
        "status": "running",
        "claude_key": "loaded" if API_KEY else "missing",
        "telegram_token": "loaded" if TELEGRAM_BOT_TOKEN else "missing",
        "telegram_chat": "loaded" if TELEGRAM_CHAT_ID else "missing",
        "signals_sent_today": len(sent_today),
    }


@app.post("/webhook")
def webhook(alert: TradingAlert):
    clean_symbol = alert.symbol.split(":")[-1]
    company_name = alert.company if alert.company else clean_symbol
    display_name = f"{clean_symbol} ({company_name})" if alert.company else clean_symbol

    if is_duplicate(clean_symbol, alert.signal.upper()):
        return {"status": "duplicate", "symbol": display_name}

    prompt = build_prompt(alert, display_name)
    model_used, analysis = ask_claude(prompt)

    now_str = datetime.now().strftime("%d/%m %H:%M")
    signal_emoji = "🟢" if "BUY" in alert.signal.upper() else "🔴"
    score = alert.buy_score if "BUY" in alert.signal.upper() else alert.sell_score
    score_bar = "🔥" if int(float(score)) >= 80 else "✅" if int(float(score)) >= 60 else "⚠️" if score else ""

    telegram_message = (
        f"{signal_emoji} <b>{display_name}</b>\n"
        f"💰 {alert.price}$  |  📡 {alert.signal}  |  ⏱ {alert.timeframe}\n"
        f"🎯 النقاط: {score}/100 {score_bar}\n"
        f"━━━━━━━━━━━━━━\n"
        f"{analysis}\n"
        f"━━━━━━━━━━━━━━\n"
        f"🕐 {now_str}"
    )

    send_telegram(telegram_message)

    return {
        "status": "ok",
        "symbol": display_name,
        "model_used": model_used,
        "score": score,
        "analysis": analysis,
    }
