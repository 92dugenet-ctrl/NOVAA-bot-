import requests
from bs4 import BeautifulSoup
import re
import base64
import os
import time
import urllib.request
import threading
import gc
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============================================
# CONFIGURATION
# ============================================

TELEGRAM_TOKEN = "8853389688:AAHeKps1e3Hj5XdjzrAjYwoBhguqMKb6Tg0"
BREVO_API_KEY = "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"

VOTRE_NOM = "NOVAA"
VOTRE_SOCIETE = "NOVAA"
VOTRE_EMAIL = "contact@novaa.fr"
SITE_WEB = "https://llcnovaa.netlify.app"

URL_PLAQUETTE = "https://www.dropbox.com/scl/fi/oi8kyh5ctlrvn2pdjgun3/NOVAA_Commercial_Brochure_2026_EN.pdf?rlkey=mxjnm55cydfuuwngi1ypdvpn9&st=zrukk8p2&dl=1"
FICHIER_PLAQUETTE = "/tmp/plaquette.pdf"

MAX_ENTREPRISES_PAR_SESSION = 15
MAX_EMAILS_PAR_SESSION = 10

# ============================================
# TÉLÉCHARGEMENT PLAQUETTE
# ============================================

def telecharger_plaquette():
    try:
        print("📥 Téléchargement de la plaquette...")
        response = requests.get(URL_PLAQUETTE, stream=True)
        with open(FICHIER_PLAQUETTE, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Plaquette téléchargée ({os.path.getsize(FICHIER_PLAQUETTE)/1024:.1f} Ko)")
        return True
    except Exception as e:
        print(f"❌ Erreur téléchargement: {e}")
        return False

# ============================================
# SCRAPER AMÉLIORÉ (Version 2)
# ============================================

def scraper_entreprises(activite, ville):
    """
    Scrape les entreprises sans site web - Version améliorée
    """
    entreprises = []
    
    # Supprimer les accents et espaces pour l'URL
    activite_clean = activite.lower().strip()
    ville_clean = ville.lower().strip()
    
    # URL de recherche Pages Jaunes
    url = f"https://www.pagesjaunes.fr/recherche/{activite_clean}/{ville_clean}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    try:
        print(f"🔍 Scraping de: {url}")
        response = requests.get(url, headers=headers, timeout=20)
        print(f"✅ Statut HTTP: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ Erreur HTTP: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        response.close()
        
        # Méthode 1: Recherche par classe "carte" (structure classique)
        cartes = soup.find_all(["div", "article"], class_=re.compile(r"carte|card|result|item|listing|bloc|annonce"))
        print(f"🔍 {len(cartes)} cartes trouvées")
        
        for carte in cartes:
            try:
                # Recherche du nom
                nom_elem = (
                    carte.find(["h2", "h3", "strong", "span", "a"], class_=re.compile(r"nom|title|denomination|name|heading")) or
                    carte.find(["h2", "h3"], class_=re.compile(r".*")) or
                    carte.find("a", href=re.compile(r"/pro/"))
                )
                
                if not nom_elem:
                    continue
                
                nom = nom_elem.text.strip()
                if len(nom) < 2:
                    continue
                
                # Recherche du téléphone
                tel_elem = (
                    carte.find("span", class_=re.compile(r"num|telephone|phone|tel")) or
                    carte.find("a", href=re.compile(r"tel:"))
                )
                tel = tel_elem.text.strip() if tel_elem else "Non trouvé"
                
                # Vérification de l'absence de site web
                site_elem = (
                    carte.find("a", href=re.compile(r"^https?://")) or
                    carte.find("a", href=re.compile(r"www\.")) or
                    carte.find("a", class_=re.compile(r"site|web|url"))
                )
                
                if not site_elem:
                    entreprises.append({
                        "nom": nom,
                        "telephone": tel,
                        "ville": ville,
                        "activite": activite
                    })
                    print(f"✅ Trouvé: {nom} - {tel}")
                    
                    if len(entreprises) >= MAX_ENTREPRISES_PAR_SESSION:
                        break
                        
            except Exception as e:
                print(f"⚠️ Erreur sur une carte: {e}")
                continue
        
        # Méthode 2: Si aucune entreprise trouvée, essayer une approche alternative
        if len(entreprises) == 0:
            print("🔄 Tentative avec méthode alternative...")
            entreprises = scraper_entreprises_alternative(activite, ville)
        
        soup.clear()
        gc.collect()
        
    except Exception as e:
        print(f"❌ Erreur scraping: {e}")
    
    return entreprises


def scraper_entreprises_alternative(activite, ville):
    """
    Méthode de scraping alternative
    """
    entreprises = []
    
    try:
        # Utiliser Google Maps via une recherche simplifiée
        url = f"https://www.google.com/search?q={activite}+{ville}+site:google.com/maps"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        response.close()
        
        # Extraire les résultats de recherche
        for result in soup.find_all(["div", "h3"], class_=re.compile(r"g|r|srg")):
            nom_elem = result.find("h3")
            if nom_elem:
                nom = nom_elem.text.strip()
                if len(nom) > 3:
                    entreprises.append({
                        "nom": nom,
                        "telephone": "Non trouvé",
                        "ville": ville,
                        "activite": activite
                    })
                    if len(entreprises) >= MAX_ENTREPRISES_PAR_SESSION:
                        break
        
        soup.clear()
        gc.collect()
        
    except Exception as e:
        print(f"❌ Erreur scraping alternatif: {e}")
    
    return entreprises

# ============================================
# GÉNÉRATION EMAIL
# ============================================

def trouver_email(nom):
    nom_propre = ''.join(c for c in nom.lower() if c.isalnum() or c == ' ').replace(' ', '')
    return f"contact@{nom_propre}.fr"

# ============================================
# ENVOI EMAIL
# ============================================

def envoyer_email(destinataire, nom_entreprise):
    if not destinataire or "@" not in destinataire:
        return False
    
    if not os.path.exists(FICHIER_PLAQUETTE):
        if not telecharger_plaquette():
            return False
    
    corps = f"""Bonjour {nom_entreprise},

Je suis {VOTRE_NOM} de {VOTRE_SOCIETE}.

Je constate que vous n'avez pas encore de site web.

Nous proposons une solution clé en main :
✅ Site internet professionnel
✅ Système de réservation en ligne
✅ CRM pour gérer vos clients
✅ Automatisation des tâches

Le tout installé en 48 à 72 heures.

Découvrez notre offre : {SITE_WEB}

Cordialement,
{VOTRE_NOM}
{VOTRE_SOCIETE}
{VOTRE_EMAIL}"""
    
    data = {
        "sender": {"email": VOTRE_EMAIL, "name": VOTRE_NOM},
        "to": [{"email": destinataire}],
        "subject": f"🚀 NOVAA - Système digital pour {nom_entreprise}",
        "htmlContent": corps.replace("\n", "<br>")
    }
    
    if os.path.exists(FICHIER_PLAQUETTE):
        try:
            with open(FICHIER_PLAQUETTE, "rb") as f:
                fichier_base64 = base64.b64encode(f.read()).decode("utf-8")
            data["attachment"] = [{"content": fichier_base64, "name": "NOVAA_Commercial_Brochure_2026_EN.pdf"}]
        except:
            pass
    
    try:
        response = requests.post(
            "https://api.brevo.com/v3/smtp/email",
            json=data,
            headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"}
        )
        return response.status_code == 201
    except:
        return False

# ============================================
# COMMANDES TELEGRAM
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Agent NOVAA V2\n\n"
        "/prospect [activite] [ville] - Ex: /prospect plombier Lyon\n"
        "/check - Vérifier la plaquette\n"
        "/stats - Statistiques"
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(FICHIER_PLAQUETTE):
        await update.message.reply_text(f"✅ Plaquette disponible ({os.path.getsize(FICHIER_PLAQUETTE)/1024:.1f} Ko)")
    else:
        await update.message.reply_text("📥 Téléchargement...")
        if telecharger_plaquette():
            await update.message.reply_text("✅ Plaquette téléchargée")
        else:
            await update.message.reply_text("❌ Erreur de téléchargement")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 Statistiques\n\n"
        f"👤 Expéditeur : {VOTRE_EMAIL}\n"
        f"🌐 Site : {SITE_WEB}\n"
        f"📎 Plaquette : {'✅' if os.path.exists(FICHIER_PLAQUETTE) else '❌'}\n"
        f"📉 Mode optimisé (limite: {MAX_ENTREPRISES_PAR_SESSION} entreprises)"
    )

async def prospect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Usage : /prospect [activite] [ville]\n\nExemples:\n/prospect plombier Lyon\n/prospect boulanger Marseille\n/prospect coiffeur Paris")
        return
    
    activite = args[0]
    ville = " ".join(args[1:])
    
    await update.message.reply_text(f"🔍 Recherche de {activite} sans site à {ville}...\n⏳ Cette opération peut prendre quelques secondes.")
    
    entreprises = scraper_entreprises(activite, ville)
    
    if not entreprises:
        await update.message.reply_text(
            f"❌ Aucune entreprise sans site trouvée pour {activite} à {ville}.\n\n"
            f"💡 Suggestions:\n"
            f"• Vérifiez l'orthographe de l'activité\n"
            f"• Essayez une autre ville\n"
            f"• Exemple: /prospect boulanger Lyon\n"
            f"• Laissez 2-3 secondes entre chaque commande"
        )
        gc.collect()
        return
    
    for e in entreprises[:MAX_EMAILS_PAR_SESSION]:
        e["email"] = trouver_email(e["nom"])
    
    msg = f"✅ {len(entreprises)} entreprises trouvées !\n\n"
    for e in entreprises[:10]:
        msg += f"- {e['nom']} : {e['email']}\n"
    if len(entreprises) > 10:
        msg += f"\n... et {len(entreprises)-10} autres."
    msg += f"\n\n📧 Envoi des emails..."
    await update.message.reply_text(msg)
    
    envoyes = 0
    for e in entreprises[:MAX_EMAILS_PAR_SESSION]:
        if envoyer_email(e["email"], e["nom"]):
            envoyes += 1
        time.sleep(2)
        gc.collect()
    
    await update.message.reply_text(f"✅ {envoyes} emails envoyés !")
    
    entreprises.clear()
    gc.collect()

# ============================================
# SERVEUR DE SANTÉ
# ============================================

app_flask = Flask(__name__)

@app_flask.route('/')
def health():
    return "OK", 200

def run_server():
    app_flask.run(host='0.0.0.0', port=10000, debug=False, threaded=True)

# ============================================
# LANCEMENT
# ============================================

def run_bot():
    print("🤖 Agent NOVAA V2 - Démarrage...")
    telecharger_plaquette()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("prospect", prospect))
    
    print("✅ Agent NOVAA V2 prêt !")
    print("🤖 En attente des commandes Telegram...")
    
    application.run_polling()

def main():
    threading.Thread(target=run_server, daemon=True).start()
    print("🏥 Serveur de santé sur le port 10000")
    run_bot()

if __name__ == "__main__":
    main()
