#!/usr/bin/env python3
"""
Philosopher Text-to-Speech Generator
Generates audio explanations of famous philosophers using AI TTS
"""

import os
import json
import base64
import requests
import wave
from pathlib import Path
from typing import Dict, Optional, List
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts_generation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TTSResult:
    """Data class for TTS generation results"""
    text: str
    transcript: str
    voice: str
    model: str
    output_file: str
    philosopher: str

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'
    
    @classmethod
    def colorize(cls, text: str, color: str) -> str:
        """Apply color to text"""
        return f"{color}{text}{cls.END}"

class AudioProcessor:
    """Handles audio file operations"""
    
    @staticmethod
    def save_pcm_as_wav(pcm_bytes: bytes, wav_path: str, 
                       channels: int = 1, sample_width: int = 2, 
                       frame_rate: int = 22050) -> None:
        """
        Save PCM16 audio bytes as WAV file
        
        Args:
            pcm_bytes: Raw PCM audio data
            wav_path: Output WAV file path
            channels: Number of audio channels (default: 1)
            sample_width: Sample width in bytes (default: 2)
            frame_rate: Sample rate in Hz (default: 22050)
        """
        try:
            with wave.open(wav_path, 'wb') as wav_file:
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(sample_width)
                wav_file.setframerate(frame_rate)
                wav_file.writeframes(pcm_bytes)
            logger.info(f"Audio saved successfully: {wav_path}")
        except Exception as e:
            logger.error(f"Failed to save audio file {wav_path}: {e}")
            raise

class TTSGenerator:
    """Handles text-to-speech generation via API"""
    
    def __init__(self, api_url: str = "https://text.pollinations.ai/openai"):
        self.api_url = api_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'PhilosopherTTS/1.0'
        })
    
    def generate_speech(self, text: str, voice: str = "nova", 
                       model: str = "openai-audio", 
                       output_file: str = "output.wav") -> Optional[TTSResult]:
        """
        Generate speech from text using TTS API
        
        Args:
            text: Text to convert to speech
            voice: Voice model to use
            model: TTS model name
            output_file: Output audio file path
            
        Returns:
            TTSResult object if successful, None otherwise
        """
        payload = {
            "model": model,
            "modalities": ["text", "audio"],
            "audio": {"voice": voice, "format": "pcm16"},
            "messages": [{"role": "user", "content": text}],
            "private": True
        }
        
        try:
            logger.info(f"Sending TTS request for {len(text)} characters")
            response = self.session.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract audio data
            audio_b64 = data["choices"][0]["message"]["audio"]["data"]
            audio_bytes = base64.b64decode(audio_b64)
            
            # Save audio file
            AudioProcessor.save_pcm_as_wav(audio_bytes, output_file)
            
            # Extract transcript
            transcript = data["choices"][0]["message"]["audio"].get(
                "transcript", "[Transcript unavailable]"
            )
            
            return TTSResult(
                text=text,
                transcript=transcript,
                voice=voice,
                model=model,
                output_file=output_file,
                philosopher=""  # Will be set by caller
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"Failed to process API response: {e}")
            if 'response' in locals():
                logger.error(f"Response content: {response.text[:500]}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in TTS generation: {e}")
            return None

class PhilosopherTTSManager:
    """Main class for managing philosopher TTS generation"""
    
    PHILOSOPHERS = [
        "Socrates", "Plato", "Aristotle", "Confucius", "Laozi", "Zhuangzi", 
        "Pythagoras", "Heraclitus", "Parmenides", "Thales", "Anaximander", 
        "Anaximenes", "Democritus", "Epicurus", "Diogenes", "Zeno of Elea",
        "Protagoras", "Gorgias", "Plotinus", "Marcus Aurelius", "Augustine of Hippo",
        "Boethius", "Anselm of Canterbury", "Avicenna", "Averroes", "Maimonides",
        "Al-Farabi", "Al-Ghazali", "Thomas Aquinas", "Duns Scotus", "William of Ockham",
        "Ramon Llull", "Bonaventure", "Meister Eckhart", "John of Salisbury",
        "Desiderius Erasmus", "Niccolò Machiavelli", "Francis Bacon", "René Descartes",
        "Thomas Hobbes", "Baruch Spinoza", "John Locke", "Blaise Pascal",
        "Gottfried Wilhelm Leibniz", "Giordano Bruno", "Michel de Montaigne",
        "Pierre Bayle", "Galileo Galilei", "Hugo Grotius", "Margaret Cavendish",
        "Voltaire", "Jean-Jacques Rousseau", "David Hume", "Immanuel Kant",
        "Denis Diderot", "Adam Smith", "Thomas Reid", "Mary Wollstonecraft",
        "Montesquieu", "Johann Gottlieb Fichte", "Georg Wilhelm Friedrich Hegel",
        "Arthur Schopenhauer", "Søren Kierkegaard", "Karl Marx", "John Stuart Mill",
        "Friedrich Nietzsche", "Auguste Comte", "William James", "Charles Sanders Peirce",
        "Ralph Waldo Emerson", "Bertrand Russell", "Ludwig Wittgenstein",
        "Martin Heidegger", "Jean-Paul Sartre", "Simone de Beauvoir", "Albert Camus",
        "Karl Popper", "Hannah Arendt", "Michel Foucault", "Jacques Derrida",
        "Jürgen Habermas", "Alfred North Whitehead", "Maurice Merleau-Ponty",
        "W.V.O. Quine", "John Rawls", "Noam Chomsky", "Judith Butler", "Slavoj Žižek",
        "Martha Nussbaum", "Cornel West", "Peter Singer", "Thomas Nagel",
        "Daniel Dennett", "Alvin Plantinga", "Amartya Sen", "Patricia Churchland",
        "Graham Harman", "Byung-Chul Han", "Quentin Meillassoux", "David Chalmers"
    ]
    
    def __init__(self, output_dir: str = "tts_audio"):
        self.output_dir = Path(output_dir)
        self.metadata_file = Path("philosophers_tts_metadata.jsonl")
        self.cache_file = Path("cache_audio_info.json")
        self.tts_generator = TTSGenerator()
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
        
        # Load cache
        self.cache = self._load_cache()
    
    def _load_cache(self) -> Dict[str, str]:
        """Load processing cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        return {}
    
    def _save_cache(self) -> None:
        """Save processing cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
    
    def _append_metadata(self, result: TTSResult) -> None:
        """Append result metadata to JSONL file"""
        try:
            with open(self.metadata_file, 'a', encoding='utf-8') as f:
                json_data = {
                    'philosopher': result.philosopher,
                    'text': result.text,
                    'transcript': result.transcript,
                    'voice': result.voice,
                    'model': result.model,
                    'output_file': result.output_file
                }
                f.write(json.dumps(json_data, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Failed to append metadata: {e}")
    
    def _create_prompt(self, philosopher_name: str) -> str:
        """Create TTS prompt for philosopher"""
        return f"Explain the life and philosophy of {philosopher_name} in 5000 words in a thoughtful, contemplative tone.Don't use list or heading"
    
    def _create_filename(self, index: int, philosopher_name: str) -> str:
        """Generate filename for audio output"""
        safe_name = philosopher_name.replace(' ', '_').replace('.', '')
        return str(self.output_dir / f"{index:03d}_{safe_name}.wav")
    
    def process_philosopher(self, index: int, philosopher_name: str) -> bool:
        """
        Process a single philosopher for TTS generation
        
        Args:
            index: Philosopher index number
            philosopher_name: Name of the philosopher
            
        Returns:
            True if successful, False otherwise
        """
        if philosopher_name in self.cache:
            print(Colors.colorize(
                f"⏩ {index:03d}. Skipping {philosopher_name} (already processed)", 
                Colors.YELLOW
            ))
            return True
        
        print(Colors.colorize(
            f"\n🎙️ {index:03d}. Processing {philosopher_name}...", 
            Colors.BOLD
        ))
        
        prompt = self._create_prompt(philosopher_name)
        output_file = self._create_filename(index, philosopher_name)
        
        result = self.tts_generator.generate_speech(
            text=prompt,
            voice="nova",
            output_file=output_file
        )
        
        if result:
            result.philosopher = philosopher_name
            self._append_metadata(result)
            self.cache[philosopher_name] = output_file
            self._save_cache()
            
            print(Colors.colorize(f"✅ Success: {output_file}", Colors.GREEN))
            return True
        else:
            print(Colors.colorize(f"❌ Failed: {philosopher_name}", Colors.RED))
            return False
    
    def process_all_philosophers(self) -> None:
        """Process all philosophers in the list"""
        total = len(self.PHILOSOPHERS)
        successful = 0
        failed = 0
        
        print(Colors.colorize(
            f"\n🚀 Starting TTS generation for {total} philosophers...\n", 
            Colors.HEADER
        ))
        
        for i, philosopher in enumerate(self.PHILOSOPHERS, 1):
            try:
                if self.process_philosopher(i, philosopher):
                    successful += 1
                else:
                    failed += 1
            except KeyboardInterrupt:
                print(Colors.colorize("\n⚡ Process interrupted by user", Colors.YELLOW))
                break
            except Exception as e:
                logger.error(f"Unexpected error processing {philosopher}: {e}")
                failed += 1
        
        # Print summary
        print(Colors.colorize(f"\n📊 Processing Complete!", Colors.HEADER))
        print(Colors.colorize(f"✅ Successful: {successful}", Colors.GREEN))
        print(Colors.colorize(f"❌ Failed: {failed}", Colors.RED))
        print(Colors.colorize(f"⏩ Skipped: {total - successful - failed}", Colors.YELLOW))

def main():
    """Main entry point"""
    try:
        manager = PhilosopherTTSManager()
        manager.process_all_philosophers()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
