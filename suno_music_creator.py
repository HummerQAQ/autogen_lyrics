import streamlit as st
import requests
import json
import subprocess
import time
import re

st.set_page_config(page_title="🎶 Create Music", layout="centered")
st.title("🎶 Music Creator")

st.markdown("Generate music with AI using the Suno API.")

# 啟動 ngrok 並取得公開 callback URL
def start_ngrok():
    # 啟動 ngrok 指向 Flask callback 的 5000 埠
    subprocess.Popen(["ngrok", "http", "5050"], stdout=subprocess.DEVNULL)
    time.sleep(2)  # 等待 ngrok 啟動

    try:
        # 呼叫 ngrok 本地 API 查詢 public_url
        res = requests.get("http://localhost:4040/api/tunnels")
        tunnels = res.json().get("tunnels", [])
        for tunnel in tunnels:
            if tunnel.get("proto") == "https":
                return tunnel.get("public_url") + "/callback"
    except:
        return ""

# 啟動 ngrok 並取得預設 callback URL
default_callback_url = start_ngrok()

# User input form
with st.form("music_form"):
    st.subheader("🎼 Music Settings")
    prompt = st.text_area("Prompt (idea or lyrics)", max_chars=3000)
    style = st.text_input("Music Style (e.g., Jazz, Classical, Pop)")
    title = st.text_input("Track Title")
    model = st.selectbox("Model Version", ["V3_5", "V4", "V4_5"])
    instrumental = st.checkbox("Instrumental Only", value=True)
    use_custom_mode = st.checkbox("Use Custom Mode", value=True)
    negative_tags = st.text_input("Exclude Styles (e.g., Heavy Metal, Upbeat Drums)")
    callback_url = st.text_input("Callback URL", value=default_callback_url or "https://a222-140-114-195-205.ngrok-free.app.ngrok.io/callback")

    submitted = st.form_submit_button("Generate Music")

    if submitted:
        if use_custom_mode:
            if not title or not style:
                st.warning("Style and Title are required in Custom Mode")
                st.stop()
            if not instrumental and not prompt:
                st.warning("Prompt is required when not instrumental")
                st.stop()
        else:
            if not prompt:
                st.warning("Prompt is required in Non-Custom Mode")
                st.stop()

        # API request payload
        payload = {
            "prompt": prompt,
            "style": style if use_custom_mode else "",
            "title": title if use_custom_mode else "",
            "customMode": use_custom_mode,
            "instrumental": instrumental,
            "model": model,
            "negativeTags": negative_tags,
            "callBackUrl": callback_url
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer b45c6c654f252e66af0a7ff8061f81bd"
        }

        try:
            response = requests.post("https://apibox.erweima.ai/api/v1/generate", headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                st.subheader("📩 Raw API Response")
                st.json(response.json())
                data = response.json()
                task_id = data.get("data", {}).get("taskId")
                st.success(f"🎵 Music generation started! Task ID: {task_id}")
                st.info("The music will be sent to your callback URL once completed.")
            else:
                st.error(f"API Error: {response.status_code} - {response.text}")
        except Exception as e:
            st.error(f"Request failed: {e}")