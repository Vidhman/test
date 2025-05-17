import streamlit as st
from gtts import gTTS
import io
import wave
import zipfile
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import numpy as np
import av


st.set_page_config(page_title="Multi-Voice Converter", layout="centered")


if 'step' not in st.session_state:
    st.session_state.step = 'select_voice'
if 'selected_voice' not in st.session_state:
    st.session_state.selected_voice = None
if 'audio_data' not in st.session_state:
    st.session_state.audio_data = {}
if 'audio_filename' not in st.session_state:
    st.session_state.audio_filename = {}


def create_download_all_button():
    if st.session_state.audio_data:
        col1, col2, col3 = st.columns([4, 1, 1])
        with col3:
            if st.button("⬇️ Download All", key="download_all"):
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zipf:
                    for voice, audio_bytes in st.session_state.audio_data.items():
                        filename = st.session_state.audio_filename[voice]
                        zipf.writestr(filename, audio_bytes)
                zip_buffer.seek(0)
                st.download_button(
                    label="Download ZIP",
                    data=zip_buffer,
                    file_name="all_processed_audios.zip",
                    mime="application/zip",
                    key="download_zip_button"
                )


if st.session_state.step == 'select_voice':
    create_download_all_button()
    st.title("Step 1: Select a Voice")
    voice_options = [f"{i}" for i in range(1, 10)]
    selected_voice = st.selectbox("Choose a voice:", voice_options)

    if st.button("Next"):
        st.session_state.selected_voice = selected_voice
        st.session_state.step = 'select_input'


elif st.session_state.step == 'select_input':
    create_download_all_button()
    st.title("Step 2: Provide Input")
    st.write(f"**Selected Voice:** {st.session_state.selected_voice}")

    input_method = st.radio("Choose input method:", ["Text Input", "Upload Audio", "Record Audio"])

    if input_method == "Text Input":
        user_text = st.text_area("Enter text to convert to speech:")
        if st.button("Convert"):
            if user_text:
                tts = gTTS(text=user_text, lang='en')
                buffer = io.BytesIO()
                tts.write_to_fp(buffer)
                audio_bytes = buffer.getvalue()
                st.session_state.audio_data[st.session_state.selected_voice] = audio_bytes
                st.session_state.audio_filename[st.session_state.selected_voice] = f"{st.session_state.selected_voice}.mp3"
                st.session_state.step = 'download'
            else:
                st.warning("Please enter some text.")

    elif input_method == "Upload Audio":
        uploaded_file = st.file_uploader("Upload an audio file:", type=["mp3", "wav", "ogg"])
        if uploaded_file:
            audio_bytes = uploaded_file.read()
            ext = uploaded_file.name.split('.')[-1].lower()
            st.session_state.audio_data[st.session_state.selected_voice] = audio_bytes
            st.session_state.audio_filename[st.session_state.selected_voice] = f"{st.session_state.selected_voice}.{ext}"
            st.session_state.step = 'download'

    elif input_method == "Record Audio":
        st.write("Click the button below to start recording:")

        class AudioProcessor(AudioProcessorBase):
            def __init__(self):
                super().__init__()
                self.frames = []
                self.sample_rate = 16000
                self.sample_width = 2
                self.channels = 1

            def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
                array = frame.to_ndarray()
                if array.ndim == 2:
                    array = np.mean(array, axis=0)
                array = (array * 32767).astype(np.int16)
                self.frames.append(array)
                return frame

            def get_audio(self):
                if not self.frames:
                    return None
                return np.concatenate(self.frames, axis=0)

        webrtc_ctx = webrtc_streamer(
            key="audio-recorder",
            mode=WebRtcMode.SENDONLY,
            audio_processor_factory=AudioProcessor,
            media_stream_constraints={
                "audio": {
                    "sampleRate": 16000,
                    "channelCount": 1,
                    "echoCancellation": True,
                    "noiseSuppression": True,
                    "autoGainControl": True,
                },
                "video": False
            },
            rtc_configuration={"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
        )

        if webrtc_ctx.audio_processor and st.button("Stop and Save Recording"):
            audio_data = webrtc_ctx.audio_processor.get_audio()
            if audio_data is not None:
                buffer = io.BytesIO()
                with wave.open(buffer, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(audio_data.tobytes())
                audio_bytes = buffer.getvalue()
                st.session_state.audio_data[st.session_state.selected_voice] = audio_bytes
                st.session_state.audio_filename[st.session_state.selected_voice] = f"{st.session_state.selected_voice}.wav"
                st.session_state.step = 'download'


elif st.session_state.step == 'download':
    create_download_all_button()
    st.title("Step 3: Download Processed Audio")
    st.write(f"**Selected Voice:** {st.session_state.selected_voice}")

    if st.session_state.audio_data.get(st.session_state.selected_voice):
        file_ext = st.session_state.audio_filename[st.session_state.selected_voice].split('.')[-1]
        st.audio(st.session_state.audio_data[st.session_state.selected_voice], format=f"{file_ext}")
        st.download_button(
            label="Download Audio",
            data=st.session_state.audio_data[st.session_state.selected_voice],
            file_name=st.session_state.audio_filename[st.session_state.selected_voice],
            mime=f"{file_ext}"
        )

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("Go Back to Process More"):
            st.session_state.step = 'select_voice'
            st.session_state.selected_voice = None
    with col2:
        if st.button("Reset All"):
            st.session_state.step = 'select_voice'
            st.session_state.selected_voice = None
            st.session_state.audio_data = {}
            st.session_state.audio_filename = {}
