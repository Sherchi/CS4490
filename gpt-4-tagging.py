from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
import time
import random
import concurrent
from concurrent.futures import ThreadPoolExecutor
load_dotenv()

client = OpenAI(api_key=os.getenv("GPT_API_KEY"))
TOKEN_LENGTH = int(os.getenv("GPT_MAX_TOKEN"))
TPM = int(os.getenv("GPT_TOKEN_PER_MIN"))

objLimit = 30

db_config = {
    'host': 'localhost',
    'database': 'webpages',
    'user': 'postgres',
    'password': 'postgres'
}

def get_query(user_message, model="gpt-3.5-turbo"):
    tagAmount = int(len(user_message)/100) + 2
    prompt = """Tag/Categorize the given text with at most {tagNum} different tags,
    Prioritize content that may be a Course Code as a tag.(ie. cs1000) The tags cannot exceed 50 Characters, are lower case, and non-plural.
    Do not show the tags.
    With these tags, create an SQL query that selects all from the a table ONLY through the tags.
    The general format is: "SELECT * FROM webpagestest WHERE Tags LIKE '%TAGHERE%' OR Tags like '%OTHER TAG HERE%';"
    Have the conditionals be combined by "OR".

    The given text is: {input}
    """.format(input=user_message, tagNum = tagAmount)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a machine that only prints out SQL queries"},
            {"role": "user", "content": prompt}
        ],
    )
    return completion.choices[0].message.content

def retrieve_data(query):
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()
        #This code was to account for GPT-4.0 adding in formatting while GPT-3.5 did not
        try:
            query = query.lower().split('\n')
            query = query[1]
        except:
            query = query[0]
        cur.execute(query) 

        rows = cur.fetchall()
        return rows


    finally:
        # Close the database connection
        if conn:
            conn.close()

def get_response(data,query, model = "gpt-4-turbo-preview"):
    prompt ="""ONLY using the given information, answer the the given question with some detail.
    Consider the given information real-time data.
    If you cannot find the answer inside the given information, reply with 'I don't know'
    Try to exclude Information from before 2020 if possible, if not, then include the data.
    If Possible, link a website related to the answer.
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

if __name__ == "__main__":
    responses = []

    while True:
        user_input = input("Please enter your prompt: ")
        start_time = time.time()
        query = get_query(user_input)
        data = retrieve_data(query.lower())

        if len(data) > objLimit:
            data = random.sample(data, objLimit)

        content = [dataObj[6] for dataObj in data]
        content = split_by_char_limit(content, int(TOKEN_LENGTH *2/5))

        if(len(content) < 1):
            print("Bad Query")
            continue


        # Using ThreadPoolExecutor to manage a pool of threads
        with ThreadPoolExecutor() as executor:
            # Create a list of tasks for the executor
            # Each task is a call to get_response_wrapper with a row and the user_input
            tasks = [executor.submit(get_response_wrapper, row, user_input) for row in content[0]]
            # As tasks complete, their results are added to the 'responses' list
            for future in concurrent.futures.as_completed(tasks):
                responses.append(future.result())
                
        # Now 'responses' contains all the responses
        allInfo = "\n".join(responses)


        if(len(responses) > 0):
            print(get_response(allInfo,user_input))
        end_time = time.time()

        print(end_time - start_time)
