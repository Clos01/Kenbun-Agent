import os
import asyncio
import logging
from pathlib import Path
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
from google import genai
from google.genai import types

from tools.infrastructure.config import settings
from tools.infrastructure.orchestrator import orchestrate
from tools.utils.notifications import send_notification

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

from tools.utils.secret_manager import decrypt_value

# Load Config from Centralized Hub
TOKEN = decrypt_value(settings.telegram.bot_token.get_secret_value()) if settings.telegram.bot_token else None
GEMINI_KEY = decrypt_value(settings.GEMINI_API_KEY.get_secret_value()) if settings.GEMINI_API_KEY else None

async def transcribe_audio(file_path: str) -> str:
    """Uses Gemini 1.5 Pro to transcribe audio."""
    client = genai.Client(api_key=GEMINI_KEY)
    
    # Upload to Gemini (or pass bytes)
    # For speed and simplicity in prototype, we use the generate_content with bytes
    with open(file_path, "rb") as f:
        audio_data = f.read()

    response = client.models.generate_content(
        model="gemini-3-flash-preview", # Cutting-edge model available in this env
        contents=[
            "Transcribe the following voice note into a concise coding task or command for an AI assistant. "
            "If it sounds like a general request, convert it into an actionable objective.",
            types.Part.from_bytes(data=audio_data, mime_type="audio/ogg")
        ]
    )
    return response.text

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming voice notes."""
    user = update.message.from_user
    logging.info(f"🎤 Voice note received from {user.first_name}")
    
    # 1. Download the file
    voice_file = await context.bot.get_file(update.message.voice.file_id)
    temp_dir = Path(settings.PROJECT_ROOT) / "artifacts" / "voice_temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = temp_dir / f"voice_{update.message.message_id}.ogg"
    await voice_file.download_to_drive(file_path)
    
    # 2. Notify User
    send_notification("Sensory Layer", f"Processing voice note from {user.first_name}...")
    
    # 3. Transcribe
    try:
        transcription = await transcribe_audio(str(file_path))
        logging.info(f"📝 Transcription: {transcription}")
        
        # 4. Immediate Acknowledgement
        clean_transcription = transcription.replace("**", "").replace("#", "")
        await update.message.reply_text(f"🎙️ **Voice Received**\n\n**Objective:** {clean_transcription[:100]}...\n\n*Swarm is initiating. Please wait for the final report.*")
        
        # Audio feedback for the car
        os.system(f'say "Swarm initiated for: {clean_transcription[:50]}" &')
        
        # 5. Trigger Orchestrator
        send_notification("Swarm Triggered", f"Objective: {transcription[:100]}...")
        
        # Run orchestrate in a thread to not block the bot
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: orchestrate("research_implement", transcription))
        
        # 6. Final Report to User
        await update.message.reply_text(f"✅ **Task Completed**\n\n**Result Summary:**\n{str(result)[:1000]}...")
        
    except Exception as e:
        logging.error(f"❌ Error processing voice: {e}")
        await update.message.reply_text(f"❌ Failed to process voice: {e}")
    finally:
        # Cleanup
        if file_path.exists():
            file_path.unlink()

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes incoming text messages for debugging."""
    user = update.message.from_user
    text = update.message.text
    logging.info(f"💬 Text received from {user.first_name}: {text}")
    await update.message.reply_text(f"📡 I hear you, {user.first_name}! I received your message: '{text}'. Waiting for your next voice command.")

async def terminal_listener():
    """Listens for direct commands typed into the terminal."""
    loop = asyncio.get_event_loop()
    print("⌨️  Terminal Command Bridge is OPEN. Type a command and press Enter.")
    while True:
        try:
            # Use run_in_executor to not block the event loop while waiting for input
            command = await loop.run_in_executor(None, lambda: input(""))
            if command.strip():
                logging.info(f"⌨️ Terminal command received: {command}")
                
                # 1. Immediate Acknowledgement
                os.system(f'say "Terminal command received: {command[:30]}" &')
                
                # 2. Trigger Orchestrator
                try:
                    result = await loop.run_in_executor(None, lambda: orchestrate("research_implement", command))
                    print(f"✅ **Task Completed**\n\n**Result Summary:**\n{str(result)[:500]}...")
                except Exception as e:
                    logging.error(f"❌ Error processing terminal command: {e}")
                    print(f"❌ Error: {e}")
        except EOFError:
            break
        except Exception as e:
            logging.error(f"⚠️ Terminal listener error: {e}")
            await asyncio.sleep(1)

async def main():
    """Main entry point for System 6."""
    import sys
    import signal
    logging.info("📍 Starting Swarm Voice script...")
    
    # 1. Build Application
    logging.info("📍 Building Telegram Application...")
    application = ApplicationBuilder().token(TOKEN).build()

    # 2. Add Handlers
    logging.info("📍 Setting up handlers...")
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # 3. Start Polling & Terminal Listener
    logging.info("🚀 Kenbun Voice & Text Listener (System 6) is ONLINE.")
    
    # The 'async with' context manager automatically handles:
    # - application.initialize()
    # - application.start()
    # - application.stop()
    # - application.shutdown()
    async with application:
        await application.updater.start_polling()
        logging.info("📍 Polling started via updater.")

        stop_event = asyncio.Event()

        # Register OS signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop_event.set)
            except NotImplementedError:
                # Fallback for systems without full signal support (e.g. Windows)
                pass

        if sys.stdin.isatty():
            logging.info("📍 Interactive terminal detected. Starting terminal listener...")
            listener_task = asyncio.create_task(terminal_listener())
            
            # Wait for either the terminal to exit OR an OS signal
            done, pending = await asyncio.wait(
                [listener_task, stop_event.wait()],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Clean up dangling tasks to prevent resource leaks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        else:
            logging.info("📍 Non-interactive mode. Waiting for SIGTERM/SIGINT...")
            await stop_event.wait()

        logging.info("📍 Shutdown initiated. Stopping updater...")
        await application.updater.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
