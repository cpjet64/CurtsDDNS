import configparser
import os
import time
import requests


# Function to load configuration from an .ini file
def load_config_file(filepath):
    config = configparser.ConfigParser()
    config.read(filepath)
    return config


# Load configuration
config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config = load_config_file(config_file_path)

DNS_PROVIDER = config.get('settings', 'DNS_PROVIDER')
CHECK_INTERVAL = config.getint('settings', 'CHECK_INTERVAL', fallback=60)

# Import the appropriate module based on DNS_PROVIDER
if DNS_PROVIDER == 'cloudflare':
    from cloudflare_module import get_public_ip, get_existing_dns_ip, update_dns
else:
    raise ValueError(f"Unsupported DNS provider: {DNS_PROVIDER}")


def main():
    while True:
        try:
            public_ip = get_public_ip()
            existing_ip = get_existing_dns_ip()

            print(f"Current DNS record: {existing_ip}")

            if public_ip != existing_ip:
                result = update_dns(public_ip)
                if result['status'] == 'success':
                    print(f"Successfully updated DNS record to {public_ip}")
                else:
                    print("Failed to update DNS record.")
                    print(f"Error: {result['message']}")
            else:
                print("IP address has not changed.")
        except Exception as e:
            print(f"Error occurred: {e}")

        time.sleep(CHECK_INTERVAL)  # Check again based on the interval in config


if __name__ == '__main__':
    main()
