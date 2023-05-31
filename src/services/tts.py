from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan
from datasets import load_dataset
import torch
import soundfile as sf
import sounddevice as sd
import os

class TTS:
    def __init__(self):
        self.processor = SpeechT5Processor.from_pretrained("microsoft/speecht5_tts")
        self.speech_model = SpeechT5ForTextToSpeech.from_pretrained("microsoft/speecht5_tts")
        self.vocoder = SpeechT5HifiGan.from_pretrained("microsoft/speecht5_hifigan")

        self.embeddings_dataset = load_dataset("Matthijs/cmu-arctic-xvectors", split="validation")
        self.speaker_embeddings = torch.tensor(self.embeddings_dataset[7306]["xvector"]).unsqueeze(0)

    def play_sound_file(self, file_path):
        data, sample_rate = sf.read(file_path)
        sd.play(data, sample_rate)
        sd.wait()

    def speak(self, text):
        inputs = self.processor(text=text, return_tensors="pt")
        speech = self.speech_model.generate_speech(inputs["input_ids"], self.speaker_embeddings, vocoder=self.vocoder)

        sf.write("speech.wav", speech.numpy(), samplerate=16000)

        self.play_sound_file("speech.wav")

        if os.path.isfile("speech.wav"):
            os.remove("speech.wav")

if __name__ == "__main__":
    print("Performing tests on TTS class")

    s = TTS()

    print("\nTesting speak() method\n")
    print("Speaking...")
    s.speak("Hello, world!")
    print('-'*50)

    print("\nTests complete")