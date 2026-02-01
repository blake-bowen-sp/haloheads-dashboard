from flask import Flask, request, jsonify
from google.cloud import vision
import io
import logging

app = Flask(__name__)

@app.route("/")
def hello():
    return "Haloheads dashboard backend is alive.  Team Aaron rules 🎮"

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/ingest", methods=["POST"])
def ingest():
    if "image" not in request.files:
        return {"error": "no image uploaded"}, 400

    image_file = request.files["image"]
    image_bytes = image_file.read()

    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)

    response = client.text_detection(image=image)

    if response.error.message:
        return {"error": response.error.message}, 500

    texts = response.text_annotations

    raw_text = texts[0].description if texts else ""
    logging.info(raw_text)
    # For Day 2: just return it
    return jsonify({
        "raw_text": raw_text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
