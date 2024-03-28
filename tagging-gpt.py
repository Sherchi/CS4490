from dotenv import load_dotenv
from openai import OpenAI
import os
import psycopg2
import time
load_dotenv()

# Database configuration (update with your credentials)
db_config = {
    'host': 'localhost',
    'database': 'webpages',
    'user': 'postgres',
    'password': 'postgres'
}


client = OpenAI(api_key=os.getenv("GPT_API_KEY"))

def tag_item(item_text, model="gpt-4-turbo-preview"):
    prompt = """Tag/Categorize the given text with at most 10 different tags that MUST seperated by a comma.
    Prioritize Strings that may be Names or Course Codes as a tag.
    The Maximum length of each tag is 50 characters.
    The Maximum combined length is 512 Chars. If it is longer then remove a tag.
    The english text is: {input}
    """.format(input=item_text)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )
    return completion.choices[0].message.content


if __name__ == "__main__":
    try:
    # Connect to the database
        conn = psycopg2.connect(**db_config)
        cur = conn.cursor()

        # Assuming 'id' is the primary key column and 'tags' is the column to update
        cur.execute("SELECT pageid, content, tags FROM webpagestest")  # Only select columns you need

        rows = cur.fetchall()

        for row in rows:
            item_id, content, tags = row  # Unpack the row
            max_token_length = 16385  # Set maximum token length 

            # Check if content exceeds max token length
            if content == "":
                continue
            elif len(content) > max_token_length * 2:
                print(f"Content with ID {item_id} exceeds max token length. Handling...")
                new_tag = tag_item(content[1:max_token_length])
                if tags != " " and tags not in new_tag:
                    new_tag = tags + "," + new_tag
                print("HERE")
            else:
                new_tag = tag_item(content)  # Generate the tag for the content
                if tags != " " and tags not in new_tag:
                    new_tag = tags + "," + new_tag

            # Update the 'tags' column for the row with the specified 'id'
            while len(new_tag) > 1024:
                new_tag = new_tag.rsplit(",", 1)[0]  

            # cur.execute("UPDATE webpagestest SET tags = %s WHERE pageid = %s", (new_tag.lower(), item_id))
            print("Finished item " + str(item_id))
        conn.commit()  # Commit the transaction to save changes

    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()  # Rollback in case of error

    finally:
        cur.close()
        conn.close()  # Ensure the connection is closed
            