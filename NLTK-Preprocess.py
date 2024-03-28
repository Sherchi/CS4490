import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from gensim.models import Word2Vec
import pickle
import psycopg2

# Database configuration (update with your credentials)
db_config = {
    'host': 'localhost',
    'database': 'webpages',
    'user': 'postgres',
    'password': 'postgres'
}

def save_tokenized_data(tokenized_data, file_path):
    with open(file_path, 'wb') as file:
        pickle.dump(tokenized_data, file)


def getData():
    documents = []  # List to hold dictionaries with pageid, tokenized content, and original content
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Execute your query
        cur.execute("SELECT pageid, content, tags FROM webpagestest")

        rows = cur.fetchall()
        stop_words = set(stopwords.words('english'))

        for row in rows:
            pageid, content, _ = row  # Assuming we don't need tags here
            # Tokenize the entire content of the document into words, removing stopwords
            word_tokens = word_tokenize(content)
            cleaned_tokens = [word.lower() for word in word_tokens if word.isalnum() and word.lower() not in stop_words and len(word) > 3]
            if cleaned_tokens:
                documents.append({
                    'pageid': pageid,
                    'tokens': cleaned_tokens,
                    'original_content': content
                })

    except Exception as e:
        print(e)
    finally:
        cur.close()
        conn.close()

    return documents


def train_word2vec_model(tokenized_sentences):
    # Train the Word2Vec model on the tokenized content
    model = Word2Vec(tokenized_sentences, vector_size=500, window=5, min_count=1, workers=4)
    
    # Save the trained model
    model.save("word2vec_model.model")
    return model



def save_original_docs(original_docs, file_path):
    with open(file_path, 'wb') as file:
        pickle.dump(original_docs, file)


if __name__ == "__main__":
    nltk.download('punkt')  # Ensure the tokenizer model is downloaded
    nltk.download('stopwords')  # Ensure the stopwords are downloaded

    # Fetch documents (each containing pageid, tokens, and original content)
    documents = getData()
    
    # Extract just the tokenized content for training
    tokenized_sentences = [doc['tokens'] for doc in documents]

    # Train Word2Vec model using the tokenized sentences
    model = train_word2vec_model(tokenized_sentences)

    # Save the entire documents list for later use
    save_tokenized_data(documents, "documents.pkl")

    # Example of how to use the model
    if 'example' in model.wv:
        similar_words = model.wv.most_similar('example', topn=5)
        print(similar_words)
    else:
        print("'example' not in vocabulary")


