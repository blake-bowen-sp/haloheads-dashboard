from flask import Flask, request, jsonify
from google.cloud import firestore
import io
import logging
from PIL import Image  # For optional downscaling

app = Flask(__name__)

def get_db():
    return firestore.Client()

def process_image_ocr(image_bytes):
    """
    Lazy-imports Vision client inside this function to avoid startup memory spikes.
    Optionally downscales image to reduce memory usage.
    """
    from google.cloud import vision  # Import inside function
    
    # Optional: downscale large images to ~1024x1024
    pil_image = Image.open(io.BytesIO(image_bytes))
    max_size = (1024, 1024)
    pil_image.thumbnail(max_size)
    
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG")
    downsized_bytes = buffer.getvalue()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=downsized_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(response.error.message)

    texts = response.text_annotations
    return texts[0].description if texts else ""

@app.route("/")
def hello():
    return "Haloheads dashboard backend is alive. Team Aaron rules 🎮"

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/ingest", methods=["POST"])
def ingest():
    if "image" not in request.files:
        return {"error": "no image uploaded"}, 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    try:
        raw_text = process_image_ocr(image_bytes)
    except Exception as e:
        logging.exception("OCR failed")
        return {"error": str(e)}, 500

    # Lazy Firestore usage example (uncomment when ready)
    # db = get_db()
    # db.collection("games").add({"ocr_text": raw_text})

    return jsonify({"raw_text": raw_text})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
