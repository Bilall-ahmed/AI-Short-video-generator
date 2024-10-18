from flask import Flask, request, jsonify, render_template
from transformers import pipeline
import requests
from gtts import gTTS
import os
import uuid
import random
from bs4 import BeautifulSoup
from PIL import Image
from moviepy.editor import ImageSequenceClip, AudioFileClip, concatenate_videoclips 
import numpy as np

app = Flask(__name__, template_folder='templates')

# Initialize the text generation pipeline
generator = pipeline('text-generation', model='gpt2')

NEWS_API_KEY = '426805fabca6474c928b3a703fa6bbb1'  # Replace with your actual API key

@app.route('/')
def index():
    # Fetch news articles and select a random one
    news_articles = fetch_news()
    if news_articles:
        selected_article = random.choice(news_articles)
        return render_template('index.html', news_article=selected_article)
    else:
        return render_template('index.html', news_article=None)

def fetch_news():
    url = f'https://newsapi.org/v2/top-headlines?country=us&apiKey={NEWS_API_KEY}'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data['articles']  # Return all articles
    return []

@app.route('/generate-description', methods=['POST'])
def generate_detailed_description():
    input_sentence = request.json.get('input_sentence', '')
    if not input_sentence:
        return jsonify({"error": "Input sentence is required"}), 400

    try:
        response = generator(
            input_sentence,
            max_length=100,
            num_return_sequences=1,
            temperature=0.7,
            top_p=0.9,
            top_k=50
        )
        generated_text = response[0]['generated_text']
        return jsonify({"description": generated_text})
    except Exception as e:
        return jsonify({"error": f"Failed to generate description: {str(e)}"}), 500

@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    description = request.json.get('description', '')
    if not description:
        return jsonify({"error": "Description is required"}), 400

    try:
        tts = gTTS(text=description, lang='en')
        audio_file = f'static/audio/{uuid.uuid4()}.mp3'
        tts.save(audio_file)
        return jsonify({"audio_url": audio_file})
    except Exception as e:
        return jsonify({"error": f"Failed to generate audio: {str(e)}"}), 500


@app.route('/fetch-images', methods=['POST'])
def fetch_images():
    query = request.json.get('query', '')
    if not query:
        return jsonify({"error": "Query is required"}), 400

    try:
        images = download_images(query)
        return jsonify({"images": images})
    except Exception as e:
        return jsonify({"error": f"Failed to fetch images: {str(e)}"}), 500

def download_images(query, num_images=20):
    query = '+'.join(query.split())
    url = f"https://www.google.com/search?q={query}&source=lnms&tbm=isch"
    headers = {
        'User-Agent': "Mozilla/5.0"
    }
    soup = get_soup(url, headers)
    ActualImages = []
    for img_tag in soup.find_all("img"):
        img_url = img_tag.get("src")
        if img_url and img_url.startswith("http"):
            ActualImages.append(img_url)
        if len(ActualImages) >= num_images:
            break
    return ActualImages

def get_soup(url, headers):
    response = requests.get(url, headers=headers)
    return BeautifulSoup(response.text, 'html.parser')

@app.route('/create-collage', methods=['POST'])
def create_collage():
    images = request.json.get('images', [])
    if len(images) < 3:
        return jsonify({"error": "At least 3 images are required for collage creation."}), 400

    collage_images = []
    
    try:
        # Create collages in sets of three vertically
        for i in range(0, len(images), 3):
            collage_height = 300  # Total collage height
            collage_width = 100    # Width of individual images
            collage = Image.new('RGB', (collage_width, collage_height))  # Adjust size for vertical collage
            
            for j in range(3):
                if i + j < len(images):
                    img = Image.open(requests.get(images[i + j], stream=True).raw).resize((collage_width, 100))  # Resize images
                    collage.paste(img, (0, j * 100))  # Position images in vertical collage
            collage_path = f'static/collages/collage_{uuid.uuid4()}.png'
            collage.save(collage_path)
            collage_images.append(collage_path)

        return jsonify({"collageUrls": collage_images})
    except Exception as e:
        return jsonify({"error": f"Failed to create collages: {str(e)}"}), 500

@app.route('/generate-video', methods=['POST'])
def generate_video():
    collage_files = request.json.get('collages', [])
    audio_file = request.json.get('audio_file', '')

    if not collage_files:
        return jsonify({"error": "Collages are required to create a video."}), 400

    try:
        # Create video clip with each image displayed for at least 3 seconds
        clips = []
        for file in collage_files:
            # Create a clip for each collage image
            clip = ImageSequenceClip([file], fps=1)  # 1 frame per second
            clips.append(clip.set_duration(3))  # Each collage should be displayed for 3 seconds

        # Concatenate all clips into one final clip
        final_clip = concatenate_videoclips(clips, method="compose")

        # Initialize audio_clip
        audio_clip = None
        
        # If there's an audio file, load it and set it to the final video
        if audio_file and os.path.exists(audio_file):
            audio_clip = AudioFileClip(audio_file)
            # Set the audio to the video and match the duration
            final_clip = final_clip.set_audio(audio_clip.set_duration(final_clip.duration))
        else:
            print("Audio file does not exist or is empty")

        video_file = f'static/videos/video_{uuid.uuid4()}.mp4'
        final_clip.write_videofile(video_file, codec='libx264', fps=24)

        # Clean up to free memory (optional)
        final_clip.close()
        if audio_clip:
            audio_clip.close()

        return jsonify({"video_url": video_file})
    except Exception as e:
        return jsonify({"error": f"Failed to create video: {str(e)}"}), 500



if __name__ == '__main__':
    if not os.path.exists('static/audio'):
        os.makedirs('static/audio')
    if not os.path.exists('static/collages'):
        os.makedirs('static/collages')
    if not os.path.exists('static/videos'):
        os.makedirs('static/videos')
    app.run(host='0.0.0.0', port=5000)
