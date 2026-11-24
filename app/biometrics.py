"""Optional prototype biometric adapters. Not suitable for production identity verification.

Requires optional packages from requirements-biometric.txt and enrolled media files.
Face: data/biometrics/<account_id>.jpg. Voice: data/biometrics/<account_id>.wav.
Never store submitted live sample; only in-memory processing. Enrolled media are
sensitive and excluded by .gitignore. Voice webm conversion requires ffmpeg.
"""
import io
import os
import subprocess
import tempfile
from pathlib import Path
from flask import current_app

class BiometricUnavailable(Exception): pass

def recognize(kind, live_bytes, accounts):
    directory=Path(current_app.config['BIOMETRIC_PATH'])
    if kind=='face':
        try: import face_recognition
        except ImportError: raise BiometricUnavailable('Install optional face-recognition dependencies.')
        try:
            live=face_recognition.load_image_file(io.BytesIO(live_bytes))
            embeddings=face_recognition.face_encodings(live)
            if len(embeddings)!=1: return None
            best=None; best_distance=0.47
            import numpy as np
            for account in accounts:
                f=directory/(account['id']+'.jpg')
                if not f.is_file():continue
                known=face_recognition.face_encodings(face_recognition.load_image_file(str(f)))
                if len(known)!=1:continue
                d=float(face_recognition.face_distance(known,embeddings[0])[0])
                if d<best_distance:best,best_distance=account['id'],d
            return best
        except (ValueError,TypeError): return None
    if kind=='voice':
        try:
            from resemblyzer import VoiceEncoder, preprocess_wav
            import numpy as np
        except ImportError:raise BiometricUnavailable('Install optional voice biometric dependencies.')
        # Browsers send webm; ffmpeg converts to PCM wav in memory only.
        conversion=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i','pipe:0',
                                   '-f','wav','-ac','1','-ar','16000','pipe:1'],input=live_bytes,
                                  capture_output=True,timeout=15,check=False)
        if conversion.returncode!=0: return None
        with tempfile.NamedTemporaryFile(suffix='.wav') as wav:
            wav.write(conversion.stdout);wav.flush()
            encoder=VoiceEncoder(device='cpu')
            live_vector=encoder.embed_utterance(preprocess_wav(wav.name))
        best=None; similarity=0.78  # Demo threshold; must be calibrated before real use.
        for account in accounts:
            f=directory/(account['id']+'.wav')
            if not f.is_file():continue
            known_vector=encoder.embed_utterance(preprocess_wav(str(f)))
            score=float(np.dot(live_vector,known_vector)/(np.linalg.norm(live_vector)*np.linalg.norm(known_vector)))
            if score>similarity:best,similarity=account['id'],score
        return best
    raise BiometricUnavailable('Unsupported biometric type.')
