from flask import Flask, request, redirect, render_template_string, jsonify
import os
from werkzeug.utils import secure_filename
import whisper
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/'

# Set up logging
logging.basicConfig(level=logging.INFO)

HTML_FORM = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Upload Audio File</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            font-family: "Gill Sans", sans-serif;
            background-image: url('static/images/background.jpg');
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center;
            border-radius: 50px;
        }
        .upload-container {
            text-align: center;
            background: rgba(130, 192, 248, 0.9);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 40px rgba(0, 0, 0, 0.2);
            border: 4px solid #add8e6;
            font-family: "Gill Sans", sans-serif;
        }
        h1 {
            margin-bottom: 20px;
            font-size: 2em;
            color: #333;
            font-family: "Fantasy", sans-serif;
            
        }
        h2 {
            margin-bottom: 20px;
            font-size: 1.5em;
            color: #333;
            
        }
        input[type="file"] {
            margin-bottom: 20px;
            font-size: 1em;
            padding: 10px;
            background-color: #ffffff;
            border: 1px solid #add8e6;
            border-radius: 20px;
            cursor: pointer;
        }
        input[type="file"]:hover{
            background-color: #a2e386;
        }
        input[type="text"] {
            margin-bottom: 20px;
            font-size: 1em;
            padding: 10px;
            width: calc(100% - 24px);
            border: 2px solid #add8e6;
            border-radius: 20px;
        }
        input[type="submit"],
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 20px;
            cursor: pointer;
            font-size: 1em;
            margin: 5px;
        }
        input[type="submit"]:hover,
        button:hover {
            background-color: #a2e386;
        }
        .file-input-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="upload-container">
        <h1>UPLOAD AUDIO</h1>
        <form method="POST" action="/upload" enctype="multipart/form-data">
            <div class="file-input-container">
                <input type="file" name="file" accept=".mp3, .wav, .ogg">
            </div>
            <input type="text" name="language" placeholder="Enter language (example: en)">
            <input type="submit" value="Upload ">
        </form>
        <h1>Or RECORD AUDIO</h1>
        <button id="startRecordButton">Start Recording</button>
        <button id="stopRecordButton" disabled>Stop Recording</button>
        <button id="uploadRecordButton" disabled>Upload Recording</button>
        <audio id="audioPlayback" controls></audio>
    </div>
    <script>
        let mediaRecorder;
        let audioChunks = [];
        let audioBlob;

        document.getElementById('startRecordButton').onclick = function() {
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    mediaRecorder = new MediaRecorder(stream);
                    mediaRecorder.start();
                    mediaRecorder.ondataavailable = event => {
                        audioChunks.push(event.data);
                    };
                    mediaRecorder.onstop = () => {
                        audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                        const audioUrl = URL.createObjectURL(audioBlob);
                        document.getElementById('audioPlayback').src = audioUrl;
                        document.getElementById('uploadRecordButton').disabled = false;
                    };
                    document.getElementById('startRecordButton').disabled = true;
                    document.getElementById('stopRecordButton').disabled = false;
                });
        };

        document.getElementById('stopRecordButton').onclick = function() {
            mediaRecorder.stop();
            document.getElementById('stopRecordButton').disabled = true;
            document.getElementById('startRecordButton').disabled = false;
        };

        document.getElementById('uploadRecordButton').onclick = function() {
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.wav');
            formData.append('language', 'en'); // You can dynamically set the language if needed
            console.log("Uploading recorded audio...");
            fetch('/upload', {
                method: 'POST',
                body: formData
            }).then(response => response.json())
              .then(data => {
                  console.log("Upload successful:", data);
                  window.location.href = '/result?transcription=' + encodeURIComponent(data.transcription);
              }).catch(error => {
                  console.error("Error uploading file:", error);
              });
        };
    </script>
</body>
</html>
"""

HTML_OUT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Transcription Result</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            font-family: "Gill Sans", sans-serif;
            background-image: url('static/images/background1.jpg');
            background-size: cover;
            background-repeat: no-repeat;
            background-position: center;
        }
        .transcription-container {
            text-align: center;
            background: rgba(130, 192, 248, 0.9);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.2);
            border: 2px solid #add8e6;
        }
        h1 {
            margin-bottom: 20px;
            font-size: 2em;
            color: #333;
            font-family: "Gill Sans", sans-serif;
        }
        p {
            font-size: 1.2em;
            color: #333;
        }
    </style>
</head>
<body>
    <div class="transcription-container">
        <h1>Generated Text</h1>
        <p>{{ transcription }}</p>
    </div>
</body>
</html>
"""

@app.route('/')
def upload_form():
    return render_template_string(HTML_FORM)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    file = request.files['file']
    language = request.form.get('language', 'en')  # Default to 'en' if no language provided
    if file.filename == '':
        return redirect(request.url)
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        logging.info(f'File saved to {filepath}')
        
        try:
            model = whisper.load_model("base")
            result = model.transcribe(filepath, language=language)
            transcription = result["text"]
            logging.info(f'Transcription result: {transcription}')
        except Exception as e:
            logging.error(f'Error during transcription: {e}')
            return jsonify({"error": str(e)}), 500
        
        return jsonify({"transcription": transcription})

@app.route('/result')
def show_result():
    transcription = request.args.get('transcription', '')
    return render_template_string(HTML_OUT, transcription=transcription)

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(host="0.0.0.0", port=5003, debug=True)







# {
#     "version":2,
#     "builds":[
#         {"src":"app.py","use":"@vercel/python"}
#     ],
#     "routes":[
#         {"src":"/(.*)","dest":"app.py"}
#     ]
# }