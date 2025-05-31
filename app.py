from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import json

app = Flask(__name__)

def fetch_page_soup(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def extract_json_ld(soup):
    script = soup.find("script", type="application/ld+json")
    if not script:
        print("No JSON-LD script found.")
        return None
    try:
        return json.loads(script.string)
    except json.JSONDecodeError:
        print("Error decoding JSON-LD data.")
        return None

def parse_search_results(search_query):
    base_url = "https://www.coursera.org"
    query = search_query.replace(" ", "%20")
    search_url = f"{base_url}/search?query={query}&sortBy=BEST_MATCH"
    
    soup = fetch_page_soup(search_url)
    if not soup:
        return None
    
    data = extract_json_ld(soup)
    if not data:
        return None
    
    items = data.get("itemListElement", [])
    if not items:
        print("No search results found in JSON-LD")
        return None
    
    first_url = items[0].get("url")
    if not first_url:
        print("First search result has no URL")
        return None
    
    if first_url.startswith("http"):
        return first_url
    else:
        return base_url + first_url

def extract_specialization_data(url):
    soup = fetch_page_soup(url)
    if not soup:
        return None

    ld_json1 = soup.find("script", type="application/ld+json")
    track_skills = []
    if ld_json1:
        try:
            data = json.loads(ld_json1.string)
            for item in data.get("@graph", []):
                if item.get("@type") == "Course":
                    skills = item.get("About", {}).get("name", [])
                    if isinstance(skills, list):
                        track_skills.extend(skills)
                    elif isinstance(skills, str):
                        track_skills.append(skills)
            track_skills = list(set(track_skills))
        except json.JSONDecodeError:
            print("Error decoding JSON-LD on specialization page")
    else:
        print("No JSON-LD script found on specialization page.")

    title_div = soup.find('div', class_='css-1q5srzp')
    track_title = title_div.get_text(strip=True) if title_div else "No Title Found"

    course_info = []
    link_tags = soup.find_all('a', href=True)
    for link_tag in link_tags:
        href = link_tag['href']
        if href.startswith('/learn/'):
            course_name = href.replace("-", " ").replace("/learn/", "").split("?")[0]
            full_url = "https://www.coursera.org" + href
            course_info.append({"Name": course_name, "URL": full_url})

    duration_divs = soup.find_all('div', class_='css-3odziz')
    durations = []
    for div in duration_divs:
        spans = div.find_all('span')
        if len(spans) >= 3:
            hours_text = spans[2].get_text(strip=True)
            durations.append(hours_text)

    for i in range(min(len(course_info), len(durations))):
        course_info[i]['Duration'] = durations[i]
##
    courses_skills = []

    for course in course_info:
        url3 = course["URL"]    
        page3 = requests.get(url3)
        soup3 = BeautifulSoup(page3.text, 'html.parser')
        
        ld_json3 = soup3.find("script", type="application/ld+json")
        
        if ld_json3:
            data = json.loads(ld_json3.string)        
            # If there’s no @graph, wrap the data in a list for easier processing
            graph = data.get("@graph", [data])
            
            found_skills = False
            for item in graph:
                if item.get("@type") == "Course":
                    about_list = item.get("about", [])
                    if about_list:
                        # Save the about list directly
                        courses_skills.append(about_list)
                        found_skills = True
            
            if not found_skills:
                print("No 'about' skills found in this course JSON-LD.")
        else:
            print("No JSON-LD script found.")
    
    

    for i in range(min(len(course_info), len(courses_skills))):
        course_info[i]['Skills'] = courses_skills[i]

##
    course_details = []
    containers = soup.select('.cds-9.css-xalpg1.cds-11.cds-grid-item.cds-56.cds-80')
    for container in containers:
        elements = container.select('.rc-CML p span span')
        for el in elements:
            text = el.get_text(strip=True)
            course_details.append(text)
        else:
            continue
        break
    course_details = [item for item in course_details if item.strip() != '']
    Track = {
        "Name": track_title,
        "URL": url,
        "Details": course_details,
        "Skills": track_skills,
        "Courses": course_info
    }

    return Track

@app.route('/api/track', methods=['GET'])
def get_track():
    search_query = request.args.get('search_query')
    if not search_query:
        return jsonify({"error": "Missing required parameter: search_query"}), 400
    
    track_url = parse_search_results(search_query)
    if not track_url:
        return jsonify({"error": "Failed to find specialization URL for the query"}), 404

    track_data = extract_specialization_data(track_url)
    if not track_data:
        return jsonify({"error": "Failed to extract track data"}), 500

    return jsonify(track_data)

if __name__ == '__main__':
    app.run(debug=True)