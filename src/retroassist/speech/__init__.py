"""Speech I/O: STT, TTS, PTT/open-mic modes, and voice dialogue."""

from retroassist.speech.dialogue import VoiceDialogue, VoiceTurnResult, format_spoken_reply
from retroassist.speech.intents import Intent, IntentResult, parse_intent
from retroassist.speech.modes import MicSource, MockMicSource, SpeechModeController, pcm_rms_energy
from retroassist.speech.stt import MockSpeechToText, WhisperSpeechToText, create_stt
from retroassist.speech.tts import MockTextToSpeech, PiperTextToSpeech, create_tts

__all__ = [
    "Intent",
    "IntentResult",
    "MicSource",
    "MockMicSource",
    "MockSpeechToText",
    "MockTextToSpeech",
    "PiperTextToSpeech",
    "SpeechModeController",
    "VoiceDialogue",
    "VoiceTurnResult",
    "WhisperSpeechToText",
    "create_stt",
    "create_tts",
    "format_spoken_reply",
    "parse_intent",
    "pcm_rms_energy",
]
