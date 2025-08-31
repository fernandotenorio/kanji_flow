from gtts import gTTS
import os
import time
import json

def load_json(file):
    with open(file, encoding='utf-8') as f:
        d = json.load(f)
        return d
    return None

def generate_audio_files(word_list, output_dir=".", delay=3):
    def gen_word_sound(word):
        try:
            tts = gTTS(text=word, lang='ja')
            filename = f"{output_dir}/{word}.mp3"
            tts.save(filename)
            print(f"Generated word: {word}")
        except Exception as e:
            print(f"Error generating word: {word}: {e}")
        finally:
            time.sleep(delay)

    for d in word_list:
        word1 = d["word_1"]
        word2 = d["word_2"]
        gen_word_sound(word1)
        gen_word_sound(word2)
            

if __name__ == '__main__':
    data = load_json('hiragana2.json')
    generate_audio_files(data, 'hiragana-sounds')