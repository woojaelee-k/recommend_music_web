import streamlit as st
import cv2
import numpy as np
import random
import requests
import base64
import urllib.parse  # URL 인코딩을 위해 사용
import streamlit.components.v1 as components  # 카카오톡 공유 버튼 위한 컴포넌트

from deepface import DeepFace

# 페이지 레이아웃 설정 (모바일 환경에서도 보기 좋게 "wide"로 설정)
st.set_page_config(page_title="사진 기반 노래 추천", layout="wide")

# 커스텀 CSS 추가 (모바일 최적화)
st.markdown(
    """
    <style>
    /* 전체 컨테이너 패딩 조정 */
    .reportview-container .main .block-container {
        padding: 2rem 1rem;
    }
    /* 제목 및 부제목 폰트 크기 조정 */
    h1 { font-size: 2.5rem; }
    h2 { font-size: 2rem; }
    h3 { font-size: 1.5rem; }
    /* 사이드바 스타일 조정 */
    .sidebar .sidebar-content {
        padding: 1rem;
    }
    /* 이미지 최대 너비 및 반응형 */
    img { max-width: 100%; height: auto; }
    
    /* 모바일 환경 (최대 너비 600px 이하) */
    @media only screen and (max-width: 600px) {
         .reportview-container .main .block-container {
              padding: 1rem 0.5rem;
         }
         h1 { font-size: 2rem; }
         h2 { font-size: 1.5rem; }
         h3 { font-size: 1.2rem; }
         .sidebar .sidebar-content {
              padding: 0.5rem;
         }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# API Credentials
# =========================
SPOTIFY_CLIENT_ID = "e22ce42055fc42689569ae59ed1e3a63"
SPOTIFY_CLIENT_SECRET = "0a7f637a96524ae6aef5fe235807d70f"
YOUTUBE_API_KEY = "YOUR_YOUTUBE_API_KEY"  # 본인의 YouTube API 키 입력

def get_spotify_token(client_id, client_secret):
    """🎧 Spotify access token 발급 (Client Credentials Flow)"""
    auth_str = f"{client_id}:{client_secret}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    token_url = "https://accounts.spotify.com/api/token"
    headers = {"Authorization": f"Basic {b64_auth_str}"}
    data = {"grant_type": "client_credentials"}
    response = requests.post(token_url, headers=headers, data=data)
    return response.json().get("access_token")

def get_youtube_video_link(query):
    """
    YouTube Data API를 사용해 query에 해당하는 첫 번째 영상의 URL을 반환합니다.
    """
    search_url = "https://www.googleapis.com/youtube/v3/search"
    params = {
       "part": "snippet",
       "q": query,
       "key": YOUTUBE_API_KEY,
       "maxResults": 1,
       "type": "video"
    }
    response = requests.get(search_url, params=params)
    data = response.json()
    items = data.get("items", [])
    if items:
         video_id = items[0]["id"]["videoId"]
         return f"https://www.youtube.com/watch?v={video_id}"
    else:
         return None

def get_recommended_songs(emotion):
    """
    감정에 따른 키워드 매핑에서 랜덤 키워드를 선택해 Spotify 검색 API를 호출하고,
    중복 없는 추천곡 5곡의 (곡 제목, 유튜브 영상 URL) 튜플 리스트를 반환합니다. 🎶
    """
    emotion_keyword_map = {
        "angry": [
            "angry", "furious", "irate", "enraged", "incensed", "seething",
            "outraged", "aggressive", "hostile", "fuming", "passionate", "fiery",
            "intense", "explosive", "combative", "defiant"
        ],
        "disgust": [
            "disgust", "repulsive", "revolting", "gross", "nauseating", "unpleasant",
            "sour", "offensive", "distasteful", "icky", "mucky", "vile", "yucky",
            "sordid", "repugnant", "abhorrent"
        ],
        "fear": [
            "fear", "scary", "eerie", "ominous", "haunting", "anxious", "tense",
            "alarming", "terrifying", "frightening", "spooky", "unsettling",
            "apprehensive", "startling", "paralyzing", "nervous", "petrifying"
        ],
        "happy": [
            "happy", "joyful", "uplifting", "cheerful", "feel good", "sunshine",
            "optimistic", "elated", "content", "delighted", "ecstatic", "radiant",
            "merry", "jubilant", "blissful", "exhilarated", "peppy", "vivacious"
        ],
        "sad": [
            "sad", "melancholy", "blue", "soulful", "heartbroken", "down", "somber",
            "depressed", "mournful", "gloomy", "forlorn", "dismal", "despondent",
            "sorrowful", "wistful", "tragic"
        ],
        "surprise": [
            "surprise", "unexpected", "exciting", "thrilling", "energetic",
            "astonishing", "startling", "amazing", "stunning", "shocking",
            "unforeseen", "unanticipated", "incredible", "breathtaking", "jaw-dropping"
        ],
        "neutral": [
            "neutral", "chill", "ambient", "calm", "relaxing", "soothing", "balanced",
            "placid", "undisturbed", "composed", "collected", "unemotional", "serene",
            "steady", "even-tempered", "measured", "moderate"
        ]
    }
    keywords = emotion_keyword_map.get(emotion, [emotion])
    query_keyword = random.choice(keywords)
    
    # Spotify API 토큰 발급
    token = get_spotify_token(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    search_headers = {"Authorization": f"Bearer {token}"}
    search_url = "https://api.spotify.com/v1/search"
    params = {
        "q": query_keyword,
        "type": "track",
        "limit": 50
    }
    search_response = requests.get(search_url, headers=search_headers, params=params)
    
    try:
        tracks = search_response.json().get("tracks", {}).get("items", [])
    except Exception as e:
        st.error(f"Spotify JSON 디코드 에러: {e} 😥")
        return []
    
    if not tracks:
        return []
    
    # 중복 제목 제거
    unique_tracks = {}
    for track in tracks:
        name = track.get("name")
        if name not in unique_tracks:
            unique_tracks[name] = track
    unique_track_list = list(unique_tracks.values())
    
    # 5곡 이상이면 랜덤하게 5곡 선택, 아니면 전부 선택
    if len(unique_track_list) >= 5:
        selected_tracks = random.sample(unique_track_list, 5)
    else:
        selected_tracks = unique_track_list
    
    # 결과 튜플 리스트 구성: (곡 제목, 유튜브 영상 URL)
    recommendations = []
    for track in selected_tracks:
        track_name = track.get("name")
        artists = ", ".join([artist.get("name") for artist in track.get("artists", [])])
        search_query = f"{track_name} {artists}"
        # YouTube Data API로 직접 영상 URL 가져오기
        yt_link = get_youtube_video_link(search_query)
        # 만약 영상 URL을 가져오지 못하면, 기본 검색 링크로 대체
        if yt_link is None:
            encoded_query = urllib.parse.quote(search_query)
            yt_link = f"https://www.youtube.com/results?search_query={encoded_query}"
        recommendations.append((f"{track_name} - {artists}", yt_link))
    return recommendations

# =========================
# Streamlit 앱 UI 구성
# =========================

# 사이드바에 앱 소개 추가
st.sidebar.markdown("### 📚 앱 소개")
st.sidebar.info(
    "이 앱은 사진을 통해 감정을 분석하고, "
    "해당 감정에 어울리는 Spotify 노래를 추천해드립니다! 😊"
)

# 메인 타이틀
st.title("📸🎵 사진 기반 노래 추천")

# 파일 업로드 섹션
st.markdown("## 👉 **사진을 업로드 해주세요!**")
uploaded_file = st.file_uploader("이미지 파일 선택 (png, jpg, jpeg, bmp)", type=["png", "jpg", "jpeg", "bmp"])

if uploaded_file is not None:
    # 업로드된 파일을 OpenCV 이미지로 변환
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    image = cv2.imdecode(file_bytes, 1)
    if image is None:
        st.error("이미지를 불러올 수 없습니다. 😢")
    else:
        st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption="업로드한 이미지", use_column_width=True)
        
        # 감정 분석 섹션
        st.markdown("### 🔍 감정 분석 중...")
        try:
            analysis = DeepFace.analyze(
                image, 
                actions=['emotion'],
                detector_backend='retinaface',
                enforce_detection=False
            )
            if isinstance(analysis, list):
                emotion_info = analysis[0]
            else:
                emotion_info = analysis
            dominant_emotion = emotion_info.get('dominant_emotion', "unknown")
            st.success(f"당신의 기분은 **{dominant_emotion}** 입니다! 🎉")
        except Exception as e:
            st.error(f"감정 분석 오류: {e} 😥")
            dominant_emotion = None
        
        # Spotify 추천곡 가져오기
        if dominant_emotion:
            st.markdown("### 🎶 추천곡을 가져오는 중...")
            rec_songs = get_recommended_songs(dominant_emotion)
            if rec_songs:
                st.subheader("추천곡 목록:")
                for song, yt_link in rec_songs:
                    # 바로 이동할 수 있도록 HTML 링크 사용 (target="_blank"로 새 탭에서 열림)
                    st.markdown(f'- <a href="{yt_link}" target="_blank">👉 {song}</a>', unsafe_allow_html=True)
            else:
                st.warning("추천 결과를 가져올 수 없습니다. 😓")

# 카카오톡 공유 버튼 추가
share_html = """
<script src="https://developers.kakao.com/sdk/js/kakao.js"></script>
<script>
  // 본인의 Kakao JavaScript 키로 초기화 (YOUR_KAKAO_APP_KEY를 변경하세요)
  Kakao.init('fbafd91ab0a63a6fe5fd34ea9f0b8797');  
  function sendKakaoLink() {
    Kakao.Link.sendDefault({
      objectType: 'feed',
      content: {
        title: '사진 기반 노래 추천',
        description: '이 앱을 사용해서 당신의 감정을 분석하고 추천곡을 확인해보세요!',
        imageUrl: 'https://your_image_url.com/your_image.png',  // 공유할 이미지 URL
        link: {
          mobileWebUrl: window.location.href,
          webUrl: window.location.href
        }
      },
      buttons: [
        {
          title: '앱 바로가기',
          link: {
            mobileWebUrl: window.location.href,
            webUrl: window.location.href
          }
        }
      ]
    });
  }
</script>
<button onclick="sendKakaoLink()" style="background-color:#F7E600; border:none; padding:10px 20px; font-size:16px; cursor:pointer;">
  카카오톡으로 공유하기
</button>
"""
components.html(share_html, height=250)
