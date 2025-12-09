import configparser
import os
import subprocess
import sys
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
AUTO_UPDATE = config.getboolean('settings', 'AUTO_UPDATE', fallback=False)
AUTO_UPDATE_INTERVAL = config.getint('settings', 'AUTO_UPDATE_INTERVAL', fallback=3600)

# Timestamp of the last auto-update check (seconds since epoch)
last_update_check = 0.0
# Import the appropriate module based on DNS_PROVIDER
if DNS_PROVIDER == 'cloudflare':
    from cloudflare_module import get_public_ip, get_existing_dns_ip, update_dns
else:
    raise ValueError(f"Unsupported DNS provider: {DNS_PROVIDER}")


def _auto_update_check_available() -> bool:
    """
    Return True if a newer version is available in the git remote.

    This assumes the updater is running from a git clone with an 'origin'
    remote pointing to the GitHub repository. If git is not available or
    the directory is not a git repo, this will safely return False.
    """
    try:
        local_sha = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        remote_output = subprocess.check_output(
            ['git', 'ls-remote', 'origin', 'HEAD'],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        remote_sha = remote_output.split()[0]

        if local_sha != remote_sha:
            print(
                f"Auto-update: new version detected "
                f"(local {local_sha}, remote {remote_sha})."
            )
            return True

        return False
    except Exception as e:
        # Any error here should not break DNS updates; just log and continue.
        print(f"Auto-update: git check failed: {e}")
        return False


def _auto_update_apply_and_restart() -> None:
    """
    Perform a git pull to update the working tree, then restart the process.

    Uses os.execv to re-exec the current interpreter with the same arguments,
    so the updated code is loaded without relying on the service manager.
    """
    try:
        subprocess.check_call(
            ['git', 'pull', '--ff-only'],
            stderr=subprocess.STDOUT,
        )
        print("Auto-update: update applied successfully, restarting process.")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        print(f"Auto-update: git pull or restart failed: {e}")


def main():
    global last_update_check

    while True:
        try:
            if AUTO_UPDATE:
                now = time.time()
                if now - last_update_check >= AUTO_UPDATE_INTERVAL:
                    last_update_check = now
                    if _auto_update_check_available():
                        _auto_update_apply_and_restart()

            public_ip = get_public_ip()
            existing_ip = get_existing_dns_ip()
            print(f"Current DNS record: {existing_ip}")
            print(f"Current IP address: {public_ip}")
            if public_ip != existing_ip:
                print("IP address and DNS record do not match. Starting update.")
                result = update_dns(public_ip)
                if result:
                    try:
                        if result['status'] == 'success':
                            print(f"Successfully updated DNS record to {public_ip}")
                        else:
                            print("Failed to update DNS record.")
                            print(f"Error: {result.get('message', 'No message provided')}")
                    except KeyError as e:
                        print("Failed to update DNS record.")
                        print(f"Reason: The update_dns(public_ip) function returned dictionary without {e} field.")
                else:
                    print("Failed to update DNS record.")
                    print("Reason: The update_dns(public_ip) function returned None or an unexpected value.")
            else:
                print("IP address and DNS record match. No updates needed.")
        except Exception as e:
            print(f"An error occurred during the operation: {str(e)}")
        time.sleep(CHECK_INTERVAL)  # Check again based on the interval in config


if __name__ == '__main__':
    main()
