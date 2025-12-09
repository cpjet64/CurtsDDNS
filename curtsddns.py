import configparser
import logging
from logging.handlers import RotatingFileHandler
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
LOG_FILE = config.get('logging', 'LOG_FILE', fallback='curtsddns.log')
LOG_LEVEL = config.get('logging', 'LOG_LEVEL', fallback='INFO').upper()
LOG_MAX_BYTES = config.getint('logging', 'LOG_MAX_BYTES', fallback=1048576)
LOG_BACKUP_COUNT = config.getint('logging', 'LOG_BACKUP_COUNT', fallback=5)

logger = logging.getLogger('curtsddns')
if not logger.handlers:
    level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    log_path = os.path.join(os.path.dirname(__file__), LOG_FILE)
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    formatter = logging.Formatter(
        '%(asctime)s %(levelname)s %(message)s'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

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
        logger.info(
            "Auto-update: checking for new version (comparing local HEAD to origin/HEAD)."
        )
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
            logger.info(
                "Auto-update: new version detected (local %s, remote %s).",
                local_sha,
                remote_sha,
            )
            return True

        logger.info(
            "Auto-update: no new version available "
            "(local %s matches remote %s).",
            local_sha,
            remote_sha,
        )
        return False
    except Exception as e:
        logger.warning("Auto-update: git check failed: %s", e)
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
        logger.info("Auto-update: update applied successfully, restarting process.")
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logger.error("Auto-update: git pull or restart failed: %s", e)


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
            logger.info("Current DNS record: %s", existing_ip)
            logger.info("Current IP address: %s", public_ip)
            if public_ip != existing_ip:
                logger.warning(
                    "IP address and DNS record do not match. Starting update."
                )
                result = update_dns(public_ip)
                if result:
                    try:
                        if result['status'] == 'success':
                            logger.info(
                                "Successfully updated DNS record to %s",
                                public_ip,
                            )
                        else:
                            logger.error("Failed to update DNS record.")
                            logger.error(
                                "Error: %s",
                                result.get('message', 'No message provided'),
                            )
                    except KeyError as e:
                        logger.error("Failed to update DNS record.")
                        logger.error(
                            "Reason: the update_dns(public_ip) function "
                            "returned dictionary without %s field.",
                            e,
                        )
                else:
                    logger.error("Failed to update DNS record.")
                    logger.error(
                        "Reason: the update_dns(public_ip) function returned "
                        "None or an unexpected value.",
                    )
            else:
                logger.info("IP address and DNS record match. No updates needed.")
        except Exception as e:
            logger.exception("An error occurred during the operation: %s", e)
        time.sleep(CHECK_INTERVAL)  # Check again based on the interval in config


if __name__ == '__main__':
    logger.info(
        "Curt's DDNS starting "
        "(provider=%s, interval=%s, auto_update=%s, auto_update_interval=%s)",
        DNS_PROVIDER,
        CHECK_INTERVAL,
        AUTO_UPDATE,
        AUTO_UPDATE_INTERVAL,
    )
    if not AUTO_UPDATE:
        logger.info("Auto-update is disabled in config; no update checks will run.")
    else:
        logger.info(
            "Auto-update is enabled; checking every %s seconds.",
            AUTO_UPDATE_INTERVAL,
        )
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Curt's DDNS shutting down due to KeyboardInterrupt.")
    except SystemExit:
        logger.info("Curt's DDNS shutting down due to SystemExit.")
        raise
    except BaseException as exc:  # pragma: no cover - defensive catch-all
        logger.exception(
            "Curt's DDNS exiting due to unexpected error: %s", exc
        )
        raise
    else:
        logger.info("Curt's DDNS main loop exited normally; shutting down.")
