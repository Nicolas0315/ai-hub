"""
KS30 Voice Synthesis Engine
Generates speech from KS30 verification results and self-generated questions.

3 voice profiles: male, female, neutral
Backends: macOS say (local), Gemini TTS (cloud), OpenAI TTS (cloud)

Design: Youta Hilono
Implementation: Shirokuma
"""

import subprocess
import os
import json
import urllib.request
import base64
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VoiceProfile:
    name: str
    gender: str  # "male", "female", "neutral"
    engine: str  # "macos", "gemini", "openai"
    voice_id: str  # engine-specific voice identifier
    language: str = "ja"
    pitch_shift: float = 0.0  # semitones
    speed: float = 1.0


# Default voice profiles
VOICE_PROFILES = {
    "male": VoiceProfile(
        name="KS30-M", gender="male", engine="macos",
        voice_id="Otoya", language="ja"
    ),
    "female": VoiceProfile(
        name="KS30-F", gender="female", engine="macos",
        voice_id="Kyoko (Enhanced)", language="ja"
    ),
    "neutral": VoiceProfile(
        name="KS30-N", gender="neutral", engine="macos",
        voice_id="Reed (日本語（日本）)", language="ja"
    ),
}


def _synthesize_macos(text, voice_id, output_path, speed=1.0):
    """Synthesize speech using macOS say command."""
    aiff_path = output_path + ".aiff"
    rate_arg = str(int(200 * speed))
    
    try:
        subprocess.run(
            ["say", "-v", voice_id, "-r", rate_arg, "-o", aiff_path, text],
            capture_output=True, timeout=30, check=True)
        
        # Convert to MP3
        subprocess.run(
            ["ffmpeg", "-y", "-i", aiff_path, "-b:a", "128k", output_path],
            capture_output=True, timeout=30, check=True)
        
        if os.path.exists(aiff_path):
            os.unlink(aiff_path)
        
        return os.path.exists(output_path)
    except Exception:
        if os.path.exists(aiff_path):
            os.unlink(aiff_path)
        return False


def _synthesize_gemini(text, output_path, api_key=None, voice="Kore"):
    """Synthesize speech using Gemini TTS API."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return False
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"Please read this text aloud: {text}"}]}],
        "generationConfig": {
            "response_modalities": ["AUDIO"],
            "speech_config": {
                "voice_config": {"prebuilt_voice_config": {"voice_name": voice}}
            }
        }
    }
    
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            audio_data = result["candidates"][0]["content"]["parts"][0].get("inline_data", {})
            if audio_data:
                audio_bytes = base64.b64decode(audio_data["data"])
                # Write raw audio, convert to mp3
                raw_path = output_path + ".raw"
                with open(raw_path, "wb") as f:
                    f.write(audio_bytes)
                mime = audio_data.get("mime_type", "audio/wav")
                subprocess.run(
                    ["ffmpeg", "-y", "-i", raw_path, "-b:a", "128k", output_path],
                    capture_output=True, timeout=30)
                os.unlink(raw_path)
                return os.path.exists(output_path)
    except Exception:
        pass
    return False


def synthesize(text, gender="neutral", output_path=None, engine=None, api_key=None):
    """Synthesize speech from text.
    
    Args:
        text: Text to speak
        gender: "male", "female", or "neutral"
        output_path: Output MP3 path (auto-generated if None)
        engine: Override engine ("macos", "gemini", "openai")
        api_key: API key for cloud engines
    
    Returns:
        Path to generated MP3, or None on failure
    """
    profile = VOICE_PROFILES.get(gender, VOICE_PROFILES["neutral"])
    
    if output_path is None:
        output_path = tempfile.mktemp(suffix=".mp3", prefix=f"ks30_{gender}_")
    
    engine = engine or profile.engine
    
    if engine == "macos":
        success = _synthesize_macos(text, profile.voice_id, output_path, profile.speed)
    elif engine == "gemini":
        voice_map = {"male": "Charon", "female": "Kore", "neutral": "Fenrir"}
        success = _synthesize_gemini(text, output_path, api_key, 
                                      voice=voice_map.get(gender, "Kore"))
    else:
        success = False
    
    return output_path if success else None


def synthesize_all(text, output_dir=None):
    """Generate all 3 voice variants.
    
    Returns dict of gender -> path.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="ks30_voices_")
    
    results = {}
    for gender in ["male", "female", "neutral"]:
        path = os.path.join(output_dir, f"ks30_{gender}.mp3")
        result = synthesize(text, gender=gender, output_path=path)
        if result:
            results[gender] = result
    
    return results


def speak_verification_result(pipeline_result, gender="neutral"):
    """Generate speech summary of a KS30 verification result."""
    r = pipeline_result
    llm = r.get("llm", "unknown")
    rate = r.get("pass_rate", 0)
    score = r.get("pipeline_score", 0)
    verdict = r.get("llm_verdict", {})
    
    text = f"KS30検証結果。{llm}パイプライン。"
    text += f"ソルバー通過率{rate*100:.0f}パーセント。スコア{score*100:.0f}点。"
    
    if verdict.get("is_real_api"):
        conf = verdict.get("confidence", 0)
        text += f"LLM信頼度{conf*100:.0f}パーセント。"
        reasoning = verdict.get("reasoning", "")
        if reasoning and len(reasoning) < 100:
            text += reasoning
    
    return synthesize(text, gender=gender)
