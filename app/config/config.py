from dotenv import load_dotenv
import os
import streamlit as st
load_dotenv()

API_KEY = os.getenv("API_KEY") or st.secrets["API_KEY"]
API_MODEL = os.getenv("API_KEY") or st.secrets["API_MODEL"]