from kokoro import KPipeline
import sounddevice as sd

print("[⏳] Loading Kokoro... (It may take a minute to download the 82M model on the first run)")

# Initialize the pipeline for American English ('a')
pipeline = KPipeline(lang_code='a') 

text_to_speak = "System online. Hello Prajjwal, your voice module is working perfectly."

print(f"[🗣️] Speaking: {text_to_speak}")

# Generate the audio using the 'af_heart' voice
generator = pipeline(text_to_speak, voice='af_heart', speed=1.0)

# Play the audio through your speakers
for _, _, audio in generator:
    sd.play(audio, samplerate=24000)
    sd.wait() # Wait for the audio to finish playing
    
print("[✅] Test complete!")