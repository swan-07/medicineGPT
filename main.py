from flask import Flask, render_template, request, redirect, jsonify
import os
import time
import ast
import sqlite3

from langchain import ConversationChain
from langchain.memory.buffer import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from chatbots import Chatbots, parse_output
from compare_rsids import compare_gene_conditions
########################################################

# INITIALIZING APP, CHATBOTS AND MEMORY

if not os.path.exists('uploads'):
  os.makedirs('uploads')

app = Flask(__name__)

params = {'open_api_key': os.environ['api_key']}
chatbot = Chatbots(params)

if os.path.exists('static/audio.mp3'):
  os.remove('static/audio.mp3')

# The bug was fixed 45 mins ago

memory_loaded = False

# initial prompt
chatbot.conversation_chain.predict(
  input=
  f"In this conversation, you are the world's best dermatologist. Your personality is knowledgeable, vibrant, empathetic, communicative, observant, as well as communicative. Engage users in a friendly and conversational manner about their health and lifestyle (diet, exercise, sleep, stress management, etc). IMPORTANT: Keep messages as concise as possible. Make sure to cite the specific rsid (GIVE THE SPECIFIC ONE, for example Rs1042602) that leads you to different diagnoses."
)
reply = parse_output(
  chatbot.chat_bot_memory.load_memory_variables({})['history'])

username = " "

# connect with the front-end
@app.route("/username-endpoint", methods=["POST"])
def username_endpoint():
  input = request.get_json()
  username = input["username"]

  global memory_loaded
  if not memory_loaded:
    chatbot.database_file_name = username + "_records.txt"
    chatbot.reading_history(chatbot.database_file_name)
    chatbot.initialize_chains()
    chatbot.memory_loaded = True
    memory_loaded = True
    return redirect("/")
  else:
    return jsonify({"message": "username already loaded."})

@app.route("/", methods=["GET", "POST"])
def index():
  if request.method == "POST":
    user_input = request.form["user_input"]
    chat_response = chatbot.get_response(user_input)
    print(chat_response)
    response = chat_response['response']
    chatbot.text_to_avatar(response)
    emotion_image_url = chat_response["emotion_img_url"]
    print(response, emotion_image_url)

    # # TEXT TO SPEECH 
    # chatbot.text_to_speech(response)

    data = {
        "messages": chatbot.messages,
        "emotion_image": emotion_image_url,  # Update to use the new image URL
        "video": "static/talking_head.mp4",
        "summary": chatbot.current_summary
    }
    return render_template("index.html", data=data, response=response)
  else:
    default_messages = [{
        "role": "assistant",
        "content": "Hello! How can I assist you today?",
        "time": time.ctime(time.time()),
        "emotion_image": chatbot.emotion_avatars["neutral"]
    }]
    data = {
        "messages":
        chatbot.messages if len(chatbot.messages) > 0 else default_messages,
        "emotion_image":
        chatbot.messages[-1]["emotion_image"] if len(chatbot.messages) > 0 else
        default_messages[-1]["emotion_image"],
        "summary":
        chatbot.current_summary
    }
    return render_template("index.html", data=data)

# @app.route("/", methods=["GET", "POST"])
# def index():
#     if request.method == "POST":
#         user_input = request.form["user_input"]
#         chat_response = chatbot.get_response(user_input)
#         response = chat_response['response']
#         chatbot.text_to_avatar(response)
#         emotion_image_url = chat_response["emotion_img_url"]
#         video_path = "talking_head.mp4"

#         data = {
#             "messages": chatbot.messages,
#             "emotion_image": emotion_image_url,
#             "video": video_path,
#             "summary": chatbot.current_summary
#         }
#         return render_template("index.html", data=data)
#     else:
#         default_messages = [{
#             "role": "assistant",
#             "content": "Hello! How can I assist you today?",
#             "time": time.ctime(time.time()),
#             "emotion_image": chatbot.emotion_avatars["neutral"]
#         }]
#         data = {
#             "messages": chatbot.messages if len(chatbot.messages) > 0 else default_messages,
#             "emotion_image": chatbot.messages[-1]["emotion_image"] if len(chatbot.messages) > 0 else default_messages[-1]["emotion_image"],
#             "video": "talking_head.mp4",
#             "summary": chatbot.current_summary
#         }
#         return render_template("index.html", data=data)


@app.route('/user_image', methods=['POST'])
def user_image():
  if 'userImageFile' not in request.files:
    return 'No file part'

  file = request.files['userImageFile']

  if file.filename == '':
    return 'No selected file'
  else:
    print(type(file))
  file.save('uploads/' + username + "/" + file.filename)

  return 'File uploaded successfully'

@app.route('/user_video', methods=['POST'])
def user_video():
    if 'userVideoFile' not in request.files:
        return 'No file part'

    file = request.files['userVideoFile']

    if file.filename == '':
        return 'No selected file'

    # Save the video file
    file.save(f'uploads/{username}/{file.filename}')
    
    # Assuming you'll use this filename in the front-end to display the video
    return 'File uploaded successfully'


@app.route('/genomic_data', methods=['POST'])
def upload_genomic_data():
  if 'genomicFile' not in request.files:
    return 'No file part'

  file = request.files['genomicFile']

  if file.filename == '':
    return 'No selected file'
  else:
    print(type(file))

  # Here, you can save the file or process it as needed
  # For example, save it to a folder on the server
  
  file.save("uploads/" + file.filename)
  
  compare_gene_conditions('uploads/' + file.filename, 'gene_conditions.csv')
  print("gene_conditions.csv was successfully generated.")
  # BETA
  conditions_input = ""
  import pandas as pd
  res = pd.read_csv('gene_conditions.csv')
  print('BRUH')
  for index, row in res.iterrows():
    conditions_input += f'{row["ID"]} causes {row["Summary"]}. '
  # BETA
  # TODO: ADD THE STRING OF "[condition] due to [rsid]" string here
  print(conditions_input)
  chatbot.conversation_chain.predict(
    input=
    f"My conditions due to my genomic data are as follows: {conditions_input}"
  )

  return 'File uploaded and analyzed successfully'

# imagebot = Chatbot()
@app.route('/generate_image', methods=['POST'])
def generate_emotion_images():
    user_prompt = request.form['user_input']

  # Call the backend method to generate and store images for each emotion based on the user prompt
    images = chatbot.generate_all_emotion_images(user_prompt)
    return jsonify(images)
  
@app.route('/process_genomic_data', methods=['POST'])
def process_genomic_data():
    if 'genomicFile' not in request.files:
        return 'No file part'
    file = request.files['genomicFile']
    if file.filename == '':
        return 'No selected file'

    file_path = "uploads/" + file.filename
    file.save(file_path)

    conditions_results = compare_gene_conditions(file_path, 'gene_conditions.csv')
    conditions_input = ", ".join(conditions_results)

    chatbot.conversation_chain.predict(
        input=f"My conditions due to my genomic data are as follows: {conditions_input}"
    )

    return 'File uploaded and analyzed successfully'

if __name__ == "__main__":
  app.run("0.0.0.0")
