import os
import threading
import pyaudio
import txBase
import wave
from pyaudio_silent import PyAudioSilent
from RPiIO import Button, pi_exit

import logging

l = logging.getLogger("piTelex." + __name__)


class SongThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super(SongThread, self).__init__(*args, **kwargs)
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
        with PyAudioSilent() as audio:
            output = audio.open(format=pyaudio.paUInt8,
                                channels=1,
                                rate=44100,
                                output=True)
            with open('song.wav', 'rb') as fh:
                while fh.tell() != os.path.getsize(
                        fh.name) and not self.stopped():  # get the file-size from the os module
                    output.write(fh.read(chunk_size))


class TelexRPiPhone(txBase.TelexBase):
    def __init__(self, **params):
        super().__init__()

        self.thread = None
        self.id = 'piPh'
        self.params = params

        self._pin_hangup = params.get('pin_hangup', 0)
        print(self._pin_hangup)
        self._button_hangup = Button(self._pin_hangup, self._callback_button_hangup,
                                     release_callback=self._callback_button_hangup_release)

    def exit(self):
        global pi

        if pi:
            del pi
            pi = None
            pi_exit()

    def idle20Hz(self):
        pass

    def idle(self):
        pass

    def _callback_button_hangup(self, gpio, level, tick):
        if self.thread:
            self.thread.stop()
        self.thread = SongThread()
        self.thread.start()

    def _callback_button_hangup_release(self, gpio, level, tick):
        if self.thread:
            self.thread.stop()
