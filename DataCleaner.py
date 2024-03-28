import os
import psycopg2
from datetime import datetime
from bs4 import BeautifulSoup
import re

# Database configuration (update with your credentials)
db_config = {
    'host': 'localhost',
    'database': 'webpages',
    'user': 'postgres',
    'password': 'postgres'
}

# SQL query to insert data into website table
insert_query = '''
    INSERT INTO webpagesTest (Tags, URL, Title, Content, LastUpdated, Domain)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (URL) DO UPDATE SET
    Tags = EXCLUDED.Tags,
    Title = EXCLUDED.Title,
    Content = EXCLUDED.Content,
    LastUpdated = EXCLUDED.LastUpdated,
    Domain = EXCLUDED.Domain;
'''

# SQL query to insert data into media table
media_query = '''
    INSERT INTO media (MediaURL, ParentURL, Type) VALUES (%s, %s, %s)
'''


brokenHTML = []
ignore = ["404", "400", "403", "401", "Page has moved", "Unauthorized", "Forbidden"]
ignorePages = ["_abrandt5","zoom"]


####
# TODO: MAKE THIS BETTER. HOW TO MAKE IT FLEXIBLE FOR ALL WEBSITES?
#       USE AI TO HELP TAG/CLEAN? USE THIS AS BASE/GOAL AND GO FROM THERE?
####

def content_filter(tag):
    # Check if the tag is a 'div'
    if tag.name == "div":
        # Check if 'content' is in the tag's 'id' or 'class'
        has_content_in_id = tag.has_attr('id') and 'content' in tag['id']
        has_content_in_class = tag.has_attr('class') and 'content' in ' '.join(tag['class'])
        has_courseInfo_in_id = tag.has_attr('id') and 'CourseInformationDiv' in tag['id']
        return has_content_in_id or has_content_in_class or has_courseInfo_in_id
    return False  # Not a 'div' or doesn't have 'content' in 'id' or 'class'
    

def clean_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    links = []  # List to store the links
    text_parts = []  # List to store text parts from different divs
    filteredContent = soup.find_all(content_filter)
    # Remove all script and style tags
    for script in soup(["script", "style"]):
        script.extract()

    if(len(filteredContent) > 0):   
        # Iterate through all div elements
        for div in filteredContent:   
            # Extract links and conditionally remove <a> tags
            for a in div.find_all('a'):
                href = a.get('href')
                if href:
                    links.append(href)
                if a.parent.name != 'p':
                    a.decompose()

            # Extract and clean text
            div_text = div.get_text()
            lines = (line.strip() for line in div_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            div_text = '\n'.join(chunk for chunk in chunks if chunk)
            text_parts.append(div_text)

        # Combine all text parts into one string
        combined_text = '\n'.join(text_parts)
        return combined_text, links  # Return the cleaned text and list of links
    
    else:
        # Extract links and remove all <a> tags not within <p> tags
        for a in soup.find_all('a'):
            href = a.get('href')  # Get the href attribute
            if href:
                links.append(href)  # Add the link to the list
            if a.parent.name != 'p':
                a.decompose()  # Remove the <a> tag if not in <p>

        # Extract text
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())  # Break into lines and remove leading/trailing space
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))  # Break multi-headlines into a line
        text = '\n'.join(chunk for chunk in chunks if chunk)  # Drop blank lines
        
        return text, links  # Return both the cleaned text and the list of links

def extract_media_urls(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    media_urls = []

    # Extract image URLs
    for img in soup.find_all('img', src=True):
        media_urls.append(img['src'])

    # Extract URLs for PDFs, PPTs, etc.
    for link in soup.find_all('a', href=True):
        href = link['href']
        if re.search(r'\.(pdf|ppt|pptx)$', href, re.IGNORECASE):
            media_urls.append(href)

    return media_urls


# Now, media_urls contains the URLs of images and specified file types


def process_directory(directory_path, conn):
    count = 0
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf8') as file:
                    """if count > 100:
                        return"""
                    try:
                        html_content = file.read()
                    except:
                        brokenHTML.append(file.name)
                        continue
                    cleaned_text,links = clean_html(html_content)
                    
                    skipFile = False
                    for keyword in ignore:
                        if(keyword in cleaned_text):
                            skipFile = True
                            break

                    if skipFile:
                        continue

                    # Assuming the file name or path as URL, and current timestamp as LastUpdated
                    # Update these values based on your actual data
                    url = file_path
                    # Removing './Western Csd' and replacing double backslashes with single forward slashes
                    cleaned_url = url.replace("./Western Csd\\", "").replace("\\", "/")

                    # Splitting the URL by forward slash and taking the last element
                    file_with_extension = cleaned_url.split("/")[-2:]
                    # Splitting the last element by dot and taking the first part
                    if(len(file_with_extension) > 1):
                        file_name = file_with_extension[0].split(".")[0] + ": " + file_with_extension[1].split(".")[0]
                    else:
                        file_name = file_with_extension[0].split(".")[0]

                    title = file_name
                    if (len(cleaned_text.split("\n")) > 0 and 
                        len(cleaned_text.split("\n")[0]) > 0 and len(cleaned_text.split("\n")[0]) < 1024 and
                        cleaned_text.lstrip().split("\n")[0][0].isupper()):
                        tags = cleaned_text.split("\n")[0]

                    else:
                        tags = " "
    
                    for keyword in ignorePages:
                        if keyword in title:
                            skipFile = True
                            break

                    if skipFile:
                        continue

                    last_updated = datetime.now() # Update this with actual date

                    # Insert data into the website table
                    with conn.cursor() as cursor:
                        cursor.execute(insert_query, (tags, url, title, cleaned_text, last_updated,directory_path))
                        conn.commit()

                    # Insert data into the media table
                    media_urls = extract_media_urls(html_content)
                    for media_url in media_urls:
                        _, media_type = os.path.splitext(media_url)
                        with conn.cursor() as cursor:
                            try:
                                data = (media_url, url, media_type)
                                cursor.execute(media_query,data)
                                conn.commit()
                            except Exception as e:
                                conn.rollback()

                    print(f"Processed and stored: {file_path}")
                    #count += 1

try:
    # Connect to the database
    conn = psycopg2.connect(**db_config)

    # Replace 'path_to_your_directory' with the path to the directory containing the HTML files
    process_directory('./Western Csd',conn)
    #process_directory('./Western Calander',conn)


finally:
    # Close the database connection
    if conn:
        conn.close()
        

