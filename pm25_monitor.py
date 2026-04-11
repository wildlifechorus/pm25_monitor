"""
pm25_monitor.py

Reads PM2.5 and PM10 values from a Nova SDS011 sensor connected via USB
serial, pushes them to Adafruit IO, and delivers Telegram notifications to a
channel every 30 minutes. Notifications are suppressed when both readings are
"Good". A /status command lets channel members request a fresh reading at any
time.

Dependencies (install via pip):
  pyserial adafruit-io "python-telegram-bot[job-queue]" python-dotenv

Environment variables (see .env.example):
  AIO_USER_NAME, AIO_KEY, TELEGRAM_TOKEN, CHANNEL_ID
"""

import asyncio
import logging
import os

import serial
from Adafruit_IO import Client
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

# Load environment variables from the .env file
load_dotenv()

# Configure module-level logger
logging.basicConfig(
  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
  level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Adafruit IO
# ---------------------------------------------------------------------------

aio_user = os.getenv('AIO_USER_NAME')
aio_key = os.getenv('AIO_KEY')
aio = Client(aio_user, aio_key)

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

telegram_token = os.getenv('TELEGRAM_TOKEN')
channel_id = os.getenv('CHANNEL_ID')

# ---------------------------------------------------------------------------
# Serial port – SDS011 sensor
# ---------------------------------------------------------------------------

ser = serial.Serial('/dev/ttyUSB0')

# ---------------------------------------------------------------------------
# In-memory cache so /status can report the most recent reading instantly
# ---------------------------------------------------------------------------

# Holds the last successfully read PM values; updated on every sensor read.
_last_reading: dict[str, float | None] = { 'pm25': None, 'pm10': None }

# Sentinel string used to detect a "Good" status and suppress notifications
_GOOD_STATUS = 'Good 🟢'

# ---------------------------------------------------------------------------
# Air quality helpers
# ---------------------------------------------------------------------------


def air_quality_level(pm_value: float, pm_type: str) -> str:
  """
  Return a human-readable, emoji-coded air quality label.

  PM2.5 thresholds (µg/m³):  ≤12 Good, ≤35 Moderate, >35 Unhealthy
  PM10  thresholds (µg/m³):  ≤20 Good, ≤50 Moderate, >50 Unhealthy
  """
  if pm_type == 'pm25':
    if pm_value <= 12:
      return 'Good 🟢'
    elif pm_value <= 35:
      return 'Moderate 🟡'
    else:
      return 'Unhealthy 🔴'
  elif pm_type == 'pm10':
    if pm_value <= 20:
      return 'Good 🟢'
    elif pm_value <= 50:
      return 'Moderate 🟡'
    else:
      return 'Unhealthy 🔴'

  raise ValueError(f'Unknown pm_type: {pm_type}')


def _build_message(pmtwofive: float, pmten: float) -> str:
  """
  Format the Telegram notification message using HTML parse mode.

  HTML is used instead of MarkdownV2 to avoid having to escape every
  special character (e.g. '.') that appears in dynamic float values.
  """
  pm25_status = air_quality_level(pmtwofive, 'pm25')
  pm10_status = air_quality_level(pmten, 'pm10')

  return (
    '🌍 <b>Air Quality Update</b> 🌍\n'
    f'PM2.5: {pmtwofive:.1f} µg/m³ — {pm25_status}\n'
    f'PM10:  {pmten:.1f} µg/m³ — {pm10_status}'
  )


# ---------------------------------------------------------------------------
# Sensor I/O
# ---------------------------------------------------------------------------


def _read_pm_values_sync() -> tuple[float, float]:
  """
  Blocking read from the SDS011 via serial and push to Adafruit IO.

  Returns a (pm25, pm10) tuple. Runs synchronously; call via
  asyncio.to_thread() to avoid blocking the event loop.
  """
  data = [ser.read() for _ in range(10)]

  # SDS011 protocol: bytes 2-3 = PM2.5, bytes 4-5 = PM10 (little-endian /10)
  pmtwofive = int.from_bytes(b''.join(data[2:4]), byteorder='little') / 10
  pmten = int.from_bytes(b''.join(data[4:6]), byteorder='little') / 10

  # Push to Adafruit IO feeds
  aio.send('air-quality-pm-2-5', float(pmtwofive))
  aio.send('pm-ten', float(pmten))

  # Update the in-memory cache for /status responses
  _last_reading['pm25'] = pmtwofive
  _last_reading['pm10'] = pmten

  return pmtwofive, pmten


async def read_pm_values() -> tuple[float, float]:
  """Async wrapper – runs the blocking serial read in a thread pool."""
  return await asyncio.to_thread(_read_pm_values_sync)


# ---------------------------------------------------------------------------
# Scheduled job (every 30 minutes)
# ---------------------------------------------------------------------------


async def periodic_update(context: ContextTypes.DEFAULT_TYPE) -> None:
  """
  PTB JobQueue callback: read sensor, then send to Telegram unless both
  PM2.5 and PM10 are Good.
  """
  try:
    pmtwofive, pmten = await read_pm_values()
  except Exception as exc:
    logger.error('Failed to read sensor data: %s', exc)
    return

  pm25_status = air_quality_level(pmtwofive, 'pm25')
  pm10_status = air_quality_level(pmten, 'pm10')

  # Suppress notification when the air quality is fully Good
  if pm25_status == _GOOD_STATUS and pm10_status == _GOOD_STATUS:
    logger.info(
      'Air quality is Good (PM2.5=%.1f, PM10=%.1f) — skipping notification.',
      pmtwofive,
      pmten,
    )
    return

  message = _build_message(pmtwofive, pmten)

  try:
    await context.bot.send_message(
      chat_id=channel_id,
      text=message,
      parse_mode='HTML',
    )
    logger.info('Notification sent (PM2.5=%.1f, PM10=%.1f).', pmtwofive, pmten)
  except Exception as exc:
    logger.error('Failed to send Telegram message: %s', exc)


# ---------------------------------------------------------------------------
# /status command handler
# ---------------------------------------------------------------------------


async def status_command(
  update: Update,
  context: ContextTypes.DEFAULT_TYPE,
) -> None:
  """
  Handle the /status command.

  Reads a fresh value from the sensor and replies with the current air
  quality status, regardless of whether it is Good or not.

  update.effective_message is PTB's built-in property that resolves to
  whichever of message / channel_post / edited_message is present, so
  this handler works in DMs, groups, and channels without extra branching.
  """
  # effective_message covers message, channel_post, and edited variants
  msg = update.effective_message
  if msg is None:
    return

  await msg.reply_text('⏳ Reading sensor, one moment…')

  try:
    pmtwofive, pmten = await read_pm_values()
  except Exception as exc:
    logger.error('/status sensor read failed: %s', exc)
    await msg.reply_text('❌ Could not read sensor data. Please try again.')
    return

  message = _build_message(pmtwofive, pmten)

  await msg.reply_text(message, parse_mode='HTML')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
  # Build the PTB Application (handles event loop + polling internally)
  app = Application.builder().token(telegram_token).build()

  # Register the /status command handler
  app.add_handler(CommandHandler('status', status_command))

  # Schedule periodic sensor reads every 30 minutes.
  # first=10 gives the app 10 seconds to start up before the first run.
  app.job_queue.run_repeating(
    periodic_update,
    interval=1800,  # 30 minutes in seconds
    first=10,
  )

  logger.info('Bot started. Periodic updates every 30 minutes.')
  # ALL_TYPES ensures channel_post updates are requested from Telegram.
  # Without this, PTB's auto-detection only requests 'message' updates,
  # so commands posted in a channel are never delivered to the bot.
  app.run_polling(allowed_updates=Update.ALL_TYPES)
