import firebase_admin 
import streamlit as st

from streamlit_theme import st_theme
from firebase_admin import credentials
from firebase_utils import ProjectUtilities
from ui import Page, SessionState, UserAuthenticationComponent, MainInterface

def run_periodic_cleanup():
    if 'user_id' in st.session_state and st.session_state['user_id']:
        project_utilities = ProjectUtilities(f"{st.session_state['user_id']}_Project")
        project_utilities.delete_old_sessions()

@st.cache_resource
def initialize_app(creds, options = None):
    creds = credentials.Certificate(creds)
    firebase_admin.initialize_app(creds, options)
    print('Firebase application initialized successfully.')

def main():
    initialize_app(creds = dict(st.secrets['FIREBASE_CREDENTIALS']), 
                   options = {'storageBucket':st.secrets['FIREBASE_STORAGE']})
    SessionState().initialize()

    theme = st_theme()
    if theme['base'] == 'dark':
        st.image('logo/DocuMate-dark.png')
    else:
        st.image('logo/DocuMate-light.png')
    
    st.write("""> DocuMate is a Retrieval-Augmented Genseration (RAG) chatbot built on top of ChatGPT that is designed to assist you by answering 
             your questions based on the contents of the files you provide. Simply upload a document, and DocuMate will read and understand its contents, 
             allowing you to ask questions and receive well-informed responses.""")

    AuthPage = Page()
    MainPage = Page()
    
    AuthPage.add_component('Authentication', UserAuthenticationComponent())
    MainPage.add_component('Main Interface', MainInterface())

    if st.session_state['user'] is None:
        AuthPage.render()
    else:   
        MainPage.render()

    run_periodic_cleanup()

if __name__ == '__main__':
    main()
