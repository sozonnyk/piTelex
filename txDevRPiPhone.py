import os
import threading
from pathlib import Path
import time
import pyaudio
import txBase
from pyaudio_silent import PyAudioSilent
from RPiIO import Button, pi_exit, Ringer

import logging

l = logging.getLogger("piTelex." + __name__)


class SongThread(threading.Thread):

    def __init__(self, pickup_palyback_file, *args, **kwargs):
        super(SongThread, self).__init__(*args, **kwargs)
        self._pickup_palyback_file = pickup_palyback_file
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def stopped(self):
        return self._stop_event.is_set()

    def run(self):
        self._play_song()

    def _play_song(self):
        # ffmpeg -i song.mp3 -acodec pcm_u8 -ar 22050 song.wav
        chunk_size = 1024
        sound_file = Path(__file__).parent / self._pickup_palyback_file
        if sound_file.is_file():
            with PyAudioSilent() as audio:
                output = audio.open(format=pyaudio.paUInt8,
                                    channels=1,
                                    rate=44100,
                                    output=True)
            with open(sound_file, 'rb') as fh:
                while fh.tell() != os.path.getsize(fh.name) and not self.stopped():
                    output.write(fh.read(chunk_size))
            audio.terminate()


class TelexRPiPhone(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()
        self.thread = None
        self.id = 'piPh'
        self.params = params
        self.start = time.time()

        self._pin_hangup = params.get('pin_hangup', 0)
        self._pickup_palyback_file = params.get('pickup_palyback_file')
        self._button_hangup = Button(self._pin_hangup, self._callback_button_hangup,
                                     release_callback=self._callback_button_hangup_release)

        self._pin_ring_a = params.get('pin_ring_a', 0)
        self._pin_ring_b = params.get('pin_ring_b', 0)
        self._ringer = Ringer(self._pin_ring_a, self._pin_ring_b)


    def exit(self):
        global pi

        if pi:
            del pi
            pi = None
            pi_exit()

    def idle20Hz(self):
        # startup chime
        if time.time() < self.start + 1:
            self._ringer.ring()

    def idle(self):
        pass

    def _callback_button_hangup(self, gpio, level, tick):
        if self.thread:
            self.thread.stop()
        self.thread = SongThread(self._pickup_palyback_file)
        self.thread.start()

    def _callback_button_hangup_release(self, gpio, level, tick):
        if self.thread:
            self.thread.stop()
