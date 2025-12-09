# cloudflare_module.py
import configparser
import ipaddress
import logging
import os
from typing import List

import requests


logger = logging.getLogger('curtsddns')


def load_config_file(filepath):
    config = configparser.ConfigParser()
    config.read(filepath)
    return config


# Load configuration
config_file_path = os.path.join(os.path.dirname(__file__), "config.ini")
config = load_config_file(config_file_path)

CLOUDFLARE_API_TOKEN = config.get("cloudflare", "CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ZONE_ID = config.get("cloudflare", "CLOUDFLARE_ZONE_ID")
CLOUDFLARE_RECORD_NAME = config.get("cloudflare", "CLOUDFLARE_RECORD_NAME")


_cloudflare_ipv4_networks: List[ipaddress.IPv4Network] = []


def _load_cloudflare_ipv4_networks() -> List[ipaddress.IPv4Network]:
    """
    Retrieve the current list of Cloudflare IPv4 CIDR ranges.

    Prefer the official Cloudflare /ips API. If that fails for any reason,
    fall back to the documented static list to avoid weakening protection.
    """
    global _cloudflare_ipv4_networks

    if _cloudflare_ipv4_networks:
        return _cloudflare_ipv4_networks

    cidrs: List[str] = []

    try:
        response = requests.get(
            "https://api.cloudflare.com/client/v4/ips", timeout=5
        )
        response.raise_for_status()
        data = response.json()
        result = data.get("result", {})
        cidrs = result.get("ipv4_cidrs", []) or []
        logger.info(
            "Loaded %d Cloudflare IPv4 CIDR ranges from /ips API.",
            len(cidrs),
        )
    except Exception as exc:
        # Fallback to the documented IPv4 ranges from
        # https://www.cloudflare.com/ips/
        logger.warning(
            "Failed to load Cloudflare IPv4 ranges from /ips API (%s); "
            "using static fallback list.",
            exc,
        )
        cidrs = [
            "173.245.48.0/20",
            "103.21.244.0/22",
            "103.22.200.0/22",
            "103.31.4.0/22",
            "141.101.64.0/18",
            "108.162.192.0/18",
            "190.93.240.0/20",
            "188.114.96.0/20",
            "197.234.240.0/22",
            "198.41.128.0/17",
            "162.158.0.0/15",
            "104.16.0.0/13",
            "104.24.0.0/14",
            "172.64.0.0/13",
            "131.0.72.0/22",
        ]

    networks: List[ipaddress.IPv4Network] = []
    for cidr in cidrs:
        try:
            networks.append(ipaddress.IPv4Network(cidr))
        except ValueError:
            # Skip any malformed CIDR instead of failing the entire load.
            continue

    # Also block Cloudflare's public DNS resolver ranges which are not
    # included in the /ips API but should never be used as a client IP.
    extra_blocked_cidrs = ["1.1.1.0/24", "1.0.0.0/24"]
    for cidr in extra_blocked_cidrs:
        try:
            networks.append(ipaddress.IPv4Network(cidr))
        except ValueError:
            continue

    _cloudflare_ipv4_networks = networks
    return _cloudflare_ipv4_networks


def _is_public_non_cloudflare_ipv4(ip_str: str) -> bool:
    """
    Return True if ip_str is a valid, global (public) IPv4 address that is
    not within any known Cloudflare IPv4 ranges.
    """
    try:
        ip = ipaddress.IPv4Address(ip_str)
    except ipaddress.AddressValueError:
        return False

    # ip.is_global excludes private, loopback, link-local, and reserved ranges.
    if not ip.is_global:
        return False

    for network in _load_cloudflare_ipv4_networks():
        if ip in network:
            return False

    return True


def get_public_ip():
    """
    Determine the current public IPv4 address in a DNS-poisoning-resistant way.

    - Try multiple independent external services.
    - Require the IP to be a valid, global IPv4 address.
    - Reject any address that falls within Cloudflare's published IP ranges.

    If no suitable IP can be determined, raise an exception so the caller
    can skip updating DNS rather than risk poisoning the record.
    """
    endpoints = [
        "https://api.ipify.org",
        "https://ifconfig.me",
        "https://icanhazip.com",
        "https://checkmyip.app/",
    ]

    last_error: Exception | None = None

    for url in endpoints:
        try:
            logger.debug("Public IP detection: trying endpoint %s", url)
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            text = response.text.strip()
            # Some services may include extra text; take the first token.
            candidate_ip = text.split()[0]

            if not _is_public_non_cloudflare_ipv4(candidate_ip):
                logger.warning(
                    "Rejected IP candidate '%s' from %s "
                    "(not a suitable public, non-Cloudflare IPv4 address).",
                    candidate_ip,
                    url,
                )
                continue

            return candidate_ip
        except Exception as exc:
            last_error = exc
            continue

    raise RuntimeError(
        "Unable to determine a valid public IP address; "
        "all endpoints failed or returned unsuitable values."
    ) from last_error


def get_existing_dns_ip():
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    url = (
        f"https://api.cloudflare.com/client/v4/zones/"
        f"{CLOUDFLARE_ZONE_ID}/dns_records?type=A&name={CLOUDFLARE_RECORD_NAME}"
    )
    logger.info(
        "Fetching existing DNS record IP (zone_id=%s, name=%s).",
        CLOUDFLARE_ZONE_ID,
        CLOUDFLARE_RECORD_NAME,
    )
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if response_data["success"]:
        results = response_data.get("result") or []
        if not results:
            logger.warning(
                "No DNS records found for name=%s in zone_id=%s.",
                CLOUDFLARE_RECORD_NAME,
                CLOUDFLARE_ZONE_ID,
            )
            raise Exception(
                "DNS lookup succeeded but no records were returned "
                f"for {CLOUDFLARE_RECORD_NAME} in zone {CLOUDFLARE_ZONE_ID}."
            )
        return results[0]["content"]
    else:
        raise Exception(
            f"Failed to fetch existing DNS record IP. "
            f"Error: {response_data['errors']}"
        )


def update_dns(ip_address):
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }

    logger.info(
        "Updating DNS record (zone_id=%s, name=%s) to IP %s.",
        CLOUDFLARE_ZONE_ID,
        CLOUDFLARE_RECORD_NAME,
        ip_address,
    )

    # Get the DNS record ID
    url = (
        f"https://api.cloudflare.com/client/v4/zones/"
        f"{CLOUDFLARE_ZONE_ID}/dns_records?type=A&name={CLOUDFLARE_RECORD_NAME}"
    )
    response = requests.get(url, headers=headers)
    response_data = response.json()

    if response_data["success"]:
        record_id = response_data["result"][0]["id"]

        # Update the DNS record with the new IP address
        dns_data = {
            "type": "A",
            "name": CLOUDFLARE_RECORD_NAME,
            "content": ip_address,
            "ttl": 120,
            "proxied": False,
        }

        update_url = (
            f"https://api.cloudflare.com/client/v4/zones/"
            f"{CLOUDFLARE_ZONE_ID}/dns_records/{record_id}"
        )
        update_response = requests.put(update_url, headers=headers, json=dns_data)
        update_response_data = update_response.json()

        if update_response_data["success"]:
            return {"status": "success", "message": "DNS updated successfully"}
        else:
            return {
                "status": "failure",
                "message": (
                    "Failed to update DNS. "
                    f"Error: {update_response_data['errors']}"
                ),
            }
    else:
        return {
            "status": "failure",
            "message": (
                "Failed to fetch existing DNS record ID. "
                f"Error: {response_data['errors']}"
            ),
        }
