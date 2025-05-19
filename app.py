from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

@app.route('/callback', methods=['POST'])
def receive_callback():
    # 取得 JSON 格式的 callback 資料
    data = request.json
    print("✅ Received callback:", data)

    # 確保 data 資料夾存在
    os.makedirs("data", exist_ok=True)

    # 將 callback 的資料寫入 music.json，供 Streamlit 播放頁讀取
    with open("data/music.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 回應 Suno API：已成功接收
    return jsonify({"code": 200, "msg": "Callback received successfully"})

if __name__ == '__main__':
    # 開啟 Flask server，監聽 port 5000
    app.run(host='0.0.0.0', port=5050)