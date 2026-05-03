import os
import uuid
import subprocess
from models.cache import CacheService
from models.yield_predictor import YieldPredictor
from models.weather import WeatherService
from models.market  import MarketService
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from models.soil_analyzer    import SoilAnalyzer
from models.disease_detector import DiseaseDetector
from database.db import init_db, save_soil_reading
from models.market_analyzer import MarketAnalyzer
from models.product_recommender import ProductRecommender
from models.report_generator import ReportGenerator
from gtts import gTTS
from deep_translator import GoogleTranslator
import time as time_module

cache_service       = CacheService()
weather_service     = WeatherService(cache=cache_service)
market_service      = MarketService(cache=cache_service)
yield_predictor     = YieldPredictor()
market_analyzer     = MarketAnalyzer()
product_recommender = ProductRecommender()
report_generator = ReportGenerator()


app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

# ── Load models once at startup ───────────────────────────
print("Loading models...")
soil_analyzer    = SoilAnalyzer()
disease_detector = DiseaseDetector("models/disease_model/disease_classifier.keras")
init_db()
print("All models ready!")

# ── Routes ────────────────────────────────────────────────
@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "models": ["soil", "disease"]})

@app.route("/api/analyze/soil", methods=["POST"])
def analyze_soil():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file     = request.files["image"]
    farm_id  = request.form.get("farm_id", "farm_001")
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    path     = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        result = soil_analyzer.analyze(path)
        save_soil_reading(
            farm_id,
            result["moisture_percent"],
            result["category"],
            path
        )
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/analyze/disease", methods=["POST"])
def analyze_disease():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded"}), 400

    file     = request.files["image"]
    farm_id  = request.form.get("farm_id", "farm_001")
    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
    path     = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    try:
        result = disease_detector.predict(path)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/history/soil/<farm_id>")
def soil_history(farm_id):
    from database.db import get_soil_history
    return jsonify(get_soil_history(farm_id))

@app.route("/api/debug/soil", methods=["POST"])
def debug_soil():
    if "image" not in request.files:
        return jsonify({"error": "No image"}), 400
    
    file     = request.files["image"]
    filename = secure_filename(f"debug_{file.filename}")
    path     = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    
    # Raw prediction without any fusion
    import tensorflow as tf
    import numpy as np
    
    img = tf.keras.utils.load_img(path, target_size=(224, 224))
    arr = tf.keras.utils.img_to_array(img)
    arr = tf.keras.applications.efficientnet.preprocess_input(arr)
    arr = np.expand_dims(arr, axis=0)
    
    preds = soil_analyzer.model.predict(arr, verbose=0)[0]
    names = ["Alluvial soil", "Black Soil", "Clay soil", "Red soil"]
    
    result = {
        "model_path": "models/soil_model/soil_classifier_v3.keras",
        "predictions": {
            name: round(float(score) * 100, 2)
            for name, score in zip(names, preds)
        },
        "predicted": names[int(np.argmax(preds))],
        "confidence": round(float(max(preds)) * 100, 2)
    }
    return jsonify(result)

@app.route("/api/weather")
def get_weather():
    lat   = request.args.get("lat",  12.9716)  # Default: Bangalore
    lon   = request.args.get("lon",  77.5946)
    state = request.args.get("state","Karnataka")
    return jsonify(weather_service.get_forecast(float(lat), float(lon)))

@app.route("/api/market/multiple", methods=["POST"])
def get_multiple_markets():
    data  = request.json
    crops = data.get("crops", ["tomato", "rice", "wheat"])
    state = data.get("state", "Karnataka")
    return jsonify(market_service.get_multiple_prices(crops, state))

@app.route("/api/smart-recommendation", methods=["POST"])
def smart_recommendation():
    """Combines soil + weather for irrigation decision"""
    data         = request.json
    soil_result  = data.get("soil_result", {})
    lat          = data.get("lat",  12.9716)
    lon          = data.get("lon",  77.5946)

    weather      = weather_service.get_forecast(lat, lon)
    moisture_pct = soil_result.get("moisture_percent", 50)
    soil_type    = soil_result.get("soil_type", "Unknown")

    # Smart decision combining soil + weather
    rain_coming  = weather.get("summary", {}).get("total_rain_7days", 0) > 10

    if rain_coming and moisture_pct > 40:
        action = "Skip watering — rain expected and soil has adequate moisture."
    elif moisture_pct < 30 and not rain_coming:
        action = "Water immediately — soil is dry and no rain expected."
    elif moisture_pct < 50 and not rain_coming:
        action = "Water this evening for 20 minutes. No rain in forecast."
    else:
        action = "Monitor soil daily. Conditions are stable."

    return jsonify({
        "soil":          soil_result,
        "weather":       weather,
        "smart_action":  action,
        "rain_expected": rain_coming,
    })

@app.route("/api/yield", methods=["POST"])
def predict_yield():
    data          = request.json
    crop          = data.get("crop", "tomato")
    area          = float(data.get("area_acres", 1))
    planting_date = data.get("planting_date", "")
    state         = data.get("state", "karnataka")
    result        = yield_predictor.predict(crop, area, planting_date, state)
    return jsonify(result)

@app.route("/api/market/analytics/generate")
def generate_market_charts():
    try:
        # Export price data to CSV
        csv_path = market_analyzer.export_price_history()

        # Run R script to generate charts
        result = subprocess.run(
            ["Rscript", "analytics/market_analytics.R",
             csv_path, "static/charts"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0:
            return jsonify({"error": result.stderr}), 500

        return jsonify({
            "success": True,
            "charts": [
                "charts/price_trend.png",
                "charts/price_volatility.png",
                "charts/profit_comparison.png",
                "charts/weekly_avg.png",
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/market/<crop>")
def get_market(crop):
    state = request.args.get("state", "Karnataka")
    return jsonify(market_service.get_price(crop, state))

@app.route("/api/market/best-sell/<crop>")
def best_sell(crop):
    return jsonify(market_analyzer.get_best_sell_advice(crop))

@app.route("/api/market/suggest/<path:soil_type>/<float:area>")
def suggest_crop(soil_type, area):
    soil_type = soil_type.replace("%20", " ")
    results = market_analyzer.get_best_crop_suggestion(soil_type, area)
    return jsonify(results)

@app.route("/api/products/<path:disease>")
def get_products(disease):
    return jsonify(product_recommender.get_products_json(disease))

@app.route("/api/water", methods=["POST"])
def water_requirement():
    from models.yield_predictor import calculate_water_requirement
    data     = request.json
    crop     = data.get("crop", "tomato")
    area     = float(data.get("area_acres", 1))
    moisture = data.get("soil_moisture", "adequate")
    result   = calculate_water_requirement(crop, area, moisture)
    return jsonify(result)

@app.route("/api/cache/stats")
def cache_stats():
    return jsonify(cache_service.get_stats())

@app.route("/api/cache/clear")
def cache_clear():
    cache_service.redis.flushdb()
    return jsonify({"success": True, "message": "Cache cleared!"})

@app.route("/api/report/soil", methods=["GET", "POST", "OPTIONS"])
def generate_soil_report():
    if request.method == "OPTIONS":
        return jsonify({}), 200 # Handles strict browser security checks
        
    data       = request.json
    soil_data  = data.get("soil_data", {})
    water_data = data.get("water_data", None)
    farm_id    = data.get("farm_id", "farm_001")
    try:
        filename = report_generator.generate_soil_report(
            soil_data, water_data, farm_id
        )
        return jsonify({
            "success":  True,
            # NEW: Remove 'static' from the URL path
            "download": "/" + filename.replace("\\", "/").replace("static/", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/report/disease", methods=["GET", "POST", "OPTIONS"])
def generate_disease_report():
    if request.method == "OPTIONS":
        return jsonify({}), 200 # Handles strict browser security checks
        
    data         = request.json
    disease_data = data.get("disease_data", {})
    products     = data.get("products", [])
    farm_id      = data.get("farm_id", "farm_001")
    try:
        filename = report_generator.generate_disease_report(
            disease_data, products, farm_id
        )
        return jsonify({
            "success":  True,
            # NEW: Remove 'static' from the URL path
            "download": "/" + filename.replace("\\", "/").replace("static/", "")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    data = request.json
    text = data.get("text", "")
    lang = data.get("lang", "en-IN")

    if not text:
        return jsonify({"error": "No text provided"}), 400

    lang_map = {
        "en-IN": "en",
        "hi-IN": "hi",
        "kn-IN": "kn",
        "ta-IN": "ta",
        "te-IN": "te"
    }

    tts_lang = lang_map.get(lang, "en")

    try:
        tts_folder = os.path.join("static", "tts")
        os.makedirs(tts_folder, exist_ok=True)

        # Clean old files
        now = time_module.time()
        for old_file in os.listdir(tts_folder):
            old_path = os.path.join(tts_folder, old_file)
            try:
                if now - os.path.getmtime(old_path) > 300:
                    os.remove(old_path)
            except:
                pass

        # Translate if not English
        final_text = text
        if tts_lang != "en":
            try:
                final_text = GoogleTranslator(
                    source="en", target=tts_lang
                ).translate(text)
                print(f"🌐 Translated to {tts_lang}: {final_text[:80]}...")
            except Exception as te:
                print(f"⚠️ Translation failed, using English: {te}")
                final_text = text

        # Generate speech
        filename = f"tts_{uuid.uuid4().hex[:8]}.mp3"
        filepath = os.path.join(tts_folder, filename)

        tts = gTTS(text=final_text, lang=tts_lang, slow=False)
        tts.save(filepath)

        print(f"🔊 TTS: {tts_lang} → {filename}")

        return jsonify({
            "success": True,
            "audio_url": f"/tts/{filename}"
        })

    except Exception as e:
        print(f"❌ TTS Error: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/sw.js")
def service_worker():
    return app.send_static_file("sw.js")

@app.route("/manifest.json")
def manifest():
    return app.send_static_file("manifest.json")

@app.route("/offline.html")
def offline():
    return app.send_static_file("offline.html")    
    
if __name__ == "__main__":
    app.run(debug=True, port=5000)