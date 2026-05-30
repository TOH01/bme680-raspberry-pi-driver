import json
import time
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

_DIR = Path(__file__).parent
LATEST = _DIR / "latest.json"

# Modern Dark Mode Palette
BG_COLOR = (18, 18, 20)
CARD_BG = (30, 30, 35)
TEXT_PRIMARY = (240, 240, 240)
TEXT_SECONDARY = (140, 140, 150)
ACCENT_GREEN = (46, 204, 113)
ACCENT_BLUE = (52, 152, 219)
ACCENT_ORANGE = (230, 126, 34)

# Load DejaVu Sans fonts statically from system paths
try:
    FONT_TITLE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
    FONT_LABEL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    FONT_VALUE = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
    FONT_IAQ = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    FONT_SMALL = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
except Exception:
    FONT_TITLE = FONT_LABEL = FONT_VALUE = FONT_IAQ = FONT_SMALL = ImageFont.load_default()

def read_data():
    try:
        with open(LATEST, "r") as f:
            return json.load(f)
    except Exception:
        return None

def draw_screen(data):
    w, h = 320, 240
    img = Image.new("RGB", (w, h), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Time
    now_str = datetime.now().strftime("%H:%M")
    
    # Minimal Header
    draw.text((15, 10), "Indoor Climate", fill=TEXT_SECONDARY, font=FONT_TITLE)
    draw.text((275, 10), now_str, fill=TEXT_SECONDARY, font=FONT_TITLE)

    # --- Top Row Cards ---
    # Temp Card
    draw.rounded_rectangle([10, 35, 155, 110], radius=8, fill=CARD_BG)
    draw.text((25, 45), "Temperature", fill=ACCENT_ORANGE, font=FONT_LABEL)
    temp = data.get("temperature", 0)
    draw.text((25, 70), f"{temp:.1f} °C", fill=TEXT_PRIMARY, font=FONT_VALUE)

    # Humidity Card
    draw.rounded_rectangle([165, 35, 310, 110], radius=8, fill=CARD_BG)
    draw.text((180, 45), "Humidity", fill=ACCENT_BLUE, font=FONT_LABEL)
    hum = data.get("humidity", 0)
    draw.text((180, 70), f"{hum:.1f} %", fill=TEXT_PRIMARY, font=FONT_VALUE)

    # --- Bottom Row Cards ---
    # CO2e Card
    draw.rounded_rectangle([10, 120, 155, 195], radius=8, fill=CARD_BG)
    draw.text((25, 130), "CO2e", fill=TEXT_SECONDARY, font=FONT_LABEL)
    co2 = data.get("co2_equivalent", 0)
    draw.text((25, 155), f"{int(co2)} ppm", fill=TEXT_PRIMARY, font=FONT_VALUE)

    # IAQ Card
    draw.rounded_rectangle([165, 120, 310, 195], radius=8, fill=CARD_BG)
    draw.text((180, 130), "IAQ Score", fill=TEXT_SECONDARY, font=FONT_LABEL)
    iaq = data.get("iaq", 0)

    if iaq <= 50:
        iaq_text = f"{int(iaq)} (Excellent)"
        iaq_color = ACCENT_GREEN
    elif iaq <= 100:
        iaq_text = f"{int(iaq)} (Good)"
        iaq_color = ACCENT_GREEN
    elif iaq <= 150:
        iaq_text = f"{int(iaq)} (Moderate)"
        iaq_color = ACCENT_ORANGE
    else:
        iaq_text = f"{int(iaq)} (Poor)"
        iaq_color = (226, 75, 74) # Red

    draw.text((180, 155), iaq_text, fill=iaq_color, font=FONT_IAQ)

    # --- Minimalist Footer ---
    pressure = data.get("pressure", 0)
    status_code = data.get("run_in_status", 0)
    status_str = "OK" if status_code != 0 else "Warm-up"
    
    draw.text((15, 210), f"Pressure: {pressure:.1f} hPa", fill=TEXT_SECONDARY, font=FONT_SMALL)
    draw.text((230, 210), f"Status: {status_str}", fill=TEXT_SECONDARY, font=FONT_SMALL)

    return img

def main():
    print("Starting display loop. Writing to /dev/fb1 every 1s...")
    while True:
        data = read_data()
        if data:
            img = draw_screen(data)
            buf = bytearray()
            # Convert RGB888 to RGB565 for framebuffer
            for r, g, b in img.getdata():
                buf += ((r & 0xF8) << 8 | (g & 0xFC) << 3 | (b >> 3)).to_bytes(2, "little")
            
            try:
                with open("/dev/fb1", "wb") as f:
                    f.write(buf)
            except OSError as e:
                print(f"Could not write to fb1: {e}")
        else:
            print("Warning: Could not read valid data from latest.json")
            
        time.sleep(1)

if __name__ == "__main__":
    main()
