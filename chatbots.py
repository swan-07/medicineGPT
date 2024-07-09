from flask import Flask, render_template, request, redirect, jsonify
import os
import time
import ast
import base64
import openai

from langchain.chains import ConversationChain
from langchain.memory.buffer import ConversationBufferMemory
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from langchain.schema import AIMessage, HumanMessage
from PIL import Image

# HELPER METHODS


def parse_output(memory):
  '''
  Given the memory of a conversation chain, return the last line spoken by the AI.
  '''
  lines = memory.split('AI: ')
  last_line = lines[-1]
  return last_line

def valid_emotion(input_emotion, emotion_avatars):
  '''
  Given an emotion, return the emotion if it's one of keys in the emotion_avatars dictionary - otherwise, return 'neutral'.
  '''
  emotions = list(emotion_avatars.keys())
  if input_emotion not in emotions:
    return "neutral"
  else:
    return input_emotion

class Chatbots(object):
  
  def __init__(self, params):
    # the actual bots
    self.chat_bot = ChatOpenAI(openai_api_key=params['open_api_key'], model_name = "gpt-4")
    self.summary_bot = ChatOpenAI(openai_api_key=params['open_api_key'], model_name = "gpt-4")
    self.utility_bot = ChatOpenAI(openai_api_key=params['open_api_key'], model_name = "gpt-4")

    # initializing the memories of the bots
    self.chat_bot_memory = ConversationBufferMemory()
    self.summary_bot_memory = ConversationSummaryMemory(llm=self.summary_bot)
    self.utility_bot_memory = ConversationBufferMemory()

    self.initialize_chains()
    self.emotion_images = {}

    # constants
    self.start_time = time.time()
    self.messages = []
    self.current_summary = ""
    self.database_file_name = "_records.txt"
    self.emotion_avatars = {
        "sad": 'https://i.imgur.com/wMxoXnf.png',
        "happy": 'https://i.imgur.com/Sf7RmzM.png',
        "cheerful": 'https://i.imgur.com/ul2Bwuv.png',
        "joyful": 'https://i.imgur.com/FMD9SHS.png',
        "neutral": 'static/icon.png',
        "shocked": 'https://i.imgur.com/UArPldR.png'
    }
    self.openai_api_key = params['open_api_key']

    # Generate all emotion images


  def reading_history(self, database_file_name):
    self.database_file_name = database_file_name
    if (os.path.isfile(database_file_name)
        ):  # if the file under the user already exists
      print("database has been loaded, memory is being read")
      read_file = open(database_file_name, "r")
      lines = read_file.readlines()
      for line in lines:
        parsed_messages = ast.literal_eval(line)
        for index in range(len(parsed_messages)):
          entry = parsed_messages[index]
          if entry['role'] == 'system' or entry['role'] == 'user':
            user_content = entry['content']
            assistant_content = parsed_messages[index + 1]['content']
            self.chat_bot_memory.save_context({"input": user_content},
                                {"output": assistant_content})
            self.summary_bot_memory.save_context({"input": user_content},
                                            {"output": assistant_content})
      self.messages.append({
          "role": "assistant",
          "content": "Would you like to continue our past conversation?",
          "time": time.ctime(time.time()),
          "emotion_image": self.emotion_avatars["neutral"]
      })
      read_file.close()
      print(self.messages)
      self.memory_loaded = True
    else:
      print("database has NOT been loaded, memory is being put")
      database_file = open(database_file_name, "a")
      self.messages.append({
          "role": "system",
          "content":
          f"AI:",
          "time": time.ctime(self.start_time),
          "emotion_image": self.emotion_avatars["neutral"]
      })

      self.chat_bot_memory.save_context(
          {
              "input":
              "AI:"
          }, {"output": "Yes, that sounds perfect!"})

      self.chat_bot_memory.save_context({"input": "Hello!"},
                          {"output": "Hello! How can I assist you today?"})

      self.messages.append({
          "role": "assistant",
          "content": "Hello! How can I assist you today?",
          "time": time.ctime(time.time()),
          "emotion_image": self.emotion_avatars["neutral"]
      })
      database_file.writelines(str(self.messages) + '\n')
      database_file.close()

  def initialize_chains(self):
    self.conversation_chain = ConversationChain(llm=self.chat_bot, verbose=True, memory=self.chat_bot_memory)

    self.summary_chain = ConversationChain(llm=self.summary_bot,
                                      verbose=True,
                                      memory=self.summary_bot_memory)

    self.utility_bot_chain = ConversationChain(llm=self.utility_bot,
                                          verbose=True,
                                          memory=self.utility_bot_memory)

  def summarize(self):
    '''
    Return the summary of the conversation with the summary_bot. 
    '''
    summary = self.summary_bot_memory.load_memory_variables({})['history']
    if len(summary) > 0:
      reply = self.utility_bot_chain.predict(
          input=f"Summarize this text as short as possible and disregard irrelevant details: { summary }")
      return reply
    else:
      return ""


  def get_response(self, input_text):
    '''
    Given user input, update the messages log and return the emotion and reply of the AI. 
    '''
    if input_text:
        # Initialize a new reply
        reply = {}

        # Parsing and recording the user text
        time_of_input = time.time()

        # Predicting and recording text from the assistant
        self.conversation_chain.predict(input=input_text)
        reply["response"] = parse_output(self.chat_bot_memory.load_memory_variables({})['history'])
        time_of_reply = time.time()

        self.summary_bot_memory.save_context(
          {"input": f"Please response to this in shorter than 100 words: {input_text}"}, 
          {"output": reply["response"]
        })

        # Predict emotion of user's reply from emotion list
        self.utility_bot_chain.predict(
            input=f"Respond in ONE WORD out of the following { str(len(self.emotion_avatars)).upper() } WORDS { str(self.emotion_avatars.keys()) }. Return one of the words to describe the following response with NO PUNCTUATION: { reply['response'] }"
        )

        emotion = valid_emotion(
            parse_output(self.utility_bot_memory.load_memory_variables({})['history']).lower(), 
            self.emotion_avatars
        )

        # Get the corresponding pre-generated emotion image URL
        if(len(self.emotion_images) > 0):
          emotion_image_url = self.emotion_images.get(emotion, self.emotion_avatars['neutral'])
          self.emotion_avatars = self.emotion_images
        else:
          emotion_image_url = self.emotion_avatars.get(emotion, self.emotion_avatars['neutral'])

        # Update the reply dictionary with the emotion image URL
        reply["emotion_img_url"] = emotion_image_url

        # Adding the user's input and the assistant's input into the messages
        user_dict = {
            "role": "user",
            "content": input_text,
            "time": time.ctime(time_of_input),
            "emotion_image": emotion_image_url  # Updated to use pre-generated emotion image
        }
        self.messages.append(user_dict)

        assistant_dict = {
            "role": "assistant",
            "content": reply["response"],
            "time": time.ctime(time_of_reply),
            "emotion_image": emotion_image_url  # Updated to use pre-generated emotion image
        }
        self.messages.append(assistant_dict)

        # Adding to the data file
        database_file = open(self.database_file_name, "a")
        database_file.writelines(str([user_dict, assistant_dict]) + '\n')

        self.current_summary = self.summarize()

        database_file.close()

        return reply
  # AUDIO HERE
  def text_to_speech(self, output_text):
    '''Given user input, get the appropriate response and convert it to speech.'''
    client = openai.OpenAI(api_key=os.environ['api_key'])

    response = client.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=output_text,
    )
    if os.path.exists('static/audio.mp3'):
      os.remove('static/audio.mp3')
    response.stream_to_file("static/audio.mp3")
  
# class Chatbot:
  def generate_all_emotion_images(self, user_prompt):
      '''
      Generate and store images for each emotion based on the user prompt.
      '''
      emotions = ['happy', 'sad', 'cheerful', 'joyful', 'neutral', 'shocked']
      images = {}
      for emotion in emotions:
          images[emotion] = self.generate_emotion_image(emotion, user_prompt)
      self.emotion_images = images

  def generate_emotion_image(self, emotion, user_prompt):
      '''
      Generate image based on perceived emotion of user response and the user prompt.
      '''
      openai.api_key = os.environ['api_key']

      try:
          response = openai.images.generate(
              prompt= f"{user_prompt} ONE avatar expressing this emotion, while staying lively and optimistic, NO TEXT:" + emotion,
              n=1,
              size="256x256"
          )

          # Accessing the image URL
          generated_image_url = response.data[0].url
          return generated_image_url

      except Exception as e:
          print(f"Error in generating image: {e}")
          return None