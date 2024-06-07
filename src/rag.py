import streamlit as st
from PyPDF2 import PdfReader
from docx import Document

from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import create_retrieval_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains import create_history_aware_retriever
from langchain_core.prompts import MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory

class CreateRAG:
    def __init__(self, document, openai_api_key = None, debug = False):
        self.openai_api_key = st.secrets['OPENAI_API_KEY'] if debug else openai_api_key
        
        self.system_prompt = (
            "You are an advanced Retrieval-Augmented Generation (RAG) chatbot designed to assist users "
            "by answering their questions with detailed and accurate information based on the contents of a provided file. "
            "Use the following pieces of retrieved context to answer the question. Ensure your responses are detailed, "
            "well-supported by the data in the file, and logically organized. If you don't know the answer, say that you don't know. "
            "Use structured responses, including paragraphs, bullet points, or numbered lists where appropriate. "
            "Provide detailed explanations, including relevant examples, definitions, and context from the file to enhance understanding. "
            "Maintain a polite and professional tone throughout your interactions. Be concise but thorough in your responses. "
            "If provided with questions related to coding, carefully analyze the question to identify the specific programming problem or task."
            "Provide a clear, concise, and detailed explanation of the solution or approach to solve the problem. Break down the explanation into logical steps or components if necessary."
            "\n\n"
            "{context}"
        )

        self.contextualize_q_system_prompt = (
            "Given a chat history and the latest user question "
            "which might reference context in the chat history, "
            "formulate a standalone question which can be understood "
            "without the chat history. Do NOT answer the question, "
            "just reformulate it if needed and otherwise return it as is."
        )
        
        self.store = {}
        self.document = document

    def extract_text_from_document(self):
        text = ''
        file_extension = self.document.name.split('.')[-1].lower()
        file_data = self.document

        try:
            if file_extension == 'pdf':
                pdf_reader = PdfReader(file_data)
                for page in pdf_reader.pages:
                    text += page.extract_text() or ""

            elif file_extension == 'docx':
                try:
                    document = Document(file_data)
                    for paragraph in document.paragraphs:
                        text += paragraph.text + '\n'
                except Exception as e:
                    raise ValueError(f"Error processing DOCX file: {e}")

            elif file_extension == 'txt':
                text = file_data.getvalue().decode('utf-8')

            else:
                raise ValueError(f'Unsupported file format: {file_extension}')

        except Exception as e:
            print(f"Error reading {file_extension} file: {e}")
            raise

        if not text.strip():
            raise ValueError(f"The file {self.document.name} seems to be empty or could not be read properly.")

        return text
    
    def get_retriever(self, embeddings, chunk_size, chunk_overlap):
        doc_text = self.extract_text_from_document()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.split_text(doc_text)

        vectorstore = FAISS.from_texts(chunks, embeddings)
        retriever = vectorstore.as_retriever()

        return retriever
    
    def get_session_history(self, session_id):
        if session_id not in self.store:
            self.store[session_id] = ChatMessageHistory()
        return self.store[session_id]
    
    def create_embeddings(self):
        return OpenAIEmbeddings(openai_api_key=self.openai_api_key)
    
    def get_model(self, temperature):
        return ChatOpenAI(temperature=temperature, api_key=self.openai_api_key)
    
    def assemble_rag_chain(self, temperature, chunk_size, chunk_overlap):
        embeddings = self.create_embeddings()
        retriever = self.get_retriever(embeddings, chunk_size = chunk_size, chunk_overlap = chunk_overlap)
        model = self.get_model(temperature=temperature)
        
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                ('system', self.contextualize_q_system_prompt), 
                MessagesPlaceholder('chat_history'),
                ('human', '{input}'),
            ]
        )

        history_aware_retriever = create_history_aware_retriever(
            model, retriever, contextualize_q_prompt
        )

        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ('system', self.system_prompt), 
                MessagesPlaceholder('chat_history'), 
                ('human', '{input}'),
            ]
        )

        qa_chain = create_stuff_documents_chain(model, qa_prompt)
        rag_chain = create_retrieval_chain(history_aware_retriever, qa_chain)
        
        conversational_rag_chain = RunnableWithMessageHistory(
            rag_chain, 
            self.get_session_history, 
            input_messages_key='input', 
            history_messages_key='chat_history', 
            output_messages_key='answer'
        ) 

        return conversational_rag_chain
