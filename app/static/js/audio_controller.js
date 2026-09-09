/**
 * Audio Controller & Spectrum Analyzer
 * Manages WebAudio API, microphone recording, Kokoro WAV playback, and real-time frequency data.
 */

class AudioController {
    constructor() {
        this.audioCtx = null;
        this.analyser = null;
        this.mediaStream = null;
        this.sourceNode = null;
        this.dataArray = new Uint8Array(64);
        
        this.isRecording = false;
        this.isPlaying = false;
        this.currentAudioElement = null;
        this.isMuted = false;
        
        // Callbacks
        this.onFrequencyData = null;
        this.onSpeechResult = null;
        this.onRecordingStateChange = null;
        
        // Speech Recognition (Native Browser Fallback)
        this.initSpeechRecognition();
    }

    initAudioContext() {
        if (!this.audioCtx) {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this.audioCtx = new AudioContext();
            this.analyser = this.audioCtx.createAnalyser();
            this.analyser.fftSize = 128;
            this.analyser.smoothingTimeConstant = 0.8;
            this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
            this.startFrequencyLoop();
        }
        if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume();
        }
    }

    initSpeechRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = true;
            this.recognition.lang = 'en-US';

            this.recognition.onresult = (event) => {
                let interim = '';
                let final = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        final += event.results[i][0].transcript;
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }
                if (this.onSpeechResult) {
                    this.onSpeechResult({ final, interim });
                }
            };

            this.recognition.onerror = (err) => {
                console.warn('Speech recognition error:', err.error);
                this.stopListening();
            };

            this.recognition.onend = () => {
                if (this.isRecording) {
                    this.stopListening();
                }
            };
        }
    }

    async startListening() {
        this.initAudioContext();
        try {
            this.mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.sourceNode = this.audioCtx.createMediaStreamSource(this.mediaStream);
            this.sourceNode.connect(this.analyser);
            
            this.isRecording = true;
            if (this.recognition) {
                try { this.recognition.start(); } catch (e) {}
            }
            if (this.onRecordingStateChange) {
                this.onRecordingStateChange(true);
            }
            return true;
        } catch (err) {
            console.error('Microphone access error:', err);
            if (this.recognition) {
                try {
                    this.recognition.start();
                    this.isRecording = true;
                    if (this.onRecordingStateChange) this.onRecordingStateChange(true);
                    return true;
                } catch (e) {}
            }
            return false;
        }
    }

    stopListening() {
        if (!this.isRecording) return;
        this.isRecording = false;
        
        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(track => track.stop());
            this.mediaStream = null;
        }
        if (this.recognition) {
            try { this.recognition.stop(); } catch (e) {}
        }
        if (this.sourceNode) {
            try { this.sourceNode.disconnect(); } catch (e) {}
            this.sourceNode = null;
        }
        if (this.onRecordingStateChange) {
            this.onRecordingStateChange(false);
        }
    }

    toggleListening() {
        if (this.isRecording) {
            this.stopListening();
        } else {
            this.startListening();
        }
    }

    async playWavBase64(base64Audio, onEndedCallback) {
        if (this.isMuted || !base64Audio) {
            if (onEndedCallback) onEndedCallback();
            return;
        }

        this.initAudioContext();
        this.stopCurrentAudio();

        try {
            const byteCharacters = atob(base64Audio);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'audio/wav' });
            const audioUrl = URL.createObjectURL(blob);

            const audio = new Audio(audioUrl);
            this.currentAudioElement = audio;

            // Connect audio element to analyser
            const source = this.audioCtx.createMediaElementSource(audio);
            source.connect(this.analyser);
            this.analyser.connect(this.audioCtx.destination);

            this.isPlaying = true;

            audio.onended = () => {
                this.isPlaying = false;
                URL.revokeObjectURL(audioUrl);
                if (onEndedCallback) onEndedCallback();
            };

            audio.onerror = (e) => {
                console.warn('Audio playback error:', e);
                this.isPlaying = false;
                if (onEndedCallback) onEndedCallback();
            };

            await audio.play();
        } catch (e) {
            console.error('Play audio error:', e);
            this.isPlaying = false;
            if (onEndedCallback) onEndedCallback();
        }
    }

    stopCurrentAudio() {
        if (this.currentAudioElement) {
            try {
                this.currentAudioElement.pause();
                this.currentAudioElement.currentTime = 0;
            } catch (e) {}
            this.currentAudioElement = null;
        }
        this.isPlaying = false;
    }

    toggleMute() {
        this.isMuted = !this.isMuted;
        if (this.isMuted) {
            this.stopCurrentAudio();
        }
        return this.isMuted;
    }

    startFrequencyLoop() {
        const loop = () => {
            if (this.analyser && (this.isRecording || this.isPlaying)) {
                this.analyser.getByteFrequencyData(this.dataArray);
                if (this.onFrequencyData) {
                    this.onFrequencyData(this.dataArray);
                }
            } else if (this.onFrequencyData) {
                // Return zeroed or calm data when idle
                this.onFrequencyData(new Uint8Array(64));
            }
            requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    }
}

window.AudioController = AudioController;

