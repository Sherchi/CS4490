from openai import OpenAI
import pandas as pd
import numpy as np
import os
from dotenv import load_dotenv
from scipy.spatial.distance import cosine
import time

load_dotenv()

client = OpenAI(api_key=os.getenv("GPT_API_KEY"))

df=pd.read_csv('processed/embeddings.csv', index_col=0)
df['embeddings'] = df['embeddings'].apply(eval).apply(np.array)

df.head()

def create_context(
    question, df, max_len=18000, size="ada"
):
    """
    Create a context for a question by finding the most similar context from the dataframe
    """
    
    q_embeddings = client.embeddings.create(input=question, model='text-embedding-ada-002').data[0].embedding

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
    model="gpt-4-turbo-preview",
    question="test",
    max_len=1800,
    size="ada",
    debug=False,
    max_tokens=1500,
    stop_sequence=None
):
    """
    Answer a question based on the most similar context from the dataframe texts
    """
    context = create_context(
        question,
        df,
        max_len=max_len,
        size=size,
    )
    # If debug, print the raw model response
    if debug:
        print("Context:\n" + context)
        print("\n\n")

    try:
        # Create a chat completion using the question and context
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "Answer the question based on the context below, and if the question can't be answered based on the context, say 'I don't know' "},
                {"role": "user", "content": f"Context: {context}\n\n---\n\nQuestion: {question}\nAnswer:"}
            ],
            temperature=0,
            max_tokens=max_tokens,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0,
            stop=stop_sequence,
        )
        return response.choices[0].message.content
    
    except Exception as e:
        print(e)
        return ""
    
if __name__ == "__main__":
    while(True):
        user_input = input("\nPlease enter your prompt: ")
        start_time = time.time()
        print(answer_question(df, question=user_input))
        end_time = time.time()

        print(end_time - start_time)
