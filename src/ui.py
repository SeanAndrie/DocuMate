import os
import re
import json
import time
import openai
import requests
import streamlit as st

from openai import OpenAI
from rag import CreateRAG
from datetime import datetime
from firebase_admin import auth
from firebase_utils import ProjectUtilities

class Page:
    def __init__(self):
        self.components = {}

    def add_component(self, id, component):
        self.components[id] = component
    
    def render(self):
        for id, component in self.components.items():
            component.render()

class UserAuthenticationComponent:
    def __init__(self):
        self.email = None
        self.user = None
        self.password = None
        self.project = None

    def validate_email(self, email):
        regex = '^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
        return re.match(regex, email)

    def check_fields(self, email, password):
        if email == '' or password == '':
            st.error('Email or password is missing.')
            return False
        
        if not self.validate_email(email):
            st.error('Invalid Email Address.')
            return False
        
        return True

    def login(self):
        try:
            rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            payload = json.dumps({
                "email": self.email,
                "password": self.password,
                "returnSecureToken": True
            })

            r = requests.post(rest_api_url,
                            params={"key": os.getenv("FIREBASE_WEB_API_KEY")},
                            data=payload)
            r.raise_for_status()
            
            self.user = auth.get_user_by_email(self.email)
            st.session_state['user'] = self.user.email
            st.session_state['user_id'] = self.user.uid
            st.session_state['project'] = ProjectUtilities(f"{st.session_state['user_id']}_Project")
            
            if st.session_state['project'].sessions_list:
                st.session_state['chats'] = st.session_state['project'].get_sessions_data()
            else:
                st.session_state['project'].create_project_folder()

            st.rerun()

        except requests.exceptions.RequestException as e:
            st.error('Invalid Credentials. Please try again.')

        except auth.UserNotFoundError:
            st.error("User not found. Please register by selecting the 'register' option in the dropdown menu.") 
    
    def register(self):
        try:
            user = auth.create_user(email=self.email, password=self.password)
            st.success(f'Account registered. Please log-in.')
        except auth.EmailAlreadyExistsError:
            st.error('Email already exists. Please Log-in')
        except Exception as e:
            st.error(f'Error: {e}')
    
    def render(self):
        st.divider()
        option = st.selectbox('Login or Register', ['Login', 'Register'])
        if option == 'Login':
            with st.form(key = option):
                self.email = st.text_input('Email')
                self.password = st.text_input('Password', type='password')
                submit = st.form_submit_button(label='Log In', use_container_width=True)
        
                if submit:
                    if self.check_fields(self.email, self.password):
                        self.login()

        if option == 'Register':
            with st.form(key = option):
                self.email = st.text_input('Email')
                self.password = st.text_input('Password', type = 'password')
                submit = st.form_submit_button(label='Create account', use_container_width=True)

                if submit:
                    if self.check_fields(self.email, self.password):
                        self.register()      

class BaseInterface:
    def __init__(self, name, idx, openai_api_key, temperature, chunk_size, chunk_overlap, borders=True):
        self.name = name
        self.idx = idx
        self.openai_api_key = openai_api_key
        self.temperature = temperature
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._upload_container = st.container(border=borders)
        self._message_container = st.container(border=borders)
        self._prompt_container = st.container(border=borders)
    
    def is_valid_api_key(self):
        if self.openai_api_key:
            try:
                client = OpenAI(
                    api_key=self.openai_api_key
                )
                models = client.models.list()
                return True
            except openai.AuthenticationError:
                return False
            except Exception as e:
                st.error(f'Error occurred while validating API key: {str(e)}')

    def upload_document(self):
        session_context_file = st.session_state['chats'][f'Session {self.idx}']['context_file']
        with self._upload_container:
            document = st.file_uploader('Upload your document here', key=f'file_uploader_{self.idx}', type=['pdf', 'docx', 'txt'])
            if document and session_context_file is None:
                st.session_state['chats'][f'Session {self.idx}']['context_file'] = document
            else:
                document = session_context_file
        return document

    def render_messages(self):
        with self._message_container:
            for message in st.session_state['chats'][f'Session {self.idx}']['logs']:
                chat_box = st.chat_message(message['role'])
                chat_box.markdown(message['content'])

    def stream_response(self, response, delay=0.02):
        for chunk in response:
            if answer_chunk := chunk.get('answer'):
                yield f'{answer_chunk}'
                time.sleep(delay)

class ChatInterface(BaseInterface):
    def __init__(self, name, idx, openai_api_key, temperature, chunk_size, chunk_overlap):
        super().__init__(name, idx, openai_api_key, temperature, chunk_size, chunk_overlap)
    
    def download_session_log(self):
        session_name = self.name
        session_logs = st.session_state['chats'][session_name]['logs']
        
        logs_json = json.dumps(session_logs, indent=2)
        
        st.download_button(
            label='Download Session Log',
            data=logs_json,
            file_name=f'{session_name}_logs.json',
            mime='application/json', 
            use_container_width=True
        )

    def delete_conversation(self, session_name):
        if len(st.session_state['chats']) == 1:
            st.session_state['chats'][session_name]['logs'] = []
            st.session_state['chats'][session_name]['context_file'] = None
            st.session_state['chats'][session_name]['history'] = None
            st.session_state['chats'][session_name]['timestamp'] = datetime.utcnow().isoformat()
            st.session_state['project'].delete_session(session_name)
            st.session_state.pop(f'file_uploader_{self.idx}', None)
            st.rerun()
        else:
            st.session_state['project'].delete_session(session_name)
            del st.session_state['chats'][session_name]
            st.session_state['project'].rename_sessions()
            self.rename_sessions()
            st.rerun()

    def rename_sessions(self):
        renamed_chats = {}
        for idx, (session_name, session_data) in enumerate(st.session_state['chats'].items(), start=1):
            renamed_chats[f'Session {idx}'] = session_data
        st.session_state['chats'] = renamed_chats
        self.renamed_chats = renamed_chats

    def delete_and_save_buttons(self):
        col1, col2 = st.columns(2)
        with col1:
            delete_button = st.button('Delete Session', key=f'delete_button_{self.idx}', use_container_width=True)
            if delete_button:
                self.delete_conversation(self.name)
                self._prompt_container.warning(f'Deleted Session {self.idx} Data.')
        with col2:
            save_chat = st.button('Save Session', use_container_width=True, key=f'save_chat_{self.idx}')
            if save_chat:
                st.session_state['project'].save_session(session_name=self.name, 
                                                         session_dict=st.session_state['chats'][f'Session {self.idx}'])
                self._prompt_container.success(f'Saved Session {self.idx} Data.')

    def render_messages(self):
        with self._message_container:
            for message in st.session_state['chats'][f'Session {self.idx}']['logs']:
                chat_box = st.chat_message(message['role'])
                chat_box.markdown(message['content'])

    def stream_response(self, response, delay=0.02):
        for chunk in response:
            if answer_chunk := chunk.get('answer'):
                yield f'{answer_chunk}'
                time.sleep(delay)

    def retrieval_qa(self, document):
        history = st.session_state['chats'][f'Session {self.idx}']['history']

        prompt = st.chat_input('Type your message here...', key=f'prompt_input_{self.idx + 1}')
        if prompt:
            with self._message_container.chat_message('user'):
                st.markdown(prompt)
            st.session_state['chats'][f'Session {self.idx}']['logs'].append({'role': 'user', 'content': prompt})

            try:
                rag = CreateRAG(document, openai_api_key=self.openai_api_key)

                if history:
                    rag.store[f'Session {self.idx}'] = history

                conversational_rag_chain = rag.assemble_rag_chain(temperature=self.temperature, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap)
                response = conversational_rag_chain.stream({'input': prompt}, config={'configurable': {'session_id': f'Session {self.idx}'}})

                with self._message_container.chat_message('assistant'):
                    full_response = st.write_stream(self.stream_response(response))

                st.session_state['chats'][f'Session {self.idx}']['logs'].append({'role': 'assistant', 'content': full_response})

                if history is None:
                    history = rag.store[f'Session {self.idx}']

            except Exception as e:
                st.error(f'Error: {e}')

    def render(self):
        logs = st.session_state['chats'][f'Session {self.idx}']['logs']
        document = self.upload_document()
        self.render_messages()

        if document:   
            if self.openai_api_key:
                if self.is_valid_api_key():
                    with self._prompt_container:
                        self.retrieval_qa(document)
                        if len(logs) > 1:
                            self.delete_and_save_buttons()
                            self.download_session_log()
                else:
                    st.error('Invalid API key. Please provide a valid OpenAI API key.')
            else:
                st.warning('Please provide your OpenAI API key.')
        else:
            st.warning('Please upload a file to proceed.')
        st.session_state['chats'][f'Session {self.idx}']

class MainInterface(BaseInterface):
    def __init__(self, openai_api_key=None, chunk_size=None, chunk_overlap=None, temperature=None):
        self.openai_api_key = openai_api_key
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.temperature = temperature

    def cleanup_old_sessions(self):
        project_utilities = ProjectUtilities(f"{st.session_state['user_id']}_Project")
        project_utilities.delete_old_sessions()
        st.success('Old sessions cleaned up successfully.')

    def save_all_sessions(self):
        for session_name, session_data in st.session_state['chats'].items():
            st.session_state['project'].save_session(session_name=session_name, 
                                                     session_dict=session_data)
        st.success('All sessions saved successfully.')

    def add_conversation(self):
        idx = len(st.session_state['chats'].keys()) + 1
        st.session_state['chats'][f'Session {idx}'] = {
            'logs': [], 
            'context_file': None, 
            'history': None,
            'timestamp': datetime.utcnow().isoformat()
        }

    def init_interface(self):
        with st.sidebar:
            AccountInfoComponent().render()
            cols = st.columns(2)
            log_out = st.button('Log Out', use_container_width=True)

            with cols[0]:
                add_new = st.button('➕ New Session', use_container_width=True)
            with cols[1]:
                save_all = st.button('💾 Save All', use_container_width=True)

            if log_out:
                st.session_state['user'] = None
                SessionState.reset()
                st.cache_data.clear()
                st.rerun()
            if save_all:
                self.save_all_sessions()
            if add_new:
                self.add_conversation()

            st.divider()
            self.openai_api_key = st.text_input('OpenAI API Key', type='password')
            with st.expander('**Advanced Settings**'):
                self.models = st.selectbox('Select a Model', ['gpt-3.5-turbo', 'gpt-4o'])
                self.temperature = st.slider('Temperature', 0.0, 1.0, value=0.5)
                self.chunk_size = st.slider('Chunk Size', 100, 2500, value=1000)
                self.chunk_overlap = st.slider('Chunk Overlap', 10, 250, value=50)

    def render(self):
        self.init_interface()
        st.divider()
        chat_session_names = list(st.session_state['chats'].keys())
        tabs = st.tabs(chat_session_names)
        for idx, tab in enumerate(tabs):
            with tab:
                ChatInterface(name=f'{chat_session_names[idx]}', idx=idx + 1, openai_api_key=self.openai_api_key, 
                              temperature=self.temperature, chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap).render()             

class AccountInfoComponent:
    def render(self):
        st.subheader('Account Information')
        with st.container(border = True):
            st.write(f"Logged in as \n\n > 🟢 **{st.session_state['user']}**")
            st.write(f"User ID\n\n > {st.session_state['user_id']}")

class SessionState:
    @staticmethod
    def initialize():
        if 'user' not in st.session_state:
            st.session_state['user'] = None
        if'user_id' not in st.session_state:
            st.session_state['user_id'] = None
        if'chats' not in st.session_state:
            st.session_state['chats'] = {
                'Session 1':{
                    'logs':[], 
                    'context_file':None, 
                    'history':None, 
                    'timestamp':datetime.utcnow().isoformat()
                }
            }
        if'project' not in st.session_state:
            st.session_state['project'] = None
    
    @staticmethod
    def reset():
        st.session_state['user'] = None
        st.session_state['user_id'] = None
        st.session_state['chats'] = {
            'Session 1':{
                'logs':[], 
                'context_file':None, 
                'history':None, 
                'timestamp':None}
        }
        st.session_state['project'] = None