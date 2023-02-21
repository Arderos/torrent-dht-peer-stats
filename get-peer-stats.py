import argparse
import bencodepy
import hashlib
import btdht
import binascii
import requests
import time
import os

IP_API_URL = "http://ip-api.com/json/{}"
RATE_LIMIT = 40  # requests per minute
COLLECTION_TIME = 120 #seconds

def get_ip_info(ip):
    url = IP_API_URL.format(ip)
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None


def main(args):
    torrent_file = args.torrent_file
    decoded = bencodepy.decode(torrent_file.read())
    info = bencodepy.encode(dict(decoded.get(b"info")))
    info_hash = hashlib.sha1(info).hexdigest()
    print(f"{info_hash=}")

    ip_file_path = f"{info_hash}.txt"

    peers = set()
    if os.path.exists(ip_file_path):
        with open(ip_file_path, 'r') as ip_file:
            for line in ip_file:
                ip = line.strip()
                peers.add(ip)
    else:
        dht = btdht.DHT()
        dht.start()
        print("Collecting peers from DHT...")
        start_time = time.time()
        count = 0
        while time.time() - start_time <= COLLECTION_TIME:
            new_peers = dht.get_peers(binascii.a2b_hex(info_hash))
            if new_peers:
                for peer in new_peers:
                    ip = str(peer[0].split(":")[0])
                    peers.add(ip)
                count += len(new_peers)
                print(f"\rCollected {len(peers)} unique peers...", end="")
            time.sleep(1)
        print("\n")
        dht.stop()

        with open(ip_file_path, 'w') as ip_file:
            ip_file.write('\n'.join([str(peer) for peer in peers]))

    print(f"Found {len(peers)} peers.")
    print("Fetching IP info...")
    info_list = []
    total = len(peers)
    count = 0
    last_timestamp = time.time()
    for peer in peers:
        if time.time() - last_timestamp >= 60 / RATE_LIMIT:
            time.sleep(5)
            last_timestamp = time.time()

        info = get_ip_info(peer)
        if info:
            info_list.append(info)
        count += 1
        print(f"Processed {count}/{total} IPs...", end='\r')

    print("\n\n=== Statistics ===\n")
    countries = {}
    isps = {}
    for info in info_list:
        country = info.get('country')
        if country:
            isp = info.get('isp')
            if isp:
                isps.setdefault(country, {}).setdefault(isp, 0)
                isps[country][isp] += 1
            countries[country] = countries.get(country, 0) + 1

    print("By Country:\n")
    for country, count in sorted(countries.items(), key=lambda x: x[1], reverse=True):
        percentage = count / total * 100
        print(f"{country} - {percentage:.2f}%")
        if country in isps:
            print("  ISPs:")
            for isp, count in sorted(isps[country].items(), key=lambda x: x[1], reverse=True):
                isp_percentage = count / countries[country] * 100
                print(f"    {isp} - {isp_percentage:.2f}%")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("torrent_file", type=argparse.FileType('rb'), help="path to the torrent file")
    args = parser.parse_args()
    main(args)

