<p align="center">
  <img src="https://github.com/user-attachments/assets/f6449bcc-4c10-4d97-9ecb-404aa252bd0b" alt="photo">
</p>

# PM2.5 Monitor with SDS 011 and Telegram Alerts

This project uses a **Raspberry Pi 3 Model B** and an **SDS 011** sensor to monitor air quality by measuring both **PM2.5** and **PM10** values. The sensor provides real-time data on air pollution, and the system logs this data to **Adafruit IO**. Additionally, PM2.5 and PM10 values are sent hourly to a **Telegram Channel** with color-coded air quality indicators to notify users about current air quality levels.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Hardware Requirements](#hardware-requirements)
3. [Software Setup](#software-setup)
4. [Installation](#installation)
5. [Usage](#usage)
6. [Telegram Integration](#telegram-integration)
7. [Adafruit IO Integration](#adafruit-io-integration)
8. [Supervisor Setup](#supervisor-setup)
9. [License](#license)

---

## Introduction

The **SDS 011 Sensor** is a reliable air quality sensor developed by Nova Fitness, capable of detecting particulate matter (PM) with a diameter of less than 2.5 micrometers (PM2.5). This project gathers air quality data using the sensor and a **Raspberry Pi 3 Model B**. The data is:

- Logged to **Adafruit IO** for tracking air quality over time.
- Sent to a **Telegram Channel** every hour, providing timely updates on air quality conditions.

PM2.5 is a widely accepted indicator of air quality, and this project follows guidelines set by the **World Health Organization (WHO)**, which recommends a PM2.5 value not exceeding 10 μg/m³ annually or 25 μg/m³ over 24 hours.

---

## Hardware Requirements

- **Raspberry Pi 3 Model B**
- **SDS 011 Air Quality Sensor**
- USB to Serial converter (for connecting the SDS 011 to the Raspberry Pi)
- MicroSD card (8GB+)
- Power supply for Raspberry Pi
- Internet connection (Ethernet or Wi-Fi)

---

## Software Setup

You will need the following software installed on your Raspberry Pi:

1. **Raspbian OS (or Raspberry Pi OS)**
2. **Python 3** (with `pip` installed)
3. **Adafruit IO Python Client**
4. **python-telegram-bot** library
5. **Supervisor** for running the script as a background service

To install the necessary Python libraries:

```bash
sudo apt update
sudo apt install python3-pip
python3 -m venv venv
source venv/bin/activate
pip3 install setuptools pyserial adafruit-io python-telegram-bot schedule python-dotenv
```

---

## Installation

1. **Clone the Repository:**

   Clone the repository to your Raspberry Pi:

   ```bash
   git clone https://github.com/wildlifechorus/pm25_monitor.git
   cd pm25_monitor
   ```

2. **Configure the `.env` File:**

   Create a `.env` file in the root directory and add the following:

   ```env
   AIO_USER_NAME=your_adafruit_username
   AIO_KEY=your_adafruit_key
   TELEGRAM_TOKEN=your_telegram_bot_token
   CHANNEL_ID=@your_telegram_channel_id
   ```

   Make sure to replace placeholders with your own credentials.

3. **Test the Script:**

   Run the script to make sure it works:

   ```bash
   python3 pm25_monitor.py
   ```

4. **Supervisor Setup:**

   Configure **Supervisor** to run the script automatically. See [Supervisor Setup](#supervisor-setup) for details.

---

## Usage

Once the script is running, it will:

1. Collect **PM2.5** and **PM10** data from the **SDS 011** sensor every 10 seconds.
2. Send the PM2.5 and PM10 data to **Adafruit IO** for real-time logging.
3. Send a message with both **PM2.5** and **PM10** values to your **Telegram Channel** every hour, along with color-coded air quality status (🟢 Good, 🟡 Moderate, 🔴 Unhealthy).

---

## Telegram Integration

To send PM2.5 data to a Telegram channel:

1. **Create a Telegram bot** using [BotFather](https://t.me/botfather).
2. Add the bot to your channel as an admin.
3. Obtain the bot token and channel ID, and add them to your `.env` file.

---

## Adafruit IO Integration

You will need to create an account on [Adafruit IO](https://io.adafruit.com/) and set up feeds for logging PM2.5 values.

- **Feed 1**: For PM2.5 values (`air-quality-pm-2-5`)
- **Feed 2**: For PM10 values (`pm-ten`)

Add your Adafruit IO credentials in the `.env` file:

```env
AIO_USER_NAME=your_adafruit_username
AIO_KEY=your_adafruit_key
```

---

## Supervisor Setup

We use **Supervisor** to manage the script as a background process, ensuring that it starts automatically and restarts on failure.

1. Install Supervisor:

   ```bash
   sudo apt install supervisor
   ```

2. Create a configuration file for the script:

   ```bash
   sudo nano /etc/supervisor/conf.d/pm25_monitor.conf
   ```

   Add the following content:

   ```ini
   [program:pm25_monitor]
   command=/home/pi/pm25_monitor/venv/bin/python3 /home/pi/pm25_monitor/pm25_monitor.py
   directory=/home/pi/pm25_monitor
   autostart=true
   autorestart=true
   startsecs=10
   stdout_logfile=/var/log/pm25_monitor.log
   stderr_logfile=/var/log/pm25_monitor_err.log
   user=pi
   ```

3. Update and start Supervisor:

   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start pm25_monitor
   ```

Your script will now run in the background and restart automatically if it crashes.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
