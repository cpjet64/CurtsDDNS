# Curt's Dynamic DNS Updater

Curt's Dynamic DNS Updater is a Python script designed to update DNS records automatically for dynamic IP addresses. This solution supports multiple DNS providers including Cloudflare.

## Features

- Automatic IP detection and DNS record update
- Support for multiple DNS providers
- Configurable via an INI file
- Runs continuously with a configurable check interval

## Requirements

- Python 3.12
- `requests` library

## Installation

### Installing Python 3.12 on Debian-based Systems

1. Update your package list:
    ```sh
    sudo apt update
    ```

2. Install dependencies:
    ```sh
    sudo apt install -y software-properties-common
    ```

3. Add the deadsnakes PPA:
    ```sh
    sudo add-apt-repository ppa:deadsnakes/ppa
    sudo apt update
    ```

4. Install Python 3.12:
    ```sh
    sudo apt install -y python3.12 python3.12-venv python3.12-dev
    ```

### Setting Up the Project

1. Clone the repository:
    ```sh
    git clone https://github.com/cpjet64/curtsddns.git
    cd curtsddns
    ```

2. Create a virtual environment:
    ```sh
    python3.12 -m venv venv
    ```

3. Activate the virtual environment:
    ```sh
    source venv/bin/activate
    ```

4. Install the required dependencies:
    ```sh
    pip install requests
    ```

5. Configure your DNS settings in the `config.ini` file. You can use `config.ini.example` as a template:
    ```sh
    cp config.ini.example config.ini
    ```

## Configuration

The `config.ini` file should be structured as follows:

```ini
[settings]
DNS_PROVIDER = cloudflare
CHECK_INTERVAL = 60

[cloudflare]
CLOUDFLARE_API_TOKEN = your_cloudflare_api_token
CLOUDFLARE_ZONE_ID = your_cloudflare_zone_id
CLOUDFLARE_RECORD_NAME = your_dns_record_name
```

## Usage

To start the script, simply run:

```sh
python curtsddns.py
```
## Systemd Service

For continuous operation, you can set up a systemd service:

Copy the curtsddns.service file to /etc/systemd/system/ and then modify as needed:

```sh
sudo cp curtsddns.service /etc/systemd/system/
sudo nano /etc/systemd/system/curtsddns.service
```

### OR 

Have the file created for you using the current user and file location:

```sh
echo "[Unit]
Description=Curt's Dynamic DNS Updater Service
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/curtsddns.py
Restart=on-failure

[Install]
WantedBy=multi-user.target" | sudo tee /etc/systemd/system/curtsddns.service
```

Reload the systemd daemon:

```sh
sudo systemctl daemon-reload
```

Enable and start the service:

```sh
sudo systemctl enable curtsddns
sudo systemctl start curtsddns
```

## Files

* curtsddns.py: Main script for updating DNS records.
* cloudflare_module.py: Module for handling Cloudflare DNS updates.
* config.ini: Configuration file (create from config.ini.example).
* config.ini.example: Example configuration file.
* curtsddns.service: Systemd service file for running the script as a service.

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## Contact

For support or inquiries, please contact Curt at curt@curtpme.com.
