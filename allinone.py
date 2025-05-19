import threading
import subprocess
import time
import os
import json
import socket
from flask import Flask, request, jsonify
import streamlit as st
import requests
import numpy as np
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from textblob import TextBlob
import google.generativeai as genai  # 添加Gemini導入

# --- 固定 API Keys ---
spotify_client_id     = "b9e0979d54c449d4a1b7f23a1be1d329"
spotify_client_secret = "03559d2dc6b643e8af412d5930ee4ec2"
suno_api_key          = "b05e6e742e5b2a4043bd9c32bed4c57f"
# 添加Gemini API key
gemini_api_key        = "AIzaSyCTGS04JWKppuWZirt9VrgW9igpTaL9aOI"  # 請替換為你的Gemini API key

# 設置Gemini
genai.configure(api_key=gemini_api_key)

# --- Flask callback server with dynamic port ---
flask_app = Flask(__name__)

def find_available_port(start=5050):
    port = start
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
            port += 1

callback_port = find_available_port()

@flask_app.route("/callback", methods=["POST"])
def receive_callback():
    try:
        data = request.json
        os.makedirs("data", exist_ok=True)
        
        # 確保我們不會覆蓋現有數據
        if os.path.exists("data/music.json"):
            try:
                existing_data = json.load(open("data/music.json", "r", encoding="utf-8"))
                # 合併數據
                if "data" in existing_data and "data" in existing_data["data"]:
                    if "data" in data and "data" in data["data"]:
                        existing_data["data"]["data"].extend(data["data"]["data"])
                        data = existing_data
            except Exception as e:
                st.error(f"合併數據時出錯: {str(e)}")
                
        with open("data/music.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        # 創建一個標記文件，表示有新數據
        with open("data/music_updated.flag", "w") as f:
            f.write(str(time.time()))
            
        return jsonify({"code": 200, "msg": "Callback received"})
    except Exception as e:
        return jsonify({"code": 500, "msg": f"Error: {str(e)}"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=callback_port)

def start_callback_server():
    threading.Thread(target=run_flask, daemon=True).start()

# --- Smart ngrok launcher ---
def start_ngrok():
    try:
        tunnels = requests.get("http://localhost:4040/api/tunnels").json().get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                return t["public_url"] + "/callback"
    except:
        pass

    ngrok_path = "/opt/homebrew/bin/ngrok"
    subprocess.Popen([ngrok_path, "http", str(callback_port)], stdout=subprocess.DEVNULL)
    time.sleep(2)
    try:
        tunnels = requests.get("http://localhost:4040/api/tunnels").json().get("tunnels", [])
        for t in tunnels:
            if t.get("proto") == "https":
                return t["public_url"] + "/callback"
    except:
        pass

    return f"http://127.0.0.1:{callback_port}/callback"

# --- Auto-rerun on file change via query params hack ---
def auto_rerun_on_file_change():
    flag_path = "data/music_updated.flag"
    if os.path.exists(flag_path):
        mtime = os.path.getmtime(flag_path)
        last = st.session_state.get("music_flag_mtime", 0)
        if mtime != last:
            st.session_state["music_flag_mtime"] = mtime
            # 移除標記文件，避免重複觸發
            os.remove(flag_path)
            # 更改查詢參數觸發重新運行
            st.experimental_set_query_params(music_mtime=mtime)

# --- Spotify helper functions ---
def get_spotify_token():
    resp = requests.post(
        "https://accounts.spotify.com/api/token",
        data={"grant_type": "client_credentials"},
        auth=(spotify_client_id, spotify_client_secret)
    )
    if resp.status_code != 200:
        return None
    return resp.json().get("access_token")

def extract_playlist_id(url):
    return url.rstrip("/").split("/")[-1].split("?")[0]

def get_playlist_tracks(token, pid):
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://api.spotify.com/v1/playlists/{pid}/tracks"
    items = []
    while url:
        r = requests.get(url, headers=headers)
        if r.status_code != 200:
            st.error(f"獲取播放列表失敗: {r.text}")
            return []
        data = r.json()
        items.extend(data["items"])
        url = data.get("next")
    return items

def get_playlist_details(token, pid):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"https://api.spotify.com/v1/playlists/{pid}", headers=headers)
    if r.status_code != 200:
        st.error(f"獲取播放列表詳情失敗: {r.text}")
        return {}
    return r.json()

def get_lyrics(artist, title):
    a = artist.strip().lower().replace(" ", "%20")
    t = title.strip().lower().replace(" ", "%20")
    try:
        r = requests.get(f"https://api.lyrics.ovh/v1/{a}/{t}", timeout=5)
        if r.status_code == 200:
            return r.json().get("lyrics") or "Lyrics not found"
    except Exception as e:
        st.warning(f"獲取歌詞失敗: {str(e)}")
    return "Lyrics not found"

# --- Visualization helpers ---
def generate_wordcloud(text):
    return WordCloud(width=400, height=200, background_color="white", max_words=100).generate(text)

def compute_sentiment_scores(lyrics):
    blob = TextBlob(lyrics)
    p, s = blob.sentiment.polarity, blob.sentiment.subjectivity
    mood = {"joy":0,"sadness":0,"anger":0,"fear":0,"love":0,"surprise":0}
    if p >= 0.4:
        mood["joy"] += 1
        if s > 0.6: mood["love"] += 1
    elif p <= -0.4:
        mood["sadness"] += 1
        if s > 0.5: mood["anger"] += 1
    else:
        if s < 0.3: mood["fear"] += 1
        elif s > 0.6: mood["surprise"] += 1
    return mood

def plot_mood_radar(mood):
    labels = list(mood.keys())
    values = list(mood.values())
    angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist()
    values += values[:1]; angles += angles[:1]
    fig, ax = plt.subplots(figsize=(3,2), subplot_kw={"polar": True})
    ax.plot(angles, values, linewidth=2)
    ax.fill(angles, values, alpha=0.3)
    ax.set_xticks(angles[:-1]); ax.set_xticklabels(labels)
    ax.set_yticklabels([])
    return fig

# --- Gemini AI helper ---
def analyze_with_gemini(lyrics, track_info):
    try:
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        分析以下歌曲的歌詞並提供洞見:
        
        曲目: {track_info['title']}
        藝術家: {track_info['artist']}
        
        歌詞:
        {lyrics}
        
        請提供:
        1. 歌詞的主要主題和情感
        2. 作者可能想傳達的訊息
        3. 3-5個關鍵詞來概括這首歌
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Gemini分析失敗: {str(e)}"

# --- Main Streamlit App ---
def main():
    st.set_page_config(page_title="Unified Music & Lyrics App", layout="wide")

    # 初始化session_state
    if "music_flag_mtime" not in st.session_state:
        st.session_state["music_flag_mtime"] = 0
    if "active_tab" not in st.session_state:
        st.session_state["active_tab"] = 0
    if "generation_in_progress" not in st.session_state:
        st.session_state["generation_in_progress"] = False

    auto_rerun_on_file_change()
    start_callback_server()
    callback_url = start_ngrok()

    # 處理音樂生成狀態
    if st.session_state.get("generation_in_progress", False):
        st.info("⏳ 音樂生成進行中... 請等待回調完成。")
        
        # 檢查是否有新的音樂文件
        if os.path.exists("data/music.json"):
            mtime = os.path.getmtime("data/music.json")
            last = st.session_state.get("last_music_check", 0)
            if mtime > last:
                st.session_state["generation_in_progress"] = False
                st.session_state["active_tab"] = 1  # 切換到播放器標籤
                st.session_state["last_music_check"] = mtime
                st.experimental_rerun()

    tabs = st.tabs(["🎶 Music Creator", "🎧 Music Player", "🔍 Spotify Analyzer"])
    st.session_state["active_tab"] = st.session_state.get("active_tab", 0)
    
    # --- Music Creator Tab ---
    with tabs[0]:
        st.header("Create Music with Suno")
        st.markdown(f"**Callback URL:** `{callback_url}`")

        with st.form("music_form"):
            prompt       = st.text_area("Prompt (idea or lyrics)")
            style        = st.text_input("Music Style (e.g., Jazz, Pop)")
            title        = st.text_input("Track Title")
            model_sel    = st.selectbox("Model Version", ["V3_5", "V4", "V4_5"])
            instrumental = st.checkbox("Instrumental Only", value=False)
            neg_styles   = st.text_input("Exclude Styles (e.g., Heavy Metal)")

            submitted = st.form_submit_button("Generate Music")
            if submitted:
                if not prompt:
                    st.error("請提供生成提示!")
                else:
                    payload = {
                        "prompt": prompt,
                        "style": style,
                        "title": title or "Untitled",
                        "customMode": True,
                        "instrumental": instrumental,
                        "model": model_sel,
                        "negativeTags": neg_styles,
                        "callBackUrl": callback_url
                    }
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {suno_api_key}"
                    }
                    
                    try:
                        with st.spinner("發送生成請求..."):
                            r = requests.post("https://apibox.erweima.ai/api/v1/generate",
                                            headers=headers, json=payload)
                            
                        if r.status_code == 200:
                            st.success("音樂生成請求已發送! 正在等待回調...")
                            st.session_state["generation_in_progress"] = True
                            st.session_state["last_music_check"] = time.time()
                        else:
                            st.error(f"錯誤 {r.status_code}: {r.text}")
                            st.json(r.json())
                    except Exception as e:
                        st.error(f"請求發送失敗: {str(e)}")

    # --- Music Player Tab ---
    with tabs[1]:
        st.header("Your Generated Music")
        path = "data/music.json"
        if os.path.exists(path):
            try:
                data = json.load(open(path, encoding="utf-8"))
                music_data = data.get("data", {}).get("data", [])
                
                if not music_data:
                    st.info("尚無音樂數據。")
                else:
                    for i, t in enumerate(music_data, 1):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.subheader(f"{i}. {t.get('title','Untitled')}")
                            img = t.get("image_url","").strip()
                            if img:
                                st.image(img, width=200)
                        
                        with col2:
                            audio_url = t.get("audio_url") or t.get("stream_audio_url","")
                            if audio_url:
                                st.audio(audio_url)
                            else:
                                st.info("音頻尚未準備好。")
                            
                            # 顯示生成的提示和風格
                            st.markdown(f"**提示:** {t.get('prompt', 'N/A')}")
                            st.markdown(f"**風格:** {t.get('style', 'N/A')}")
                            
                        st.markdown("---")
            except Exception as e:
                st.error(f"讀取音樂數據時出錯: {str(e)}")
        else:
            st.info("尚未生成音樂。請使用Music Creator標籤創建音樂。")

    # --- Spotify Analyzer Tab ---
    with tabs[2]:
        st.header("Spotify Playlist Analyzer")
        playlist_url = st.text_input("Spotify Playlist URL",
                                     placeholder="https://open.spotify.com/playlist/...")

        if playlist_url:
            with st.spinner("正在與Spotify認證..."):
                token = get_spotify_token()
            if not token:
                st.error("獲取Spotify令牌失敗。")
                return

            try:
                pid = extract_playlist_id(playlist_url)
                
                # 獲取播放列表詳情
                playlist_info = get_playlist_details(token, pid)
                if playlist_info:
                    st.subheader(f"分析中: {playlist_info.get('name', '未知播放列表')}")
                    
                    if 'images' in playlist_info and playlist_info['images']:
                        col1, col2 = st.columns([1, 3])
                        with col1:
                            st.image(playlist_info['images'][0]['url'], width=150)
                        with col2:
                            st.markdown(f"**創建者:** {playlist_info.get('owner', {}).get('display_name', '未知')}")
                            st.markdown(f"**曲目數:** {playlist_info.get('tracks', {}).get('total', 0)}")
                
                # 獲取曲目
                items = get_playlist_tracks(token, pid)
                total = len(items)
                
                if total == 0:
                    st.warning("播放列表中沒有曲目。")
                    return
                    
                progress = st.progress(0)
                tracks_with_lyrics = []
                
                # 創建容器以控制布局
                lyrics_container = st.container()
                col1, col2 = st.columns([1, 1])
                
                with st.spinner("獲取歌詞和分析中..."):
                    for idx, item in enumerate(items):
                        tr = item.get("track")
                        if tr:
                            artist = tr["artists"][0]["name"]
                            title  = tr["name"]
                            lyrics = get_lyrics(artist, title)
                            tracks_with_lyrics.append({"artist":artist, "title":title, "lyrics":lyrics})
                        progress.progress((idx+1)/total)

                all_lyrics = " ".join([x["lyrics"] for x in tracks_with_lyrics
                                       if x["lyrics"] != "Lyrics not found"])
                                       
                if all_lyrics:
                    # 在左列顯示文字雲
                    with col1:
                        st.subheader("詞頻分析")
                        wc = generate_wordcloud(all_lyrics)
                        st.image(wc.to_image())
                    
                    # 在右列顯示情感雷達圖
                    with col2:
                        st.subheader("情感分析")
                        mood = compute_sentiment_scores(all_lyrics)
                        fig = plot_mood_radar(mood)
                        st.pyplot(fig)
                        
                        # 添加情感解釋
                        mood_descriptions = {
                            "joy": "積極和歡樂",
                            "sadness": "哀傷和悲傷",
                            "anger": "激烈和憤怒",
                            "fear": "不安和恐懼",
                            "love": "情感和連結",
                            "surprise": "意想不到和新奇"
                        }
                        
                        st.markdown("### 情感分布")
                        for mood_name, score in mood.items():
                            if score > 0:
                                st.markdown(f"- **{mood_name}**: {mood_descriptions[mood_name]} - 得分: {score}")
                                
                    # 使用Gemini分析歌詞
                    if gemini_api_key != "YOUR_GEMINI_API_KEY":
                        st.subheader("AI深度歌詞分析")
                        # 選擇一首有歌詞的歌曲進行分析
                        songs_with_lyrics = [t for t in tracks_with_lyrics if t["lyrics"] != "Lyrics not found"]
                        if songs_with_lyrics:
                            selected_song = st.selectbox(
                                "選擇要分析的歌曲",
                                options=range(len(songs_with_lyrics)),
                                format_func=lambda i: f"{songs_with_lyrics[i]['artist']} - {songs_with_lyrics[i]['title']}"
                            )
                            
                            if st.button("分析歌詞"):
                                selected_track = songs_with_lyrics[selected_song]
                                with st.spinner("正在使用Gemini分析歌詞..."):
                                    analysis = analyze_with_gemini(
                                        selected_track["lyrics"], 
                                        {"title": selected_track["title"], "artist": selected_track["artist"]}
                                    )
                                    st.markdown(analysis)
                        else:
                            st.info("沒有找到可分析的歌詞。")
                    else:
                        st.info("要啟用AI歌詞分析，請設置Gemini API密鑰。")
                        
                    # 顯示所有找到歌詞的歌曲
                    with lyrics_container:
                        st.subheader("歌詞瀏覽")
                        for idx, track in enumerate(tracks_with_lyrics):
                            if track["lyrics"] != "Lyrics not found":
                                with st.expander(f"{track['artist']} - {track['title']}"):
                                    st.markdown(track["lyrics"].replace("\n", "  \n"))
                else:
                    st.warning("未找到分析用的歌詞。API可能限制了請求或歌詞不可用。")
            except Exception as e:
                st.error(f"分析過程中出錯: {str(e)}")

if __name__ == "__main__":
    main()