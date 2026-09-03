import requests
from bs4 import BeautifulSoup
import re
import base64
import os
import time
import urllib.request
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import threading
from flask import Flask

# ============================================
# 🔧 CONFIGURATION - VOS CLÉS INTÉGRÉES
# ============================================

TELEGRAM_TOKEN = "8853389688:AAHeKps1e3Hj5XdjzrAjYwoBhguqMKb6Tg0"
BREVO_API_KEY = "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"

VOTRE_NOM = "NOVAA"  # ← À MODIFIER
VOTRE_SOCIETE = "NOVAA"
VOTRE_EMAIL = "contact@novaa.fr"
SITE_WEB = "https://llcnovaa.netlify.app"

# ============================================
# 📥 LIEN DROPBOX DE VOTRE PLAQUETTE
# ============================================

URL_PLAQUETTE = "https://www.dropbox.com/scl/fi/oi8kyh5ctlrvn2pdjgun3/NOVAA_Commercial_Brochure_2026_EN.pdf?rlkey=mxjnm55cydfuuwngi1ypdvpn9&st=zrukk8p2&dl=1"
FICHIER_PLAQUETTE = "/tmp/plaquette.pdf"

# Limites
MAX_EMAILS_PAR_JOUR = 300
MAX_ENTREPRISES_PAR_SESSION = 30
MAX_EMAILS_PAR_SESSION = 20

# ============================================
# 📥 TÉLÉCHARGEMENT DE LA PLAQUETTE
# ============================================

def telecharger_plaquette():
    try:
        print("📥 Téléchargement de la plaquette depuis Dropbox...")
        urllib.request.urlretrieve(URL_PLAQUETTE, FICHIER_PLAQUETTE)
        taille = os.path.getsize(FICHIER_PLAQUETTE) / 1024
        print(f"✅ Plaquette téléchargée ({taille:.1f} Ko)")
        return True
    except Exception as e:
        print(f"❌ Erreur téléchargement: {e}")
        return False

# ============================================
# 🔍 SCRAPING : ENTREPRISES SANS SITE
# ============================================

def scraper_entreprises_sans_site(activite, ville):
    """Scrape les entreprises sans site web"""
    url = f"https://www.pagesjaunes.fr/recherche/{activite}/{ville}"
    entreprises = []
    
    try:
        response = requests.get(
            url, 
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15
        )
        soup = BeautifulSoup(response.text, "html.parser")
        
        for carte in soup.find_all(["div", "article"], class_=re.compile(r"carte|card|fiche|result")):
            nom = carte.find(["h2", "h3", "strong"], class_=re.compile(r"nom|title|denomination"))
            tel = carte.find(["span", "a"], href=re.compile(r"tel:"))
            site = carte.find("a", href=re.compile(r"^https?://"))
            
            if nom and not site:
                nom_texte = nom.text.strip()
                if len(nom_texte) > 2:
                    entreprises.append({
                        "nom": nom_texte,
                        "telephone": tel.text.strip() if tel else "Non trouvé",
                        "ville": ville,
                        "activite": activite
                    })
    except Exception as e:
        print(f"❌ Erreur scraping: {e}")
    
    return entreprises

# ============================================
# 📧 TROUVER L'EMAIL (SIMULATION)
# ============================================

def trouver_email(nom_entreprise):
    """Trouve ou génère un email pour l'entreprise"""
    nom_propre = nom_entreprise.lower().strip()
    nom_propre = ''.join(c for c in nom_propre if c.isalnum() or c == ' ')
    return f"contact@{nom_propre.replace(' ', '')}.fr"

# ============================================
# 📝 VOTRE MAIL TYPE
# ============================================

EMAIL_TEMPLATE = """
Bonjour {nom_entreprise},

Je suis {votre_prenom} de {votre_societe}.

Je constate que vous avez récemment créé votre activité et que vous n'avez pas encore de site web.

Nous proposons une solution clé en main qui va bien au-delà d'un simple site :
✅ Site internet professionnel
✅ Système de réservation en ligne
✅ CRM pour gérer vos clients
✅ Automatisation des tâches répétitives

Le tout installé en 48 à 72 heures.

Découvrez notre offre : {site_web}

Vous trouverez notre plaquette commerciale en pièce jointe.

Souhaitez-vous qu'on échange rapidement ?

Cordialement,
{votre_prenom}
{votre_societe}
{votre_email}
"""

# ============================================
# 📧 ENVOI D'EMAIL AVEC PIÈCE JOINTE
# ============================================

def envoyer_email_brevo(destinataire, nom_entreprise):
    """Envoie un email personnalisé avec la plaquette NOVAA"""
    
    if not destinataire or "@" not in destinataire:
        return False
    
    if not os.path.exists(FICHIER_PLAQUETTE):
        if not telecharger_plaquette():
            return False
    
    url = "https://api.brevo.com/v3/smtp/email"
    headers = {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json"
    }
    
    corps = EMAIL_TEMPLATE.format(
        nom_entreprise=nom_entreprise,
        votre_prenom=VOTRE_NOM,
        votre_societe=VOTRE_SOCIETE,
        site_web=SITE_WEB,
        votre_email=VOTRE_EMAIL
    )
    
    data = {
        "sender": {"email": VOTRE_EMAIL, "name": VOTRE_NOM},
        "to": [{"email": destinataire}],
        "subject": f"🚀 NOVAA - Système digital pour {nom_entreprise}",
        "htmlContent": corps.replace("\n", "<br>")
    }
    
    if os.path.exists(FICHIER_PLAQUETTE):
        try:
            with open(FICHIER_PLAQUETTE, "rb") as f:
                fichier_bytes = f.read()
                fichier_base64 = base64.b64encode(fichier_bytes).decode("utf-8")
            data["attachment"] = [{
                "content": fichier_base64,
                "name": "NOVAA_Commercial_Brochure_2026_EN.pdf"
            }]
        except Exception as e:
            print(f"❌ Erreur pièce jointe: {e}")
    
    try:
        response = requests.post(url, json=data, headers=headers)
        return response.status_code == 201
    except Exception as e:
        print(f"❌ Erreur envoi: {e}")
        return False

# ============================================
# 🤖 COMMANDES TELEGRAM
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🤖 **Agent NOVAA V2**\n\n"
        f"🚀 `/prospect [activite] [ville] [email]` → Prospection ciblée\n"
        f"📎 `/check` → Vérifier la plaquette\n"
        f"📊 `/stats` → Statistiques\n\n"
        f"Exemple : `/prospect plombier Lyon`",
        parse_mode="Markdown"
    )

async def check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not os.path.exists(FICHIER_PLAQUETTE):
        if not telecharger_plaquette():
            await update.message.reply_text("❌ Erreur de téléchargement")
            return
    taille = os.path.getsize(FICHIER_PLAQUETTE) / 1024
    await update.message.reply_text(
        f"✅ **Plaquette disponible !**\n📏 Taille : {taille:.1f} Ko",
        parse_mode="Markdown"
    )

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📊 **Statistiques NOVAA V2**\n\n"
        f"📧 Limite Brevo : 300/jour\n"
        f"📎 Plaquette : `NOVAA_Commercial_Brochure_2026_EN.pdf`\n"
        f"👤 Expéditeur : {VOTRE_EMAIL}",
        parse_mode="Markdown"
    )

async def prospect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            f"❌ **Commande incomplète**\n\n"
            f"Usage : `/prospect [activite] [ville] [email]`\n\n"
            f"Exemple : `/prospect plombier Lyon`",
            parse_mode="Markdown"
        )
        return
    
    activite = args[0]
    ville = " ".join(args[1:-1]) if len(args) > 2 else args[1]
    email_dest = args[-1] if len(args) > 2 and "@" in args[-1] else VOTRE_EMAIL
    
    if "@" in args[-1]:
        email_dest = args[-1]
        ville = " ".join(args[1:-1])
    
    await update.message.reply_text(
        f"🚀 **Prospection NOVAA V2**\n\n"
        f"🎯 Cible : {activite} à {ville}\n"
        f"📧 Envoi vers : `{email_dest}`\n\n"
        f"⏳ Recherche d'entreprises sans site...",
        parse_mode="Markdown"
    )
    
    entreprises = scraper_entreprises_sans_site(activite, ville)
    
    if not entreprises:
        await update.message.reply_text("❌ Aucune entreprise sans site trouvée.")
        return
    
    entreprises_avec_email = []
    for e in entreprises[:MAX_ENTREPRISES_PAR_SESSION]:
        email = trouver_email(e["nom"])
        if email:
            e["email"] = email
            entreprises_avec_email.append(e)
    
    msg = f"✅ **{len(entreprises_avec_email)} entreprises trouvées !**\n\n"
    for i, e in enumerate(entreprises_avec_email[:10], 1):
        msg += f"{i}. **{e['nom']}** - 📧 {e['email']}\n"
    if len(entreprises_avec_email) > 10:
        msg += f"\n... et {len(entreprises_avec_email) - 10} autres."
    msg += f"\n\n📧 Envoi des emails..."
    await update.message.reply_text(msg, parse_mode="Markdown")
    
    envoyes = 0
    for e in entreprises_avec_email[:MAX_EMAILS_PAR_SESSION]:
        if envoyer_email_brevo(e["email"], e["nom"]):
            envoyes += 1
        time.sleep(2)
    
    await update.message.reply_text(
        f"✅ **Mission terminée !**\n\n"
        f"📊 {len(entreprises)} entreprises trouvées\n"
        f"✉️ {envoyes} emails envoyés à `{email_dest}`\n"
        f"📎 Plaquette : `NOVAA_Commercial_Brochure_2026_EN.pdf`",
        parse_mode="Markdown"
    )

# ============================================
# 🏥 SERVEUR DE SANTÉ POUR RENDER (OBLIGATOIRE)
# ============================================

app_flask = Flask(__name__)

@app_flask.route('/')
def health():
    return "✅ Bot NOVAA V2 is running!", 200

@app_flask.route('/health')
def health_check():
    return "OK", 200

def run_health_server():
    app_flask.run(host='0.0.0.0', port=10000)

# ============================================
# 🚀 LANCEMENT
# ============================================

def main():
    # Démarrer le serveur de santé dans un thread séparé
    threading.Thread(target=run_health_server, daemon=True).start()
    print("🏥 Serveur de santé démarré sur le port 10000")
    
    print("🤖 Agent NOVAA V2 - Démarrage...")
    telecharger_plaquette()
    
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("prospect", prospect))
    
    print("✅ Agent NOVAA V2 prêt !")
    print("🤖 En attente des commandes Telegram...")
    
    app.run_polling()

if __name__ == "__main__":
    main()
