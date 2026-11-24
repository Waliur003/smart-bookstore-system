import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-only-change-this-secret')
    DATA_PATH = os.environ.get('DATA_PATH', str(ROOT / 'data' / 'store.json'))
    BIOMETRIC_PATH = os.environ.get('BIOMETRIC_PATH', str(ROOT / 'data' / 'biometrics'))
    DEMO_MODE = os.environ.get('DEMO_MODE', '0') == '1'
    OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://127.0.0.1:11434')
    OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'llama3.2:3b')
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('HTTPS', '0') == '1'
