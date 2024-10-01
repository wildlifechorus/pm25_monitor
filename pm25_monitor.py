import serial
import time
from Adafruit_IO import Client
from telegram import Bot
import schedule
from dotenv import load_dotenv
import os
import asyncio

# Load environment variables from the .env file
load_dotenv()

# Adafruit IO Credentials
aio_user = os.getenv('AIO_USER_NAME')
aio_key = os.getenv('AIO_KEY')
aio = Client(aio_user, aio_key)

# Telegram Bot Credentials
telegram_token = os.getenv('TELEGRAM_TOKEN')
channel_id = os.getenv('CHANNEL_ID')
bot = Bot(token=telegram_token)

# Initialize the serial port for SDS 011 sensor
ser = serial.Serial('/dev/ttyUSB0')

# Function to determine air quality level based on PM2.5 and PM10 values
def air_quality_level(pm_value, pm_type):
    if pm_type == 'pm25':
        if pm_value <= 12:
            return "Good 🟢"
        elif 12 < pm_value <= 35:
            return "Moderate 🟡"
        else:
            return "Unhealthy 🔴"
    elif pm_type == 'pm10':
        if pm_value <= 20:
            return "Good 🟢"
        elif 20 < pm_value <= 50:
            return "Moderate 🟡"
        else:
            return "Unhealthy 🔴"

def read_pm_values():
    """Read PM2.5 and PM10 values from the sensor."""
    data = []
    for index in range(0, 10):
        datum = ser.read()
        data.append(datum)

    # Extract PM2.5 and PM10 values from sensor data
    pmtwofive = int.from_bytes(b''.join(data[2:4]), byteorder='little') / 10
    pmten = int.from_bytes(b''.join(data[4:6]), byteorder='little') / 10

    # Send values to Adafruit IO
    aio.send('air-quality-pm-2-5', float(pmtwofive))  # Ensure values are floats
    aio.send('pm-ten', float(pmten))

    return pmtwofive, pmten

async def send_to_telegram(pmtwofive, pmten):
    """Send the PM2.5 and PM10 values to the Telegram channel with color-coded air quality status."""
    # Determine air quality levels for both PM2.5 and PM10
    pm25_status = air_quality_level(pmtwofive, 'pm25')
    pm10_status = air_quality_level(pmten, 'pm10')

    # Create message with emoji and PM values
    message = (f"🌍 **Air Quality Update** 🌍\n"
               f"PM2.5: {pmtwofive:.1f} µg/m³ - {pm25_status}\n"
               f"PM10: {pmten:.1f} µg/m³ - {pm10_status}")

    # Send message to Telegram
    await bot.send_message(chat_id=channel_id, text=message, parse_mode='Markdown')

def hourly_task():
    """Task that runs every hour to send PM2.5 and PM10 values to Telegram."""
    pmtwofive, pmten = read_pm_values()
    asyncio.run(send_to_telegram(pmtwofive, pmten))

# Schedule the task to run every hour
schedule.every().hour.do(hourly_task)

if __name__ == '__main__':
    while True:
        # Run scheduled tasks
        schedule.run_pending()

        # Read and send PM values every 10 seconds to Adafruit IO
        read_pm_values()
        time.sleep(10)
