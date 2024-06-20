import firebase_admin 
import streamlit as st

from streamlit_theme import st_theme
from firebase_admin import credentials
from firebase_utils import ProjectUtilities
from ui import Page, SessionState, UserAuthenticationComponent, MainInterface

icons = {
    'linkedin' : """
                <a href="https://www.linkedin.com/in/sean-andrie-gadingan-703620297/" target="_blank">
                    <button type="button" class="icon-button">
                        <i class="fa-brands fa-linkedin-in"></i>
                    </button>
                </a>
                """,
    'email' : """
                <a href="mailto:seanandriegadingan@gmail.com" target="_blank">
                    <button type="button" class="icon-button">
                        <i class="fa-solid fa-envelope"></i>
                    </button>
                </a>
              """
}

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
    st.set_page_config(**dict(st.secrets['PAGE_CONFIG']))
    initialize_app(creds = dict(st.secrets['FIREBASE_CREDENTIALS']), 
                   options = {'storageBucket':st.secrets['FIREBASE_STORAGE']})
    SessionState().initialize()

    theme = st_theme()
    if theme['base'] == 'dark':
        st.image('logo/DocuMate-dark.png')
        st.session_state['icon-config']['bg-color'] = '#0E1117'
        st.session_state['icon-config']['color'] = '#FFFFFF'
        st.session_state['icon-config']['bg-color-on-hover'] = '#FFFFFF'
        st.session_state['icon-config']['color-on-hover'] = '#0E1117'
    else:
        st.image('logo/DocuMate-light.png')
        st.session_state['icon-config']['bg-color'] = '#FFFFFF'
        st.session_state['icon-config']['color'] = '#0E1117' 
        st.session_state['icon-config']['bg-color-on-hover'] = '#0E1117'
        st.session_state['icon-config']['color-on-hover'] = '#FFFFFF'
    
    st.write("""> DocuMate is a Retrieval-Augmented Generation (RAG) chatbot built on top of ChatGPT that is designed to assist you by answering 
                your questions based on the contents of the files you provide. Simply upload a document, and DocuMate will read and understand its contents, 
                allowing you to ask questions and receive well-informed responses. 
            """)
    
    style = f"""
    <style>

    .icon-button {{
        background-color:{st.session_state['icon-config']['bg-color']}; 
        color:{st.session_state['icon-config']['color']};
        display:inline-block;
        font-size: 15px;
        text-decoration:none;
        cursor: pointer;
        border-color:transparent;
        border-radius:4px;
        transition-duration: 0.4s;
    }}

    .icon-button:hover {{
        background-color:{st.session_state['icon-config']['bg-color-on-hover']};
        color:{st.session_state['icon-config']['color-on-hover']};
    }}

    a {{
        text-decoration: none;
    }}

    a:hover {{
        text-decoration: none;
    }}

    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    """
    st.write(style, unsafe_allow_html=True)
    st.markdown(f"""by **Sean Gadingan** ({icons['linkedin']}/{icons['email']})""", unsafe_allow_html=True)

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
