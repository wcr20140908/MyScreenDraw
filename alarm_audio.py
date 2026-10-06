# SPDX-License-Identifier: GPL-3.0-or-later
"""Timer audio with per-app amplitude; never change the system mixer."""
import io
import math
import sys
import threading
import wave
from array import array
from functools import lru_cache


@lru_cache(maxsize=16)
def alarm_wave(volume=100):
    volume = max(0, min(100, int(volume)))
    rate = 22050
    samples = array("h")
    for _ in range(4):
        for frequency, duration in ((1319, .16), (1568, .16), (2093, .32)):
            count = round(rate * duration)
            fade = round(rate * .004)
            for i in range(count):
                envelope = min(1.0, i / fade, (count - 1 - i) / fade)
                samples.append(round(28000 * volume / 100 * envelope * math.sin(2 * math.pi * frequency * i / rate)))
        samples.extend([0] * round(rate * .15))
    if sys.byteorder != "little":
        samples.byteswap()
    result = io.BytesIO()
    with wave.open(result, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(samples.tobytes())
    return result.getvalue()


def play_alarm_async(volume=100):
    volume = max(0, min(100, int(volume)))
    if volume == 0:
        return None
    def play():
        try:
            import winsound
            # SND_MEMORY cannot be combined with SND_ASYNC: use our own thread.
            winsound.PlaySound(alarm_wave(volume), winsound.SND_MEMORY | winsound.SND_NODEFAULT)
        except (ImportError, RuntimeError):
            pass
    thread = threading.Thread(target=play, name="msd-timer-alarm", daemon=True)
    thread.start()
    return thread
