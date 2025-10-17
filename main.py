import requests
import argparse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import logging
from collections import deque

# --- Konfigurasi Awal ---
# Konfigurasi logging untuk output yang jelas
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Header User-Agent agar terlihat seperti browser biasa
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Set untuk menyimpan URL yang sudah diperiksa agar tidak duplikat
processed_urls = set()

def is_valid_url(url):
    """Memeriksa apakah URL memiliki skema (http/https) dan domain yang valid."""
    parsed = urlparse(url)
    return bool(parsed.scheme) and bool(parsed.netloc)

def get_all_links(base_url):
    """
    Mengambil semua link unik dari sebuah halaman web.
    
    :param base_url: URL halaman yang akan dipindai.
    :return: Sebuah set (Set) berisi URL absolut yang ditemukan.
    """
    links_to_check = set()
    
    try:
        # 1. Ambil konten halaman
        response = requests.get(base_url, headers=HEADERS, timeout=10)
        # Beri error jika status bukan 2xx (misal 404 atau 500)
        response.raise_for_status()  
        
        # 2. Parse HTML menggunakan BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 3. Temukan semua tag <a> yang memiliki atribut href
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Lewati link internal halaman (anchor #), email (mailto:), atau javascript
            if href.startswith('#') or href.startswith('mailto:') or href.startswith('javascript:'):
                continue
            
            # 4. Ubah link relatif menjadi absolut
            # (misal: /about -> https://domain.com/about)
            absolute_url = urljoin(base_url, href)
            
            # 5. Validasi URL dan tambahkan ke set
            if is_valid_url(absolute_url):
                links_to_check.add(absolute_url)
                
    except requests.exceptions.RequestException as e:
        logging.error(f"Gagal mengambil {base_url}: {e}")
    
    return links_to_check

def check_link(url):
    """
    Memeriksa status satu URL.
    
    :param url: URL yang akan diperiksa.
    :return: (status_code, status_message)
             Contoh: (200, "OK") atau (404, "Not Found")
    """
    if url in processed_urls:
        return None, "Skipped (Already Checked)"
        
    processed_urls.add(url)
    
    try:
        # Gunakan method HEAD untuk efisiensi (tidak download body/isi halaman)
        # allow_redirects=True akan mengikuti redirect (301, 302) ke halaman final
        response = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        
        if response.status_code >= 400:
            # 4xx (Client Error) atau 5xx (Server Error)
            return response.status_code, f"Client/Server Error ({response.reason})"
        else:
            # 2xx (Success) atau 3xx (Redirect telah diikuti)
            return response.status_code, "OK"
            
    except requests.exceptions.Timeout:
        return None, "Timeout"
    except requests.exceptions.TooManyRedirects:
        return None, "Too Many Redirects"
    except requests.exceptions.ConnectionError:
        return None, "Connection Error"
    except requests.exceptions.RequestException as e:
        # Tangkap error umum lainnya
        return None, f"Error Lainnya: {e}"

def main():
    """Fungsi utama untuk parsing argumen dan menjalankan logika."""
    parser = argparse.ArgumentParser(
        description="Pemeriksa Tautan Rusak (Broken Link Checker) untuk sebuah halaman web."
    )
    
    parser.add_argument(
        'url', 
        type=str, 
        help="URL lengkap (termasuk http:// atau https://) dari halaman yang ingin diperiksa."
    )
    
    args = parser.parse_args()
    base_url = args.url
    
    if not is_valid_url(base_url):
        logging.error(f"URL tidak valid: {base_url}. Pastikan menyertakan 'http://' atau 'https://'.")
        return

    logging.info(f"Memulai pemindaian di: {base_url}")
    
    # Ambil semua link dari halaman utama
    links_to_check = get_all_links(base_url)
    
    if not links_to_check:
        logging.warning("Tidak ada tautan eksternal yang ditemukan di halaman tersebut.")
        return

    logging.info(f"Menemukan {len(links_to_check)} tautan unik. Memulai pemeriksaan...")
    
    broken_links = []
    ok_links = 0
    
    # Periksa setiap link
    for i, link in enumerate(links_to_check):
        # Cetak progress agar pengguna tahu skrip berjalan
        print(f"  ({i+1}/{len(links_to_check)}) Memeriksa: {link[:75]}...") # Potong URL panjang
        
        status_code, message = check_link(link)
        
        if status_code is None: # Error koneksi/timeout
            logging.warning(f"  -> RUSAK: {link} (Alasan: {message})")
            broken_links.append((link, message))
        elif status_code >= 400: # Error 4xx atau 5xx
            logging.warning(f"  -> RUSAK: {link} (Status: {status_code} {message})")
            broken_links.append((link, f"Status {status_code}"))
        else:
            ok_links += 1

    # --- Cetak Laporan Akhir ---
    print("\n" + "="*30)
    print("--- LAPORAN PEMINDAIAN SELESAI ---")
    print("="*30)
    print(f"Halaman Dipindai : {base_url}")
    print(f"Total Tautan Diperiksa : {len(links_to_check)}")
    print(f"Tautan Berfungsi : {ok_links}")
    print(f"Tautan Rusak/Error : {len(broken_links)}")
    
    if broken_links:
        print("\n--- Daftar Tautan Rusak ---")
        for link, reason in broken_links:
            print(f"- {link}\n  (Alasan: {reason})")
    
    logging.info("Pemeriksaan selesai.")

# Standar entri poin Python
if __name__ == "__main__":
    main()
