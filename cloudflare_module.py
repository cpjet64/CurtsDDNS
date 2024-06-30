# cloudflare_module.py
import configparser
import os

import requests


def load_config_file(filepath):
    config = configparser.ConfigParser()
    config.read(filepath)
    return config

# Load configuration
config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = load_config_file(config_file_path)

CLOUDFLARE_API_TOKEN = config.get('cloudflare', 'CLOUDFLARE_API_TOKEN')
CLOUDFLARE_ZONE_ID = config.get('cloudflare', 'CLOUDFLARE_ZONE_ID')
CLOUDFLARE_RECORD_NAME = config.get('cloudflare', 'CLOUDFLARE_RECORD_NAME')

def get_public_ip():
    response = requests.get('https://checkmyip.app/')
    return response.text.strip()

def get_existing_dns_ip():
    headers = {
        'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    url = f'https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records?type=A&name={CLOUDFLARE_RECORD_NAME}'
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if response_data['success']:
        return response_data['result'][0]['content']
    else:
        raise Exception(f"Failed to fetch existing DNS record IP. Error: {response_data['errors']}")

def update_dns(ip_address):
    headers = {
        'Authorization': f'Bearer {CLOUDFLARE_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    # Get the DNS record ID
    url = f'https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records?type=A&name={CLOUDFLARE_RECORD_NAME}'
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if response_data['success']:
        record_id = response_data['result'][0]['id']

        # Update the DNS record with the new IP address
        dns_data = {
            'type': 'A',
            'name': CLOUDFLARE_RECORD_NAME,
            'content': ip_address,
            'ttl': 120,
            'proxied': False
        }

        update_url = f'https://api.cloudflare.com/client/v4/zones/{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}'
        update_response = requests.put(update_url, headers=headers, json=dns_data)
        return update_response.json()
    else:
        return response_data
