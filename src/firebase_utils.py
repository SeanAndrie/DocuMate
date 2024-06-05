import json
import pickle
import tempfile
from datetime import datetime, timedelta
from firebase_admin import storage

class ProjectUtilities:
    def __init__(self, project_name):
        self.project_name = project_name
        self.bucket = storage.bucket()
        self.project_folder_path = f'{project_name}/'
        self.chat_hist_path = f'{project_name}/chat_history/'
        self.sessions_list = self._list_sessions()

    def _list_sessions(self):
        return sorted(set([blob.name.split('/')[-2] for blob in self.bucket.list_blobs(prefix=self.chat_hist_path)][1:]))

    def get_sessions_data(self):
        return {
            session_name.split('.')[0]: {
                'logs': self._get_file_data(session_name, '_logs.json', json.load),
                'context_file': self._get_file_data(session_name, '_context.pkl', pickle.load),
                'history': self._get_file_data(session_name, '_history.pkl', pickle.load),
                'timestamp': self._get_file_data(session_name, '_timestamp.json', json.load)
            }
            for session_name in self.sessions_list
        }

    def _get_file_data(self, session_name, file_suffix, load_func):
        session_folder_path = f"{self.chat_hist_path}{session_name.split('.')[0]}"
        blobs = self.bucket.list_blobs(prefix=session_folder_path)

        file_blob = next((blob for blob in blobs if blob.name.endswith(file_suffix)), None)

        if not file_blob:
            raise FileNotFoundError(f'No {file_suffix} file found for session {session_name}.')

        file_name = file_blob.name.split('/')[-1]
        file_extension = file_name.split('.')[-1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
            file_blob.download_to_filename(temp_file.name)
            
            with open(temp_file.name, 'rb') as file:
                data = load_func(file)

        return data 

    def create_project_folder(self):
        content_type = 'application/x-www-form-urlencoded;charset=UTF-8'
        project_folder_blob = self.bucket.blob(self.project_folder_path)
        chat_hist_blob = self.bucket.blob(self.chat_hist_path)

        project_folder_blob.upload_from_string('', content_type=content_type)
        chat_hist_blob.upload_from_string('', content_type=content_type)

        print(f'Created {self.project_name} folder.')

    def save_session(self, session_name, session_dict):
        path = f'{self.project_name}/chat_history/{session_name}'
        session_logs, session_context_file, session_history, session_timestamp = session_dict.values()

        print(session_timestamp)

        self._upload_file(f'{path}/{session_name}_logs.json', json.dumps(session_logs), 'application/json')
        self._upload_file(f'{path}/{session_name}_context.pkl', pickle.dumps(session_context_file), 'application/octet_stream')
        self._upload_file(f'{path}/{session_name}_history.pkl', pickle.dumps(session_history), 'application/octet-stream')
        self._upload_file(f'{path}/{session_name}_timestamp.json', json.dumps({'timestamp': session_timestamp}), 'application/json')

        print(f"Session data for '{session_name}' uploaded successfully to Firebase Storage.")

    def _upload_file(self, file_path, data, content_type):
        blob = self.bucket.blob(file_path)
        blob.upload_from_string(data, content_type=content_type)     
    
    def delete_session(self, session_name):
        session_folder_path = f"{self.chat_hist_path}{session_name}"
        blobs = self.bucket.list_blobs(prefix=session_folder_path)

        for blob in blobs:
            blob.delete()

        print(f"'{session_name}' deleted successfully from Firebase Storage.")
        self.sessions_list = self._list_sessions()
    
    def rename_sessions(self):
        sessions = self.sessions_list

        for idx, session_name in enumerate(sessions, start=1):
            old_session_folder_path = f"{self.chat_hist_path}{session_name}"
            new_session_folder_path = f"{self.chat_hist_path}Session {idx}"

            blobs = self.bucket.list_blobs(prefix=old_session_folder_path)

            for blob in blobs:
                new_blob_name = blob.name.replace(old_session_folder_path, new_session_folder_path)
                self.bucket.rename_blob(blob, new_blob_name)

            print(f"Session '{session_name}' renamed to 'Session {idx}' in Firebase Storage.")

        self.sessions_list = self._get_session_list()
        
    def delete_old_sessions(self):
        sessions_data = self.get_sessions_data()
        current_time = datetime.utcnow()
        threshold_time = current_time - timedelta(days=30)

        for session_name, session_data in sessions_data.items():
            session_timestamp = datetime.fromisoformat(session_data['timestamp']['timestamp']['timestamp']) # What the hell 😭
            if session_timestamp < threshold_time:
                self.delete_session(session_name)
                print(f"Deleted session '{session_name}' due to exceeding 30 days.")