import os
from pydub import AudioSegment
import simpleaudio as sa
import random

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



