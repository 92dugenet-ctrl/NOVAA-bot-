import requests
from bs4 import BeautifulSoup
import re
import base64
import os
import time
import urllib.request
import threading
import asyncio
import sys
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

MAX_EMAILS_PAR_SESSION = 20

# ============================================
# TÉLÉCHARGEMENT PLAQUETTE
# ============================================

def telecharger_plaquette():
    try:
        print("📥 Téléchargement de la plaquette...")
        urllib.request.urlretrieve(URL_PLAQUETTE, FICHIER_PLAQUETTE)
        print(f"✅ Plaquette téléchargée ({os.path.getsize(FICHIER_PLAQUETTE)/1024:.1f} Ko)")
        return True
    except Exception as e:
        print(f"❌ Erreur téléchargement: {e}")
        return False

# ============================================
# SCRAPING
# ============================================

def scraper_entreprises(activite, ville):
    url = f"https://www.pagesjaunes.fr/recherche/{activite}/{ville}"
    entreprises = []
    
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        
        for carte in soup.find_all(["div", "article"], class_=re.compile(r"carte|card|fiche|result")):
            nom = carte.find(["h2", "h3", "strong"], class_=re.compile(r"nom|title|denomination"))
            tel = carte.find(["span", "a"], href=re.compile(r"tel:"))
            site = carte.find("a", href=re.compile(r"^https?://"))
            
            if nom and not site:
                nom_texte = nom.text.strip()
                if len(nom_texte) > 2:
                    entreprises.append({"nom": nom_texte, "telephone": tel.text.strip() if tel else "Non trouvé"})
    except Exception as e:
        print(f"❌ Erreur scraping: {e}")
    
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
        f"📎 Plaquette : {'✅' if os.path.exists(FICHIER_PLAQUETTE) else '❌'}"
    )

async def prospect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Usage : /prospect [activite] [ville]")
        return
    
    activite = args[0]
    ville = " ".join(args[1:])
    
    await update.message.reply_text(f"🔍 Recherche de {activite} sans site à {ville}...")
    
    entreprises = scraper_entreprises(activite, ville)
    
    if not entreprises:
        await update.message.reply_text("❌ Aucune entreprise sans site trouvée.")
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
    
    await update.message.reply_text(f"✅ {envoyes} emails envoyés !")

# ============================================
# SERVEUR DE SANTÉ
# ============================================

app_flask = Flask(__name__)

@app_flask.route('/')
def health():
    return "✅ Bot NOVAA V2 is running!", 200

@app_flask.route('/health')
def health_check():
    return "OK", 200

def run_server():
    app_flask.run(host='0.0.0.0', port=10000, debug=False, threaded=True)

# ============================================
# LANCEMENT (Version compatible Python 3.10+)
# ============================================

def run_bot():
    """Fonction principale pour démarrer le bot"""
    print("🤖 Agent NOVAA V2 - Démarrage...")
    telecharger_plaquette()
    
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("prospect", prospect))
    
    print("✅ Agent NOVAA V2 prêt !")
    print("🤖 En attente des commandes Telegram...")
    
    # Démarrer le bot de manière synchrone
    application.run_polling()

def main():
    # Démarrer le serveur de santé
    threading.Thread(target=run_server, daemon=True).start()
    print("🏥 Serveur de santé sur le port 10000")
    
    # Démarrer le bot
    run_bot()

if __name__ == "__main__":
    main()
