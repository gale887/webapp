from flask import Flask, render_template, request, json, redirect, url_for
import requests
from fuzzywuzzy import fuzz, process

app = Flask(__name__)

with open('country-capital.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

countryCapital = {}

for entry in data:
    countryCapital[entry["country"].lower()] = entry["capital"]

# Cache for all countries to avoid repeated API calls
all_countries_cache = None

def get_all_countries():
    """Get all countries from REST Countries API with caching"""
    global all_countries_cache
    
    if all_countries_cache is not None:
        return all_countries_cache
    
    try:
        url = "https://restcountries.com/v3.1/all"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            all_countries_cache = [country['name']['common'] for country in data]
            return all_countries_cache
        else:
            return []
    except requests.RequestException:
        return []

def validate_country(country_name):
    """Validate if a country exists using REST Countries API"""
    try:
        url = f"https://restcountries.com/v3.1/name/{country_name}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return True, data[0]['name']['common'], None  # Return standardized name
        else:
            return False, None, None
    except requests.RequestException:
        return False, None, None

def find_similar_countries(country_name, threshold=50):
    """Find similar countries using fuzzy matching from online API"""
    all_countries = get_all_countries()
    if not all_countries:
        return []
    
    # Use fuzzy matching to find similar countries
    matches = process.extract(country_name, all_countries, scorer=fuzz.ratio, limit=5)
    
    # Filter matches above threshold
    similar_countries = [match for match in matches if match[1] >= threshold]
    
    return similar_countries

def find_similar_local_countries(country_name, threshold=60):
    """Find similar countries in our local database using fuzzy matching"""
    local_countries = list(countryCapital.keys())
    if not local_countries:
        return []
    
    # Use fuzzy matching to find similar countries
    matches = process.extract(country_name, local_countries, scorer=fuzz.ratio, limit=5)
    
    # Filter matches above threshold and convert back to proper case
    similar_countries = []
    for match, score in matches:
        if score >= threshold:
            # Convert back to proper case for display
            proper_case = match.capitalize()
            similar_countries.append((proper_case, score))
    
    return similar_countries

@app.route('/')
def index():
    return render_template("index.html")

@app.route("/capital", methods=['POST'])
def capital():
    country = request.form['city'].lower()
    city = countryCapital.get(country)
    
    if city is not None:
        return render_template("success.html", country=country.capitalize(), city=city)
    else:
        # Check for similar countries in our local database first
        local_suggestions = find_similar_local_countries(country)
        if local_suggestions:
            return render_template("suggestions.html", 
                                 country=country.capitalize(), 
                                 suggestions=local_suggestions,
                                 city="")
        else:
            return render_template("unknown.html", country=country.capitalize(), city="")

@app.route("/ask", methods=['POST'])
def ask():
    country = request.form['country'].lower()
    city = request.form['city']
    return render_template("success.html", country=country.capitalize(), city=city)

@app.route("/select_local", methods=['POST'])
def select_local():
    """Handle when user selects a suggested country from local database"""
    country = request.form['country'].lower()
    city = countryCapital.get(country)
    
    if city:
        return render_template("success.html", country=country.capitalize(), city=city)
    else:
        return render_template("unknown.html", country=country.capitalize(), city="")

@app.route("/save", methods=["POST"])
def save():
    country = request.form['country'].strip()
    city = request.form['city'].strip()
    
    # Validate the country exists
    is_valid, standardized_name, _ = validate_country(country)
    
    if not is_valid:
        # Find similar countries
        similar_countries = find_similar_countries(country)
        if similar_countries:
            return render_template("suggestions.html", 
                                 country=country.capitalize(), 
                                 suggestions=similar_countries,
                                 city=city)
        else:
            return render_template("invalid_country.html", country=country.capitalize())
    
    # Use the standardized country name from the API
    country = standardized_name
    city = city.capitalize()
    
    countcap = {"country": country, "capital": city, "type": "countryCapital"}
    with open('country-capital.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.append(countcap)
    with open('country-capital.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    # Update the in-memory dictionary
    countryCapital[country.lower()] = city
    
    return render_template("success.html", country=country, city=city)

@app.route("/confirm_country", methods=["POST"])
def confirm_country():
    """Handle when user selects a suggested country"""
    country = request.form['country'].strip()
    city = request.form['city'].strip()
    
    # Validate the selected country
    is_valid, standardized_name, _ = validate_country(country)
    
    if is_valid:
        country = standardized_name
        city = city.capitalize()
        
        countcap = {"country": country, "capital": city, "type": "countryCapital"}
        with open('country-capital.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        data.append(countcap)
        with open('country-capital.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        
        # Update the in-memory dictionary
        countryCapital[country.lower()] = city
        
        return render_template("success.html", country=country, city=city)
    else:
        return render_template("invalid_country.html", country=country.capitalize())

if __name__ == '__main__':
    app.run(debug=True, port=5001)