from resemblyzer import VoiceEncoder, preprocess_wav
import numpy as np
from pathlib import Path
from numpy.linalg import norm
import os

encoder = VoiceEncoder()

def enroll_user(audio_path, username):
    wav = preprocess_wav(Path(audio_path))
    embedding = encoder.embed_utterance(wav)

    embeddings_dir = "utils/embeddings"
    os.makedirs(embeddings_dir, exist_ok=True)  # 🔥 ensures folder exists

    np.save(f"{embeddings_dir}/{username}.npy", embedding)
    return embedding

def cosine_similarity(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

def identify_user(audio_path, threshold=0.60):  # 👈 start with a lower threshold for testing
    try:
        print(f"🔍 Processing test audio: {audio_path}")
        wav = preprocess_wav(Path(audio_path))
        test_embedding = encoder.embed_utterance(wav)

        best_match = None
        best_score = -1
        embeddings_path = Path("utils/embeddings")

        print("📂 Searching through enrolled users in:", embeddings_path)

        for file in embeddings_path.glob("*.npy"):
            user_id = file.stem
            enrolled_embedding = np.load(file)

            score = cosine_similarity(test_embedding, enrolled_embedding)
            print(f"➡️ Compared with {user_id}: similarity = {score:.4f}")

            if score > best_score:
                best_score = score
                best_match = user_id

        print(f"🏁 Best match: {best_match}, Score: {best_score:.4f}, Threshold: {threshold}")

        if best_score >= threshold:
            print("✅ Voice recognized!")
            return best_match, best_score, True
        else:
            print("❌ Voice not recognized: below threshold")
            return None, best_score, False

    except Exception as e:
        print("🔥 Error in identify_user:", str(e))
        import traceback
        traceback.print_exc()
        return None, -1, False

"""def identify_user(audio_path, threshold=0.75):
    wav = preprocess_wav(Path(audio_path))
    test_embedding = encoder.embed_utterance(wav)

    best_match = None
    best_score = -1

    for file in Path("utils/embeddings").glob("*.npy"):
        user_id = file.stem
        enrolled_embedding = np.load(file)
        similarity = np.inner(test_embedding, enrolled_embedding)

        if similarity > best_score:
            best_score = similarity
            best_match = user_id

    if best_score >= threshold:
        return best_match, best_score, True
    else:
        return None, best_score, False"""