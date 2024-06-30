# Curt's Dynamic DNS Updater

Curt's Dynamic DNS Updater is a Python script designed to update DNS records automatically for dynamic IP addresses. This solution supports multiple DNS providers including Cloudflare and Dynu.

## Features

- Automatic IP detection and DNS record update
- Support for multiple DNS providers
- Configurable via an INI file
- Runs continuously with a configurable check interval

## Requirements

- Python 3.x
- `requests` library

## Installation

1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/curtsddns.git
    cd curtsddns
    ```

2. Install the required dependencies:
    ```sh
    pip install requests
    ```

3. Configure your DNS settings in the `config.ini` file. You can use `config.ini.example` as a template:
    ```sh
    cp config.ini.example config.ini
    ```

## Configuration

The `config.ini` file should be structured as follows:

```ini
[settings]
DNS_PROVIDER = cloudflare

[cloudflare]
CLOUDFLARE_API_TOKEN = your_cloudflare_api_token
CLOUDFLARE_ZONE_ID = your_cloudflare_zone_id
CLOUDFLARE_RECORD_NAME = your_dns_record_name
