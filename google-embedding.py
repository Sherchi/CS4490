import pandas as pd
import numpy as np
from dotenv import load_dotenv
from scipy.spatial.distance import cosine
import time
from google.cloud import aiplatform
from vertexai.language_models import TextEmbeddingModel
from vertexai.language_models import TextGenerationModel

load_dotenv()

def init():
    aiplatform.init(
        project= 'dliao-thesis',
        experiment='my-experiment',
    )

df=pd.read_csv('processed/google_embeddings.csv', index_col=0)
df['embeddings'] = df['embeddings'].apply(eval).apply(np.array)

df.head()
init()
model = TextEmbeddingModel.from_pretrained("textembedding-gecko@001")

def create_context(
    question, df, max_len=18000,
):
    """
    Create a context for a question by finding the most similar context from the dataframe
    """
    
    q_embeddings = model.get_embeddings([question])[0].values

    # Get the distances from the embeddings
    df['distances'] = df['embeddings'].apply(lambda emb: cosine(q_embeddings, emb))

    returns = []
    cur_len = 0

    # Sort by distance and add the text to the context until the context is too long
    for i, row in df.sort_values('distances', ascending=True).iterrows():
        # Add the length of the text to the current length
        cur_len += row['n_tokens'] + 4

        # If the context is too long, break
        if cur_len > max_len:
            break

        # Else add it to the text that is being returned
        returns.append(row["text"])

    # Return the context
    return "\n\n###\n\n".join(returns)

def answer_question(
    df,
    question='test',
    max_len=1800,
):
    context = create_context(
        question,
        df,
        max_len=max_len,
    )

    # TODO developer - override these parameters as needed:
    parameters = {
        "max_output_tokens": 500,  # Token limit determines the maximum amount of text output.
    }
    model = TextGenerationModel.from_pretrained("text-bison@002")
    response = model.predict(
        f"Answer the question based on the context below, and if the question can't be answered based on the context, say 'I don't know'\nContext: {context}\n\n---\n\nQuestion: {question}\nAnswer:",
        **parameters,
    )
    return response.text
    
if __name__ == "__main__":
    while(True):
        user_input = input("\nPlease enter your prompt: ")
        start_time = time.time()
        print(answer_question(df, question=user_input))
        end_time = time.time()

        print(end_time - start_time)
