import speech_recognition as sr

r = sr.Recognizer()
print("Starting Mic Test...")

try:
    with sr.Microphone() as source:
        print("Listening for 3 seconds... Say something!")
        r.adjust_for_ambient_noise(source, duration=1)
        audio = r.listen(source, timeout=5, phrase_time_limit=5)
        
    print("Processing...")
    text = r.recognize_google(audio)
    print(f"SUCCESS! I heard: {text}")

except Exception as e:
    print(f"FAILED! Error: {e}")