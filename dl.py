import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import requests
import pickle
import threading
from urllib.parse import unquote
from bs4 import BeautifulSoup

# Configuration
DOSSIER_TELECHARGEMENT = "telechargements/"
DOSSIER_COOKIES = "cookies/"
os.makedirs(DOSSIER_TELECHARGEMENT, exist_ok=True)
os.makedirs(DOSSIER_COOKIES, exist_ok=True)

# Chemin du fichier de cookies
COOKIES_FILE = os.path.join(DOSSIER_COOKIES, "uploady_io_cookies.pkl")

# Initialiser Chrome avec undetected-chromedriver
options = uc.ChromeOptions()
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--start-maximized")
options.add_argument("--disable-extensions")
options.add_argument("--disable-infobars")

# Désactiver les téléchargements automatiques
prefs = {
    "download.default_directory": DOSSIER_TELECHARGEMENT,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
}
options.add_experimental_option("prefs", prefs)

# Variable globale pour le driver
driver = None
driver_lock = threading.Lock()

def init_driver():
    """Initialise le driver Chrome une seule fois."""
    global driver
    with driver_lock:
        if driver is None:
            driver = uc.Chrome(options=options)
            print("✅ Chrome ouvert avec undetected-chromedriver.")

            # Charger les cookies sauvegardés
            if os.path.exists(COOKIES_FILE):
                driver.get("https://uploady.io")
                time.sleep(2)
                with open(COOKIES_FILE, "rb") as f:
                    cookies = pickle.load(f)
                for cookie in cookies:
                    try:
                        if 'domain' in cookie and cookie['domain'] != '.uploady.io':
                            cookie['domain'] = '.uploady.io'
                        driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"⚠️  Impossible d'ajouter le cookie {cookie.get('name', 'inconnu')} : {e}")
                print("✅ Cookies chargés.")
                driver.get("https://uploady.io")
                time.sleep(3)
            else:
                print("⚠️  Aucun cookie trouvé. Tu devras te connecter manuellement la première fois.")

def extraire_liens_episodes(url):
    """Extrait TOUS les liens des épisodes dans div.postinfo, mais UNIQUEMENT ceux pointant vers uploady.io."""
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )
        soup = BeautifulSoup(response.text, "html.parser")
        postinfo = soup.find("div", class_="postinfo")
        if not postinfo:
            print("❌ Balise div.postinfo introuvable !")
            return []

        # Trouver la section "Uploady" (couleur #c2107b)
        uploady_section = None
        for div in postinfo.find_all("div", style=True):
            style = div.get("style", "")
            if "color:#c2107b" in style or "color: #c2107b" in style:
                uploady_section = div
                break

        if not uploady_section:
            print("⚠️  Section 'Uploady' introuvable !")
            return []

        # Extraire les liens UNIQUEMENT dans la section Uploady
        liens_episodes = []
        current_b = uploady_section.find_parent("b")
        if current_b:
            next_b = current_b.find_next_sibling("b")
            while next_b:
                # Vérifier si on atteint une nouvelle section (ex: DailyUploads)
                div_in_next_b = next_b.find("div", style=True)
                if div_in_next_b and ("color:#" in div_in_next_b.get("style", "") or "color: #" in div_in_next_b.get("style", "")):
                    break  # On quitte la section Uploady

                a = next_b.find("a", href=True)
                if a and "dl-protect.link" in a["href"]:
                    liens_episodes.append(a["href"])
                next_b = next_b.find_next_sibling("b")

        return liens_episodes
    except Exception as e:
        print(f"❌ Erreur extraction : {e}")
        return []

def telecharger_depuis_dl_protect(lien_dl_protect):
    """Télécharge depuis dl-protect.link avec détection automatique de la sortie."""
    try:
        with driver_lock:
            driver.get(lien_dl_protect)
        print(f"\n🌐 Page ouverte : {lien_dl_protect}")
        print("⚠️  Coche la case Cloudflare MANUELLEMENT. Le script détectera automatiquement quand tu auras quitté dl-protect.link...")

        # Attendre automatiquement que l'utilisateur quitte dl-protect.link
        start_time = time.time()
        while time.time() - start_time < 60:  # Timeout après 60 secondes
            with driver_lock:
                current_url = driver.current_url
            if "dl-protect.link" not in current_url:
                break
            time.sleep(1)
        else:
            print("⚠️  Temps écoulé (60s) : vérification Cloudflare non terminée.")
            return

        print("✅ Vérification Cloudflare terminée, le script reprend le contrôle...")

        # Sauvegarder les cookies après la vérification Cloudflare
        with driver_lock:
            cookies = driver.get_cookies()
        with open(COOKIES_FILE, "wb") as f:
            pickle.dump(cookies, f)
            print("✅ Cookies sauvegardés pour éviter la reconnexion.")

        # --- ÉTAPE 1 : Cliquer sur le bouton de la PAGE 1 (button#downloadbtn) ---
        try:
            with driver_lock:
                bouton_page1 = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#downloadbtn"))
                )
                bouton_page1.click()
            print("✅ Cliqué sur le bouton de la PAGE 1 (Télécharger).")
            time.sleep(5)  # Attendre la redirection vers la PAGE 2
        except Exception as e:
            print(f"❌ Impossible de cliquer sur le bouton de la PAGE 1 : {e}")
            return

        # --- ÉTAPE 2 : Cliquer sur le lien de la PAGE 2 (a#downloadbtn) ---
        try:
            with driver_lock:
                # Attendre que la PAGE 2 soit chargée
                lien_page2 = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a#downloadbtn"))
                )
                print("✅ Bouton de la PAGE 2 trouvé : 'Démarrer le téléchargement rapide'.")

                # Récupérer le lien direct
                lien_direct = lien_page2.get_attribute("href")
                print(f"🔗 Lien direct : {lien_direct}")

                # Cliquer sur le lien pour lancer le téléchargement
                lien_page2.click()
            print("✅ Cliqué sur le bouton de la PAGE 2 (Démarrer le téléchargement rapide).")

            # Nom du fichier depuis l'URL initiale
            nom_fichier = unquote(lien_dl_protect.split("fn=")[1].split("&")[0])

            # Téléchargement avec les cookies (en arrière-plan)
            session = requests.Session()
            with driver_lock:
                for cookie in driver.get_cookies():
                    session.cookies.set(cookie['name'], cookie['value'], domain='.uploady.io')

            # Lancer le téléchargement dans un thread séparé
            def telecharger_fichier():
                try:
                    response = session.get(lien_direct, stream=True, headers={"User-Agent": "Mozilla/5.0"})
                    with open(f"{DOSSIER_TELECHARGEMENT}{nom_fichier}", "wb") as f:
                        for chunk in response.iter_content(8192):
                            f.write(chunk)
                    print(f"✅ Téléchargé : {nom_fichier}")
                except Exception as e:
                    print(f"❌ Erreur lors du téléchargement de {nom_fichier} : {e}")

            # Démarrer le téléchargement en arrière-plan
            thread = threading.Thread(target=telecharger_fichier)
            thread.start()
            print(f"📥 Téléchargement de {nom_fichier} lancé en arrière-plan.")

        except Exception as e:
            print(f"❌ Impossible de cliquer sur le bouton de la PAGE 2 : {e}")

    except Exception as e:
        print(f"❌ Erreur globale : {e}")

# Demander l'URL
URL_INITIALE = input("🌐 Colle l'URL de la page à analyser : ").strip()

if __name__ == "__main__":
    # Initialiser le driver
    init_driver()

    print("🔍 Recherche des liens Uploady.io...")
    liens = extraire_liens_episodes(URL_INITIALE)
    print(f"📌 Liens Uploady.io trouvés : {len(liens)}")

    for i, lien in enumerate(liens, 1):
        print(f"\n--- Téléchargement {i}/{len(liens)} ---")
        telecharger_depuis_dl_protect(lien)
        time.sleep(2)  # Petit délai pour éviter de surcharger le navigateur

    # Attendre que tous les téléchargements soient terminés
    print("\n⏳ Attente de la fin des téléchargements en arrière-plan...")
    time.sleep(10)  # Délai pour laisser le temps aux threads de finir

    with driver_lock:
        if driver:
            driver.quit()
    print("\n🎉 Tous les téléchargements ont été lancés !")
