import rtc # type: ignore
import alarm
import displayio
import terminalio
import time
import wifi
from adafruit_magtag.magtag import MagTag
from adafruit_display_text import label
from adafruit_display_shapes import roundrect

magtag = MagTag()
border_thickness = 6

TWELVE_HOUR = False
YEAR = 2025

# Graphics
display_width = magtag.graphics.display.width
display_height = magtag.graphics.display.height
magtag.graphics.set_background(0x000000)
magtag.graphics.auto_refresh = True

time_group = displayio.Group()

# Outline
background_rect = roundrect.RoundRect(
    0,
    0,
    display_width,
    display_height,
    10,
    fill=None,
    outline=0xFFFFFF,
    stroke=border_thickness,
)
time_group.append(background_rect)

# Time Background
time_background_rect = roundrect.RoundRect(
    3 * border_thickness,
    display_height // 2 - border_thickness,
    display_width - 6 * border_thickness,
    display_height // 2 - border_thickness,
    10,
    fill=0xFFFFFF,
    outline=None,
    stroke=None,
)
time_group.append(time_background_rect)

# Date Display
date_display = label.Label(terminalio.FONT, text="Starting...")
date_display.anchor_point = (0.5, 0.0)
date_display.anchored_position = (display_width // 2, 2 * border_thickness)
date_display.scale = 3
date_display.background_color = None

# Time Display
time_display = label.Label(terminalio.FONT, text="XX:XX")
time_display.anchor_point = (0.5, 1.0)
time_display.anchored_position = (
    display_width // 2,
    display_height - 2 * border_thickness,
)
time_display.scale = 5
time_display.color = 0x000000
time_display.background_color = None

time_group.append(date_display)
time_group.append(time_display)

magtag.display.show(time_group)


def logger(msg):
    now = rtc.RTC().datetime
    year = now.tm_year
    mon = f"{now.tm_mon:02d}"
    day = f"{now.tm_mday:02d}"
    hh = f"{now.tm_hour:02d}"
    mm = f"{now.tm_min:02d}"
    ss = f"{now.tm_sec:02d}"
    print(f"{year}-{mon}-{day} {hh}:{mm}:{ss} | {msg}")


# Modified from https://learn.adafruit.com/magtag-cat-feeder-clock/getting-the-date-time
def make_time_text(time_struct):
    """Given a time.struct_time, return a string as H:MM or HH:MM, either
    12- or 24-hour style depending on TWELVE_HOUR flag.
    """
    if TWELVE_HOUR:
        postfix = ""
        if time_struct.tm_hour > 12:
            hour_string = str(time_struct.tm_hour - 12)  # 13-23 -> 1-11 (pm)
            postfix = " PM"
        elif time_struct.tm_hour > 0:
            hour_string = str(time_struct.tm_hour)  # 1-12
            postfix = " AM"
            if time_struct.tm_hour == 12:
                postfix = " PM"  # 12 -> 12 (pm)
        else:
            hour_string = "12"  # 0 -> 12 (am)
            postfix = " AM"
        time_string = hour_string + ":{mm:02d}".format(mm=time_struct.tm_min) + postfix
    else:
        time_string = "{hh:02d}:{mm:02d}".format(hh=time_struct.tm_hour, mm=time_struct.tm_min)
    time_display.text = time_string


def make_date_text(time_struct):
    days_of_week = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")
    months = (
        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC",
    )

    dow = days_of_week[time_struct.tm_wday]
    month = months[time_struct.tm_mon - 1]
    day = time_struct.tm_mday
    year = time_struct.tm_year

    date_string = f"{dow} {month} {day} {year}"

    date_display.text = date_string

def update_clock():
    now = rtc.RTC().datetime
    if now.tm_year >= YEAR:
        logger("Updating Clock")
        make_time_text(now)
        make_date_text(now)
        safe_refresh()
        alarm.sleep_memory[0] = now.tm_hour % 256
        logger(f"Sleep Memory: {alarm.sleep_memory[0]}")
    else:
        logger("skipping update due to bad data")

    time_to_sleep = 60 - now.tm_sec
    logger(f"Sleeping for {time_to_sleep}s")
    magtag.exit_and_deep_sleep(time_to_sleep)

def update_from_network(delay=1):
    logger(f"Updating from network. Delay: {delay}")
    try:
        magtag.network.get_local_time()
        now = rtc.RTC().datetime
        logger(f"Local time retrieved")
        if now.tm_year < YEAR:
            logger("Incorrect time, retrying")
            logger(f"{wifi.radio.connected} | {wifi.radio.ipv4_address}")
            time_display.text = f"{2**delay}"
            date_display.text = f"Retry: {delay}"
            safe_refresh()
            time_to_sleep = 2**delay
            magtag.enter_light_sleep(time_to_sleep)
            update_from_network(delay + 1)
    except Exception as e:
        logger(f"Error refreshing time: {e}")
        if wifi.radio.connected:
            date_display.text = f"{wifi.radio.ipv4_address}"
        else:
            date_display.text = "Disconnected"
        time_display.text = f"{magtag.peripherals.battery:.02f}"
        safe_refresh()
    logger("Continuing with clock update after refresh")
    update_clock()


def push_batt_update():
    batt = magtag.peripherals.battery
    logger(f"Updating IO feed with battery status: {batt}")
    magtag.network.push_to_io("magtag-battery", batt)


def safe_refresh():
    while magtag.display.time_to_refresh > 0 or magtag.display.busy:
        pass
    magtag.display.refresh()


def get_local_time(location=None, max_attempts=10):
    """
    Fetch and "set" the local time of this microcontroller to the local time at the location,
    using an internet time API.

    :param str location: Your city and country, e.g. ``"America/New_York"``.
    :param max_attempts: The maximum number of attempts to connect to WiFi before
                         failing or use None to disable. Defaults to 10.

    """
    TIME_SERVICE_FORMAT = "%Y-%m-%d %H:%M:%S.%L %j %u %z %Z"
    reply = magtag.network.get_strftime(TIME_SERVICE_FORMAT, location=location)
    if reply:
        times = reply.split(" ")
        the_date = times[0]
        the_time = times[1]
        year_day = int(times[2])
        week_day = int(times[3])
        is_dst = None  # no way to know yet
        year, month, mday = (int(x) for x in the_date.split("-"))
        the_time = the_time.split(".")[0]
        hours, minutes, seconds = (int(x) for x in the_time.split(":"))
        now = time.struct_time(
            (year, month, mday, hours, minutes, seconds, week_day, year_day, is_dst)
        )

        if rtc is not None:
            rtc.RTC().datetime = now
        else:
            logger("RTC doesn't appear to be initialized")

    return reply

now = rtc.RTC().datetime
if not alarm.wake_alarm:
    logger("Fresh Start")
    alarm.sleep_memory[0] = 99
    try:
        time_display.text = "Syncing"
        magtag.display.refresh()
        update_from_network()
    except (ValueError, RuntimeError, ConnectionError, OSError) as e:
        time_display.text = "Error"
        safe_refresh()
        logger(f"Error during initial refresh: {e}")
        update_clock()
elif alarm.sleep_memory[0] != now.tm_hour or now.tm_min % 20 == 0:
    logger("Time to refresh")
    try:
        update_from_network()
    except (ValueError, RuntimeError, ConnectionError, OSError) as e:
        logger(f"Error during intermittent refresh: {e}")
        update_clock()
else:
    logger("Looks like we can update without refresh")
    update_clock()
