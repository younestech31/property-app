import json
import os
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)

# Paths to data
SALE_DIR = 'static/data/sale'
RENT_DIR = 'static/data/rent'

def load_json_files(directory):
    data_dict = {}
    if not os.path.exists(directory):
        return data_dict
    for filename in os.listdir(directory):
        if filename.endswith('.json'):
            filepath = os.path.join(directory, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Extract a clean wilaya name from the JSON's "wilaya" field
                raw_wilaya = data.get('wilaya', '')
                # Remove "Wilaya d'" or "Wilaya de " prefix, keep only the name
                clean_wilaya = raw_wilaya.replace('Wilaya d\'', '').replace('Wilaya de ', '').replace('Wilaya ', '')
                # If still empty, fall back to filename without extension
                if not clean_wilaya:
                    clean_wilaya = os.path.splitext(filename)[0]
                # Use the clean name as key
                data_dict[clean_wilaya] = data
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
    return data_dict

# Load all sale and rent data
sale_data = load_json_files(SALE_DIR)
rent_data = load_json_files(RENT_DIR)

def get_data(wilaya, transaction_type):
    if transaction_type == 'sale':
        return sale_data.get(wilaya)
    else:
        return rent_data.get(wilaya)

def get_communes(wilaya, transaction_type):
    data = get_data(wilaya, transaction_type)
    if not data:
        return []
    return list(data['communes'].keys())

def get_property_types(wilaya, transaction_type, commune):
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return []
    return list(data['communes'][commune]['data'].keys())

def get_categories(wilaya, transaction_type, commune, property_type):
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return []
    if property_type not in data['communes'][commune]['data']:
        return []
    return list(data['communes'][commune]['data'][property_type].keys())

def get_zones(wilaya, transaction_type, commune, property_type, category):
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return []
    if property_type not in data['communes'][commune]['data']:
        return []
    if category not in data['communes'][commune]['data'][property_type]:
        return []
    zones = data['communes'][commune]['data'][property_type][category]
    return [z for z in zones if zones[z] is not None and isinstance(zones[z], list) and len(zones[z]) == 2]

def get_price_range(wilaya, transaction_type, commune, property_type, category, zone):
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return None
    if property_type not in data['communes'][commune]['data']:
        return None
    if category not in data['communes'][commune]['data'][property_type]:
        return None
    zone_data = data['communes'][commune]['data'][property_type][category].get(zone)
    if not zone_data or len(zone_data) != 2:
        return None
    return zone_data[0], zone_data[1]

def is_agricultural(property_type):
    return "Agricoles" in property_type

def get_commune_description(wilaya, transaction_type, commune):
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return ''
    return data['communes'][commune].get('description', '')

# Endpoints
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ads.txt')
def ads_txt():
    return send_from_directory('.', 'ads.txt', mimetype='text/plain')

@app.route('/api/wilayas')
def api_wilayas():
    # Return sorted list of available wilayas (union of sale and rent)
    all_wilayas = set(sale_data.keys()) | set(rent_data.keys())
    return jsonify(sorted(list(all_wilayas)))

@app.route('/api/communes')
def api_communes():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    if not wilaya or wilaya not in get_data(wilaya, transaction_type):
        return jsonify([])
    communes = get_communes(wilaya, transaction_type)
    return jsonify(communes)

@app.route('/api/commune_description')
def api_commune_description():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    commune = request.args.get('commune')
    if not wilaya or not commune:
        return jsonify({'description': ''})
    desc = get_commune_description(wilaya, transaction_type, commune)
    return jsonify({'description': desc})

@app.route('/api/property_types')
def api_property_types():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    commune = request.args.get('commune')
    if not wilaya or not commune:
        return jsonify([])
    types = get_property_types(wilaya, transaction_type, commune)
    return jsonify(types)

@app.route('/api/categories')
def api_categories():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    commune = request.args.get('commune')
    property_type = request.args.get('property_type')
    if not wilaya or not commune or not property_type:
        return jsonify([])
    categories = get_categories(wilaya, transaction_type, commune, property_type)
    return jsonify(categories)

@app.route('/api/zones')
def api_zones():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    commune = request.args.get('commune')
    property_type = request.args.get('property_type')
    category = request.args.get('category')
    if not wilaya or not commune or not property_type or not category:
        return jsonify([])
    zones = get_zones(wilaya, transaction_type, commune, property_type, category)
    return jsonify(zones)

@app.route('/api/price', methods=['POST'])
def api_price():
    data = request.get_json()
    wilaya = data.get('wilaya')
    transaction_type = data.get('transaction_type', 'sale')
    commune = data.get('commune')
    property_type = data.get('property_type')
    category = data.get('category')
    zone = data.get('zone')
    surface = data.get('surface')

    if not all([wilaya, commune, property_type, category, zone, surface]):
        return jsonify({'error': 'Missing parameters'}), 400

    try:
        surface = float(surface)
        if surface <= 0:
            return jsonify({'error': 'Surface must be positive'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid surface'}), 400

    price_range = get_price_range(wilaya, transaction_type, commune, property_type, category, zone)
    if not price_range:
        return jsonify({'error': 'No price data for this combination'}), 404

    min_price, max_price = price_range

    if is_agricultural(property_type):
        hectares = surface / 10000.0
        min_total = min_price * hectares
        max_total = max_price * hectares
        unit_per = "DA/Ha"
        note = "Prix par hectare, surface convertie automatiquement."
    else:
        min_total = min_price * surface
        max_total = max_price * surface
        unit_per = "DA/m²"
        note = ""

    if transaction_type == 'rent':
        unit_label = "DA/mois"
    else:
        unit_label = "DA"

    return jsonify({
        'min': round(min_total, 2),
        'max': round(max_total, 2),
        'unit': unit_label,
        'unit_per': unit_per,
        'min_per_unit': min_price,
        'max_per_unit': max_price,
        'note': note
    })

@app.route('/api/debug')
def debug():
    wilaya = request.args.get('wilaya')
    transaction_type = request.args.get('transaction_type', 'sale')
    commune = request.args.get('commune')
    property_type = request.args.get('property_type')
    category = request.args.get('category')
    
    data = get_data(wilaya, transaction_type)
    if not data or commune not in data['communes']:
        return jsonify({'error': 'Commune not found'}), 404
    commune_data = data['communes'][commune]['data']
    
    if property_type:
        if property_type not in commune_data:
            return jsonify({'error': 'Property type not found'}), 404
        if category:
            if category not in commune_data[property_type]:
                return jsonify({'error': 'Category not found'}), 404
            return jsonify(commune_data[property_type][category])
        else:
            return jsonify(commune_data[property_type])
    else:
        return jsonify(commune_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
