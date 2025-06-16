import os
from pydub import AudioSegment
import simpleaudio as sa
import random
from gtts import gTTS
from io import BytesIO
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class SpeakAgent:
    def __init__(self, subject):
        if subject == 'move':
            dir_path = os.path.join('audio', 'move')
        elif subject == 'sleep':
            dir_path = os.path.join('audio', 'sleep')
        elif subject == 'fall':
            dir_path = os.path.join('audio', 'fall')
        else:
            dir_path = None

        if dir_path is not None:
            choices = os.listdir(dir_path)
            choice = random.choice(choices)
            file_path = os.path.join(dir_path, choice)
            audio = AudioSegment.from_mp3(file_path)
            play_obj = sa.play_buffer(audio.raw_data, num_channels=audio.channels,
                                      bytes_per_sample=audio.sample_width, sample_rate=audio.frame_rate)
            play_obj.wait_done()
        else:
            self.speak_from_memory(subject)

    def speak_from_memory(self, text: str, lang='en', tld='ca'):
        text = text.replace('~', '')
        tts = gTTS(text=text, lang=lang, tld=tld)
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        # Redare cu mpg123 direct din stdin
        process = subprocess.Popen(['mpg123', '-'], stdin=subprocess.PIPE)
        process.communicate(mp3_fp.read())

