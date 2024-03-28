import pickle
from gensim.models import Word2Vec
from nltk.tokenize import word_tokenize
import numpy as np
from scipy import spatial
from openai import OpenAI
from dotenv import load_dotenv
import time
import os
import concurrent
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

client = OpenAI(api_key=os.getenv("GPT_API_KEY"))
objLimit = 20
TOKEN_LENGTH = int(os.getenv("GPT_MAX_TOKEN"))

# Load the pre-trained Word2Vec model
def load_model(model_path):
    return Word2Vec.load(model_path)

# Load the tokenized data
def load_tokenized_data(data_path):
    with open(data_path, 'rb') as file:
        return pickle.load(file)
    
# Load the original documents
def load_original_docs(docs_path):
    with open(docs_path, 'rb') as file:
        return pickle.load(file)


# Vectorize the text using the Word2Vec model
def vectorize_text(model, text_tokens):
    tokens = [token for token in text_tokens if token in model.wv]
    if tokens:
        return np.mean([model.wv[token] for token in tokens], axis=0)
    else:
        return None
    
# Find the most similar documents to the user input
def find_similar_documents(input_vector, documents, model):
    similarities = []
    for document in documents:
        tokens = document['tokens']  # Extract tokens from each document dictionary
        doc_vector = vectorize_text(model, tokens)
        if doc_vector is not None:
            similarity = 1 - spatial.distance.cosine(input_vector, doc_vector)
            similarities.append(similarity)
        else:
            similarities.append(-1)  # Low similarity for non-vectorized documents

    # Sort documents by similarity
    sorted_docs_indices = np.argsort(similarities)[::-1]
    return sorted_docs_indices, similarities

def get_response(data,query, model = "gpt-3.5-turbo"):    
    prompt ="""ONLY using the given context, answer the the given question with some detail.
    Consider the given information real-time data.
    If you cannot find the answer inside the given context, reply with 'I don't know'.
    I must re-iterate, ONLY USE the given information below.
    Information = {userData}
    Question = {userQuery}
    """.format(userData = data, userQuery = query)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content":"You are a system that looks up data related to Western University"},
            {"role": "user", "content": prompt}
        ],
    )
    return completion.choices[0].message.content

def split_by_char_limit(s, limit):
    return [s[i:i+limit] for i in range(0, len(s), limit)]

# This function will be executed by a thread in the thread pool
def get_response_wrapper(row, user_input):
    if len(row) > TOKEN_LENGTH:
        row = row[:int(TOKEN_LENGTH*2/5)]
    # Get the response and return it
    return get_response(row, user_input)

def main():
    model_path = "word2vec_model.model"
    documents_path = "documents.pkl"  # Adjusted to the new filename for clarity

    # Load model and the full documents list
    model = load_model(model_path)
    documents = load_tokenized_data(documents_path)  # Now loading the full documents
    # Take user input
    counter = 0

    while(True):
        user_input = input("Enter your query: ")
        start_time = time.time()

        input_tokens = word_tokenize(user_input.lower())

        # Vectorize user input
        input_vector = vectorize_text(model, input_tokens)

        if input_vector is not None:
            # Find similar documents
            similar_docs_indices, similarities = find_similar_documents(input_vector, documents, model)

            # Display top 5 similar documents
            print("Top 10 similar documents:")
            allText = ''
            doc_limit = 20
            for i in range(doc_limit):
                if i < len(similar_docs_indices):
                    doc_index = similar_docs_indices[i]
                    # Fetch the original document text and pageid using the index
                    document = documents[doc_index]  # Fetch the document dictionary
                    document_text = document['original_content']
                    allText += document_text
                else:
                    break

            if(len(allText) < 1):
                print("Bad Query")
                continue

            if(len(allText) > TOKEN_LENGTH *2/5):
                allText = split_by_char_limit(allText,int(TOKEN_LENGTH *2/5))

            responses = []
            # Using ThreadPoolExecutor to manage a pool of threads
            with ThreadPoolExecutor() as executor:
                # Create a list of tasks for the executor
                # Each task is a call to get_response_wrapper with a row and the user_input
                tasks = [executor.submit(get_response_wrapper, row, user_input) for row in allText]
                # As tasks complete, their results are added to the 'responses' list
                for future in concurrent.futures.as_completed(tasks):
                    responses.append(future.result())
                if(counter > 21):
                    print("HERE: " + str(counter))
                    break
                    

            # Now 'responses' contains all the responses

            allInfo = "\n".join(responses)

            if(len(responses) > 0):
                print(get_response(allInfo,user_input))

        else:
            print("User input could not be vectorized.")

        end_time = time.time()
        print(end_time - start_time)


if __name__ == "__main__":
    main()
