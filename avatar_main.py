import eng_to_ipa as ipa
import moviepy.editor as mp
import os
from pydub import AudioSegment
from pydub.silence import detect_silence
import random
import edge_tts
import asyncio

# Mapping of phonemes to visemes
phoneme_to_viseme = {
    'b': 'p', 'd': 't', 'ʤ': 'S_cap', 'ð': 'T_cap', 'f': 'f', 'ɡ': 'k', 'h': 'k', 'j': 'i', 'k': 'k',
    'l': 'l', 'm': 'p', 'n': 't', 'ŋ': 'k', 'p': 'p', 'r': 'r', 's': 's', 'ʃ': 'S_cap', 't': 't',
    'ʧ': 'S_cap', 'θ': 'T_cap', 'v': 'f', 'w': 'u', 'z': 's', 'ʒ': 'S_cap', 'ə': '@', 'ər': '@',
    'æ': 'a', 'aɪ': 'a', 'aʊ': 'a', 'ɑ': 'a', 'eɪ': 'e', 'ɛ': 'e', 'i': 'i', 'ɪ': 'i', 'oʊ': 'o',
    'ɔ': 'O_cap', 'ɔɪ': 'O_cap', 'u': 'u', 'ʊ': 'u', ' ': 'default', ',': 'default', '.': 'default',
}

def text_to_phonemes(text):
    """
    Convert text to phonemes using the eng_to_ipa library.

    Args:
        text (str): The input text to convert.

    Returns:
        str: The converted phonemes.
    """
    phonemes = ipa.convert(text)
    return phonemes

def text_to_visemes(text):
    """
    Convert text to visemes using the phoneme_to_viseme mapping.

    Args:
        text (str): The input text to convert.

    Returns:
        list: A list of visemes corresponding to the input text.
    """
    phonemes = text_to_phonemes(text)
    visemes = []
    for p in phonemes:
        chance = random.random()
        if p in phoneme_to_viseme and chance <= 0.8: # randomly skip some visemes to reduce video length
            visemes.append(phoneme_to_viseme[p])
    return visemes

async def text_to_speech(text, output_path, voice="en-US-GuyNeural"):
    """
    Generate TTS audio file from text using the Edge TTS API.

    Args:
        text (str): The input text to convert to speech.
        output_path (str): The path to save the generated audio file.
        voice (str, optional): The voice to use for TTS. Defaults to "en-US-GuyNeural".
    """
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def detect_silence_segments(audio_path, min_silence_len=200, silence_thresh=-40):
    """
    Detect silent segments in a TTS audio file.

    Args:
        audio_path (str): The path to the audio file.
        min_silence_len (int, optional): Minimum length of silence to detect (in ms). Defaults to 200.
        silence_thresh (int, optional): Silence threshold (in dB). Defaults to -40.

    Returns:
        list: A list of tuples representing the start and end of silent segments.
    """
    audio = AudioSegment.from_file(audio_path)
    silence_ranges = detect_silence(audio, min_silence_len=min_silence_len, silence_thresh=silence_thresh)
    return silence_ranges

def preload_viseme_clips(viseme_list, base_path):
    """
    Preloads video clips for all visemes and returns them in a dictionary.

    Args:
        viseme_list (list): List of visemes to load.
        base_path (str): The base path where viseme video clips are stored.

    Returns:
        dict: Dictionary where keys are visemes and values are the preloaded video clips.
    """
    viseme_clips = {}
    for viseme in viseme_list:
        clip_path = os.path.join(base_path, f"{viseme}.mp4") #mp4
        if os.path.exists(clip_path):
            viseme_clips[viseme] = mp.VideoFileClip(clip_path)
        else:
            print(f"Warning: Clip for viseme '{viseme}' not found. Using default.")
    
    # Preload the default clip for silent segments
    default_clip_path = os.path.join(base_path, "default.mp4") #mp4
    viseme_clips['default'] = mp.VideoFileClip(default_clip_path) if os.path.exists(default_clip_path) else None

    return viseme_clips


def create_video_from_visemes(visemes, silence_ranges, audio_duration, viseme_clips):
    """
    Optimized function to stitch viseme clips based on silent ranges.
    
    Args:
        visemes (list): A list of visemes.
        silence_ranges (list): A list of tuples representing the start and end of silent segments.
        audio_duration (float): The duration of the audio in seconds.
        viseme_clips (dict): Preloaded viseme clips.
    
    Returns:
        VideoFileClip: The final video clip.
    """
    clips = []
    current_time = 0
    viseme_index = 0
    
    # Create a silence map with 0.1 second granularity
    silence_map = [False] * int(audio_duration * 10)
    for start, end in silence_ranges:
        for i in range(int(start / 100), int(end / 100)):
            silence_map[i] = True
    
    # Loop over the audio duration
    while current_time < audio_duration:
        silence_idx = int(current_time * 10)
        if silence_idx < len(silence_map) and silence_map[silence_idx]:
            clips.append(viseme_clips['default'].set_duration(0.1))
            current_time += 0.1
        else:
            if viseme_index < len(visemes):
                viseme = visemes[viseme_index]
                if viseme in viseme_clips:
                    clip = viseme_clips[viseme]
                    clips.append(clip)
                    current_time += clip.duration
                viseme_index += 1

    if clips:
        final_clip = mp.concatenate_videoclips(clips, method="compose")
        return final_clip


async def create_talking_head(text, audio_output_path, final_output_path):
    """
    Create a talking head video from text with audio.

    Args:
        text (str): The input text to convert to a talking head video.
        audio_output_path (str): The path to save the generated audio file.
        final_output_path (str): The path to save the final video file.
    """
    print("************************************************\ntext_to_viseme")
    visemes = text_to_visemes(text)
    print("viseme gen done, tts")
    await text_to_speech(text, audio_output_path)
    print("tts finished")

    audio = AudioSegment.from_file(audio_output_path)
    audio_duration = len(audio) / 1000
    print("detecting silence")
    silence_ranges = detect_silence_segments(audio_output_path)
    print("silence ranges detected, creating video from visemes ")

    base_clip_path = "MedicineGPT/Viseme Clips/shortened/correct_crop"
    # viseme_list = ['p', 't', 'S_cap', 'T_cap', 'f', 'k', 'i', 'l', 'r', 's', 'u', '@', 'a', 'o', 'e', 'O_cap', 'default']
    viseme_list = ['p', 't', 'S_cap', 'T_cap', 'f', 'k', 'i', 'r', 's', 'u', '@', 'a', 'o', 'e', 'O_cap', 'default']
    viseme_clips = preload_viseme_clips(viseme_list, base_clip_path)
    video = create_video_from_visemes(visemes, silence_ranges, audio_duration, viseme_clips)
    print("video from visemes finished")
    video = video.without_audio()
    audio = mp.AudioFileClip(audio_output_path)
    print("syncing audio")
    final_video = video.set_audio(audio)
    print("audio synced, writing videofile")
    # try:
    final_video.write_videofile(final_output_path, codec="libx264", audio_codec="aac", threads=16, fps=20, preset="ultrafast", logger=None, verbose=False)
    # except OSError as e:
        # print(e)
    # final_video.write_videofile(
    #     final_output_path,
    #     codec="libx264",
    #     audio_codec="aac",
    #     threads=16,
    #     fps=15,
    #     preset="ultrafast",
    #     bitrate="500k",
    #     ffmpeg_params=["-crf", "35", "-tune", "fastdecode", "-movflags", "+faststart"],
    #     temp_audiofile='temp-audio.m4a',
    #     remove_temp=True,
    #     logger=None,
    #     verbose=False
    # )
    print("video file written\n********************************")

# # Example usage
# phrase = ("Black spots on the skin could be due to a variety of reasons, ranging from harmless freckles"
#           "to more serious conditions like melanoma. It's important to get a comprehensive understanding"
#           "of your condition. Could you provide more information on the size, number, and location of the"
#           "black spots? Also, have you noticed any changes in the spots over time? Lastly, do you have any"
#           "genetic predispositions to skin conditions, for example, a variant in the MC1R gene (rs 1805007)"
#           "which is associated with an increased risk for melanoma?")

# audio_output_path = "tts_audio.mp3"
# final_output_path = "talking_head.mp4"

# asyncio.run(create_talking_head(phrase, audio_output_path, final_output_path))