import os
import sys
import time
import asyncio
import logging
from pathlib import Path

# Import centralized settings
from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import swarm
from tools.audit.supervisor_agent import run_supervisor_audit

# Native macOS Imports
try:
    import Speech
    import AVFoundation
    from Foundation import NSRunLoop, NSDate, NSObject
    from AppKit import NSSpeechSynthesizer
except ImportError as e:
    print(f"❌ Native macOS libraries missing: {e}")
    sys.exit(1)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/tmp/kenbun_native.log"), logging.StreamHandler()]
)

class SpeechDelegate(NSObject):
    """
    Delegate to track when the system is speaking to prevent acoustic feedback.
    """
    def initWithParent_(self, parent):
        self = super().init()
        if self:
            self.parent = parent
        return self

    def speechSynthesizer_didFinishSpeaking_(self, synth, finished):
        self.parent.is_speaking = False
        self.parent.lockout_until = time.time() + 0.8
        logging.info("🔊 System finished speaking.")

class NativeKenbunEars:
    def __init__(self):
        # Speech Recognition
        self.recognizer = Speech.SFSpeechRecognizer.alloc().initWithLocale_(Speech.NSLocale.alloc().initWithLocaleIdentifier_("en-US"))
        self.audio_engine = AVFoundation.AVAudioEngine.alloc().init()
        self.recognition_request = None
        self.recognition_task = None
        
        # Speech Synthesis (The Mouth)
        self.synthesizer = NSSpeechSynthesizer.alloc().init()
        self.delegate = SpeechDelegate.alloc().initWithParent_(self)
        self.synthesizer.setDelegate_(self.delegate)
        
        # State Management
        self.is_speaking = False
        self.lockout_until = 0
        self.last_transcript = ""
        self.last_update_time = time.time()
        self.silence_threshold = 1.2
        self.wake_word_active = False
        
        # Interaction State
        self.current_state = "IDLE" # IDLE, AWAITING_CONFIRMATION, EXECUTING
        self.pending_objective = None
        self.loop = None
        
        # Telemetry
        self.ears_state_path = settings.BRAIN_HEALTH_DIR / "ears_state.json"
        self.write_state("IDLE", "")

    def start_listening(self):
        def auth_handler(status):
            if status == 3: logging.info("✅ Speech Recognition Authorized.")
        Speech.SFSpeechRecognizer.requestAuthorization_(auth_handler)

        if not self.recognizer.isAvailable():
            logging.error("❌ Speech Recognizer not available.")
            return

        self.recognition_request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        self.recognition_request.setShouldReportPartialResults_(True)

        input_node = self.audio_engine.inputNode()
        recording_format = input_node.outputFormatForBus_(0)
        input_node.installTapOnBus_bufferSize_format_block_(0, 1024, recording_format, self.handle_audio)
        
        self.audio_engine.prepare()
        self.audio_engine.startAndReturnError_(None)

        self.recognition_task = self.recognizer.recognitionTaskWithRequest_resultHandler_(self.recognition_request, self.handle_result)
        logging.info("👂 System 6: Native Ears are ONLINE.")
        self.say("Sensory layer online.")
        self.write_state("LISTENING", "Sensory layer online")

    def write_state(self, status: str, transcript: str):
        """Updates ears_state.json for the dashboard."""
        try:
            state = {
                "timestamp": time.time(),
                "status": status,
                "transcript": transcript,
                "is_speaking": self.is_speaking
            }
            with open(self.ears_state_path, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logging.error(f"Failed to write ears state: {e}")

    def handle_audio(self, buffer, when):
        if self.recognition_request:
            self.recognition_request.appendAudioPCMBuffer_(buffer)

    def handle_result(self, result, error):
        if error or self.is_speaking or time.time() < self.lockout_until: 
            return
        
        if result:
            transcript = result.bestTranscription().formattedString().lower()
            if transcript != self.last_transcript:
                self.last_transcript = transcript
                self.last_update_time = time.time()
                sys.stdout.write(f"\r🎤 Hearing: {transcript[-50:]} ...")
                sys.stdout.flush()
                self.write_state("HEARING", transcript)

                if self.current_state == "IDLE":
                    if any(wake in transcript for wake in ["kenbun", "anti gravity", "anti-gravity"]):
                        if not self.wake_word_active:
                            self.wake_word_active = True
                            self.play_sound("Submarine")

    async def check_silence_loop(self):
        """Async loop to check for silence and process commands."""
        while True:
            if self.last_transcript and (time.time() - self.last_update_time > self.silence_threshold):
                if not self.is_speaking:
                    logging.info(f"\n📍 Processing: '{self.last_transcript}'")
                    
                    if self.current_state == "IDLE" and self.wake_word_active:
                        await self.process_initial_command(self.last_transcript)
                    elif self.current_state == "AWAITING_CONFIRMATION":
                        await self.process_confirmation(self.last_transcript)
                    
                    self.reset_recognition()
            
            await asyncio.sleep(0.5)

    async def process_initial_command(self, transcript):
        objective = self.extract_command(transcript)
        if not objective or len(objective) < 3: 
            return

        self.pending_objective = objective
        self.say(f"I heard {objective}. Let me check with the supervisor.")
        
        # --- SYSTEM 2 ENSEMBLE AUDIT (Integrated) ---
        audit_result = await run_supervisor_audit(f"Intent: {objective}")
        
        if audit_result.get("decision") == "REJECTED":
            self.say(f"I'm sorry, the supervisor rejected that command. Reason: {audit_result.get('reason')}")
            self.current_state = "IDLE"
            self.pending_objective = None
        else:
            self.current_state = "AWAITING_CONFIRMATION"
            self.say("Supervisor has approved the intent. Should I initiate the swarm?")

    async def process_confirmation(self, transcript):
        text = transcript.strip().lower()
        if any(confirm in text for confirm in ["yes", "proceed", "do it", "sure", "ok"]):
            self.say("Swarm initiating.")
            # Run swarm in background thread so ears stay alive
            asyncio.create_task(self.execute_swarm_task(self.pending_objective))
        else:
            self.say("Cancelled. Standing by.")
            self.current_state = "IDLE"
        
        self.pending_objective = None

    async def execute_swarm_task(self, command):
        self.current_state = "EXECUTING"
        try:
            # Swarm is a long-running async task
            # Since orchestrator uses asyncio.run internally, we wrap it
            import asyncio
            report = await asyncio.to_thread(swarm, command)
            self.say("Swarm task completed. Report is on your dashboard.")
        except Exception as e:
            self.say(f"Swarm error: {str(e)[:40]}")
        finally:
            self.current_state = "IDLE"

    def extract_command(self, transcript):
        for wake in ["kenbun", "anti gravity", "anti-gravity"]:
            if wake in transcript:
                parts = transcript.split(wake)
                if len(parts) >= 2:
                    return parts[-1].strip()
        return None

    def reset_recognition(self):
        self.wake_word_active = False
        self.last_transcript = ""
        if self.recognition_task: 
            self.recognition_task.cancel()
        self.recognition_request = Speech.SFSpeechAudioBufferRecognitionRequest.alloc().init()
        self.recognition_request.setShouldReportPartialResults_(True)
        self.recognition_task = self.recognizer.recognitionTaskWithRequest_resultHandler_(self.recognition_request, self.handle_result)

    def play_sound(self, sound_name):
        os.system(f'afplay /System/Library/Sounds/{sound_name}.aiff &')

    def say(self, text):
        self.is_speaking = True
        self.synthesizer.startSpeakingString_(text)

    async def run_daemon(self):
        """Master Async Loop."""
        self.start_listening()
        asyncio.create_task(self.check_silence_loop())
        
        while True:
            # Pump the native macOS event loop
            NSRunLoop.currentRunLoop().runMode_beforeDate_("NSDefaultRunLoopMode", NSDate.dateWithTimeIntervalSinceNow_(0.02))
            await asyncio.sleep(0.02)

if __name__ == "__main__":
    ears = NativeKenbunEars()
    asyncio.run(ears.run_daemon())
