import streamlit as st
import json
import os

st.set_page_config(page_title="🎧 Suno Generated Music", layout="centered")
st.title("🎧 Your Generated Songs")
music_data_path = "data/music.json"

if os.path.exists(music_data_path):
    with open(music_data_path, "r", encoding="utf-8") as f:
        music_data = json.load(f)

    if music_data.get("data") and music_data["data"].get("data"):
        for i, track in enumerate(music_data["data"]["data"]):
            st.subheader(f"🎵 {track.get('title', f'Track {i+1}')}")
            st.markdown(f"**Prompt:** {track.get('prompt', '')}")
            st.markdown(f"**Tags:** {track.get('tags', '')}")
            st.audio(track.get("audio_url"), format="audio/mp3")
            st.image(track.get("image_url"))
            st.markdown("---")
    else:
        st.info("No tracks found in music.json. Please wait for callback after generation.")
else:
    st.warning("music.json not found. Please generate music first using the creator page.")
    
#streamlit run app.py