# =============================================================
#  BOÎTE À OUTILS DE CRZ  -  version FENÊTRE
# =============================================================
#  Lancer : double-clic sur ce fichier (.pyw = pas de console noire)
#           ou dans PowerShell :  python boite_a_outils.pyw
#
#  La fenêtre est faite avec "tkinter", la boîte à outils graphique
#  livrée avec Python (rien à installer).
#
#  Rien n'est supprimé ou déplacé sans que tu cliques "Oui".
#
#  Onglet 🔐 Coffre : coffre-fort à mots de passe chiffré (AES-256).
#  Le coffre est rangé dans  C:\Users\<toi>\CoffreFort\coffre.dat
#
#  Onglet ⚙️ Réglages : tout se règle là, sans toucher au code.
#  Tes réglages sont dans  C:\Users\<toi>\BoiteAOutils\reglages.json
# =============================================================

import hashlib
import json
import os
import queue
import re
import secrets
import shutil
import string
import struct
import subprocess
import sys
import threading
import time
from collections import deque
import urllib.request
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font
import ctypes

# Les commandes Windows (netstat, tasklist, powershell...) répondent dans l'encodage "OEM"
# de la console : sans ça, les accents font planter la lecture.
ENCODAGE = "oem" if sys.platform == "win32" else "utf-8"


# =============================================================
#  RÉGLAGES
#  Les valeurs par défaut sont ici. Celles que tu changes dans
#  l'onglet ⚙️ Réglages sont enregistrées dans un fichier JSON
#  (un format texte tout simple pour ranger des données).
# =============================================================

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")
DOSSIER_APPLI = Path.home() / "BoiteAOutils"
FICHIER_REGLAGES = DOSSIER_APPLI / "reglages.json"

VERSION = "2.0.3"
# Les mises à jour sont publiées ici (dépôt GitHub public de Crz)
DEPOT_MAJ = "https://raw.githubusercontent.com/Clrzz/boite-a-outils/main/"

REGLAGES_DEFAUT = {
    "maj_auto": True,            # installe les mises à jour toute seule au démarrage
    "dossier_medal": r"D:\Medal",
    "jours_clips": 30,
    "dossier_a_ranger": str(Path.home() / "Downloads"),
    "alerte_gpu": 83,            # °C
    "alerte_cpu": 90,            # °C (un 13600KF supporte jusqu'à 100 °C)
    "minutes_entre_prix": 30,
    "verrou_minutes": 5,
    "apps_a_fermer": ["OneDrive.exe"],
    "mode_performances": True,   # plan d'alim Performances pendant les parties
    "fermer_vers_icone": True,   # la croix range la fenêtre près de l'horloge
    "demarrage_windows": False,
}
REGLAGES = dict(REGLAGES_DEFAUT)

# Jeux affichés si Steam n'est pas trouvé
JEUX_SECOURS = {
    "ARK Survival Evolved": 346110,
    "Valheim": 892970,
    "Arc Raiders": 1808500,
}


def charger_reglages():
    if FICHIER_REGLAGES.exists():
        try:
            REGLAGES.update(json.loads(FICHIER_REGLAGES.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass   # fichier abîmé : on garde les valeurs par défaut
    appliquer_reglages()


def enregistrer_reglages():
    DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
    FICHIER_REGLAGES.write_text(json.dumps(REGLAGES, indent=2, ensure_ascii=False), encoding="utf-8")
    appliquer_reglages()


def appliquer_reglages():
    """Recopie les réglages dans les variables utilisées par les outils.
    "global" permet de modifier une variable définie en dehors de la fonction."""
    global DOSSIER_MEDAL, JOURS_CLIPS, DOSSIER_A_RANGER, ALERTE_GPU, ALERTE_CPU
    global MINUTES_ENTRE_PRIX, VERROU_MINUTES, APPS_A_FERMER
    DOSSIER_MEDAL = Path(REGLAGES["dossier_medal"])
    JOURS_CLIPS = int(REGLAGES["jours_clips"])
    DOSSIER_A_RANGER = Path(REGLAGES["dossier_a_ranger"])
    ALERTE_GPU = int(REGLAGES["alerte_gpu"])
    ALERTE_CPU = int(REGLAGES["alerte_cpu"])
    MINUTES_ENTRE_PRIX = int(REGLAGES["minutes_entre_prix"])
    VERROU_MINUTES = int(REGLAGES["verrou_minutes"])
    APPS_A_FERMER = list(REGLAGES["apps_a_fermer"])


appliquer_reglages()


def installer_paquets(*paquets):
    """Installe des librairies avec pip, puis les rend utilisables tout de suite."""
    res = subprocess.run([sys.executable, "-m", "pip", "install", "--user", *paquets],
                         capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if res.returncode != 0:
        return False
    import importlib
    import site
    dossier = site.getusersitepackages()
    if dossier not in sys.path:   # le dossier n'existait peut-être pas au lancement
        sys.path.append(dossier)
    importlib.invalidate_caches()
    return True


# --- Lancement au démarrage de Windows ---
# On dépose un petit script .vbs dans le dossier "Démarrage" de Windows :
# tout ce qui s'y trouve est lancé quand tu ouvres ta session.
LANCEUR_DEMARRAGE = Path(APPDATA) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / "BoiteAOutils.vbs"


def regler_demarrage(actif):
    if actif:
        python = Path(sys.executable)
        pythonw = python.with_name("pythonw.exe")   # pythonw = Python sans console
        if pythonw.exists():
            python = pythonw
        script = Path(__file__).resolve()
        contenu = f'CreateObject("WScript.Shell").Run """{python}"" ""{script}"" --cache", 0\r\n'
        LANCEUR_DEMARRAGE.parent.mkdir(parents=True, exist_ok=True)
        LANCEUR_DEMARRAGE.write_text(contenu, encoding="mbcs" if os.name == "nt" else "utf-8")
    elif LANCEUR_DEMARRAGE.exists():
        LANCEUR_DEMARRAGE.unlink()


CATEGORIES = {
    "Images":      [".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"],
    "Videos":      [".mp4", ".mkv", ".mov", ".avi", ".webm"],
    "Musique":     [".mp3", ".wav", ".flac", ".ogg"],
    "Archives":    [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Installeurs": [".exe", ".msi"],
    "Documents":   [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".odt"],
    "Code":        [".py", ".js", ".lua", ".json", ".html", ".css"],
}

# Couleurs du thème sombre (codes hexadécimaux : #RRVVBB)
# Thème « Néon »
FOND = "#07070c"       # fond de la fenêtre
MENU = "#0c0c14"       # barre de menu à gauche
CARTE = "#0f0f19"      # cartes
BORD = "#23233a"       # bordure des cartes
TEXTE = "#e9e9ff"
GRIS = "#8a8aa8"
CYAN = "#00e5ff"
ROSE = "#ff2bd6"
VIOLET = "#8b5cff"
ACCENT = CYAN
VERT = "#3dffa2"
ORANGE = "#ffb648"
ROUGE = "#ff4d6d"
COULEURS_CLAIRES = (CYAN, VERT, ORANGE)   # sur ces couleurs, on écrit en foncé


def texte_sur(couleur):
    """Couleur du texte lisible sur un bouton de cette couleur."""
    return FOND if couleur in COULEURS_CLAIRES else "white"


def espacer(texte):
    """MAJUSCULES avec les lettres un peu écartées (style des petits titres)."""
    return "\u2009".join(texte.upper()).replace("\u2009 \u2009", "   ")


def melanger(c1, c2, t):
    """Couleur entre c1 et c2 (t=0 : c1, t=1 : c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(a, b))


def assombrir(couleur, facteur=0.35):
    """Version sombre d'une couleur (pour faire l'effet « lueur » des courbes)."""
    r, v, b = (int(couleur[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * facteur):02x}{int(v * facteur):02x}{int(b * facteur):02x}"


# =============================================================
#  LA "LOGIQUE" : les mêmes fonctions que la version console,
#  mais elles RENVOIENT des résultats au lieu de faire des print.
#  Séparer la logique de l'affichage, c'est une bonne habitude !
# =============================================================

def taille_lisible(octets):
    for unite in ["o", "Ko", "Mo", "Go"]:
        if octets < 1024:
            return f"{octets:.1f} {unite}"
        octets /= 1024
    return f"{octets:.1f} To"


def taille_dossier(dossier):
    total = 0
    for f in Path(dossier).rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def dossier_temp():
    return Path(os.environ.get("TEMP", "/tmp"))


def vieux_clips():
    """Liste des clips Medal plus vieux que JOURS_CLIPS."""
    if not DOSSIER_MEDAL.exists():
        return []
    limite = time.time() - JOURS_CLIPS * 24 * 3600
    clips = []
    for c in DOSSIER_MEDAL.rglob("*"):
        try:
            if c.is_file() and c.suffix.lower() in (".mp4", ".mkv") and c.stat().st_mtime < limite:
                clips.append(c)
        except OSError:
            pass
    return clips


def vider_temp():
    """Vide le dossier TEMP, renvoie le nombre d'octets libérés."""
    temp = dossier_temp()
    avant = taille_dossier(temp)
    for element in temp.iterdir():
        try:
            if element.is_dir():
                shutil.rmtree(element)
            else:
                element.unlink()
        except OSError:
            pass   # fichier utilisé par une appli : on le laisse
    return avant - taille_dossier(temp)


def vider_dossier(dossier):
    """Supprime le CONTENU d'un dossier (pas le dossier lui-même)."""
    if not Path(dossier).exists():
        return
    for element in Path(dossier).iterdir():
        try:
            if element.is_dir():
                shutil.rmtree(element)
            else:
                element.unlink()
        except OSError:
            pass   # fichier utilisé par une appli : on le laisse


DOSSIER_MAJ_WINDOWS = Path(r"C:\Windows\SoftwareDistribution\Download")


def zones_nettoyage():
    """Une liste de dictionnaires : chaque zone = un truc qu'on peut nettoyer."""
    la, ad = Path(LOCALAPPDATA), Path(APPDATA)
    return [
        {"cle": "temp", "nom": "Fichiers temporaires de Windows", "coche": True,
         "dossiers": [dossier_temp()]},
        {"cle": "discord", "nom": "Cache de Discord (ferme Discord avant)", "coche": True,
         "dossiers": [ad / "discord" / d for d in ("Cache", "Code Cache", "GPUCache")]},
        {"cle": "nvidia", "nom": "Cache de shaders NVIDIA (petits lags au 1er lancement des jeux après)", "coche": False,
         "dossiers": [la / "NVIDIA" / "DXCache", la / "NVIDIA" / "GLCache"]},
        {"cle": "maj", "nom": "Fichiers de mises à jour Windows (Windows demandera l'accès admin)", "coche": False,
         "dossiers": [DOSSIER_MAJ_WINDOWS]},
        {"cle": "medal", "nom": f"Clips Medal de plus de {JOURS_CLIPS} jours", "coche": False,
         "dossiers": []},
    ]


def nettoyer_maj_windows():
    """Le dossier des mises à jour est protégé : on demande l'accès admin
    (la fenêtre bleue de Windows), puis on le vide."""
    import ctypes
    commande = f'/c net stop wuauserv & rd /s /q "{DOSSIER_MAJ_WINDOWS}" & net start wuauserv'
    retour = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", commande, None, 0)
    if retour <= 32:   # refusé ou erreur
        return False
    for _ in range(30):   # on attend jusqu'à 30 s que ce soit fini
        time.sleep(1)
        if not DOSSIER_MAJ_WINDOWS.exists() or not any(DOSSIER_MAJ_WINDOWS.iterdir()):
            break
    return True


def supprimer(fichiers):
    libere = 0
    for f in fichiers:
        try:
            poids = f.stat().st_size
            f.unlink()
            libere += poids
        except OSError:
            pass
    return libere


def lire_gpu():
    try:
        sortie = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=temperature.gpu,utilization.gpu,memory.used,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding=ENCODAGE, errors="replace", timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # pas de console qui clignote
        ).stdout.strip()
        temp, util, vram, watts = [v.strip() for v in sortie.split(",")]
        return round(float(temp)), round(float(util)), round(float(vram)), float(watts)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


# --- Lecture des capteurs de HWiNFO (CPU, disques...) ---
# HWiNFO peut partager ses mesures dans une "mémoire partagée" que les autres
# programmes lisent. Il faut l'activer : Paramètres > "Shared Memory Support".
# On lit cette mémoire avec ctypes (qui permet d'appeler Windows directement).

TYPES_HWINFO = {1: "temp", 7: "usage"}   # 1 = température, 7 = utilisation en %


def decoder_hwinfo(octets):
    """Transforme la mémoire de HWiNFO en liste de capteurs :
    [(nom_du_composant, nom_du_capteur, type, valeur, unité), ...]"""
    (_sig, _ver, _rev, _poll, off_cap, taille_cap, nb_cap,
     off_lect, taille_lect, nb_lect) = struct.unpack_from("<IIIqIIIIII", octets, 0)

    def texte(debut, longueur):
        return octets[debut:debut + longueur].split(b"\0")[0].decode("cp1252", errors="ignore")

    composants = []
    for i in range(nb_cap):
        debut = off_cap + i * taille_cap
        composants.append(texte(debut + 136, 128) or texte(debut + 8, 128))
    capteurs = []
    for i in range(nb_lect):
        debut = off_lect + i * taille_lect
        type_, num_cap = struct.unpack_from("<II", octets, debut)
        nom = texte(debut + 140, 128) or texte(debut + 12, 128)
        valeur = struct.unpack_from("<d", octets, debut + 284)[0]
        composant = composants[num_cap] if num_cap < len(composants) else ""
        unite = texte(debut + 268, 16)
        capteurs.append((composant, nom, TYPES_HWINFO.get(type_, "autre"), valeur, unite))
    return capteurs


def lire_hwinfo():
    """Renvoie la liste des capteurs, ou None si HWiNFO ne partage rien."""
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
    except (ImportError, AttributeError):
        return None   # pas sous Windows
    k32.OpenFileMappingW.restype = ctypes.c_void_p
    k32.MapViewOfFile.restype = ctypes.c_void_p
    k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_size_t]
    k32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    poignee = k32.OpenFileMappingW(4, False, "Global\\HWiNFO_SENS_SM2")   # 4 = lecture seule
    if not poignee:
        return None
    try:
        adresse = k32.MapViewOfFile(poignee, 4, 0, 0, 0)
        if not adresse:
            return None
        try:
            entete = ctypes.string_at(adresse, 44)
            _, _, _, _, off_cap, taille_cap, nb_cap, off_lect, taille_lect, nb_lect = struct.unpack("<IIIqIIIIII", entete)
            taille = max(off_cap + taille_cap * nb_cap, off_lect + taille_lect * nb_lect)
            return decoder_hwinfo(ctypes.string_at(adresse, taille))
        finally:
            k32.UnmapViewOfFile(adresse)
    finally:
        k32.CloseHandle(poignee)



def sorte_capteur(nom):
    """HWiNFO peut être en anglais ou en français : on ramène le nom du capteur à un mot-clé."""
    n = nom.lower()
    if n in ("cpu package", "cpu entier"):
        return "cpu_temp"
    if n in ("total cpu usage",) or n.startswith("utilisation totale du processeur"):
        return "cpu_usage"
    if n in ("drive temperature", "température du disque", "temperature du disque"):
        return "disque_temp"
    if n == "drive remaining life" or "vie restante" in n:
        return "vie"
    if n == "total host writes" or ("écritures" in n and "hôte" in n):
        return "ecrit"
    if n in ("drive failure", "drive warning") or "défaillance" in n or "avertissement du disque" in n:
        return "panne"
    return None

def lire_ram():
    """Renvoie (Go utilisés, Go total) grâce à une fonction de Windows."""
    try:
        import ctypes

        class Memoire(ctypes.Structure):
            _fields_ = [("taille", ctypes.c_ulong), ("charge", ctypes.c_ulong),
                        ("total", ctypes.c_ulonglong), ("libre", ctypes.c_ulonglong),
                        ("a", ctypes.c_ulonglong), ("b", ctypes.c_ulonglong),
                        ("c", ctypes.c_ulonglong), ("d", ctypes.c_ulonglong), ("e", ctypes.c_ulonglong)]
        m = Memoire()
        m.taille = ctypes.sizeof(Memoire)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return (m.total - m.libre) / 1024**3, m.total / 1024**3
    except (ImportError, AttributeError, OSError):
        return None


def compteurs_reseau():
    """Octets reçus / envoyés depuis le démarrage (toutes cartes réseau confondues).
    On demande à la commande Windows "netstat -e"."""
    try:
        sortie = subprocess.run(["netstat", "-e"], capture_output=True, text=True, encoding=ENCODAGE, errors="replace", timeout=5,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    trouve = re.search(r"^\s*(?:Bytes|Octets)\s+(\d+)\s+(\d+)", sortie or "", re.MULTILINE)
    return (int(trouve.group(1)), int(trouve.group(2)), time.time()) if trouve else None


def debit(avant, apres):
    """Deux relevés de compteurs -> (download, upload) en Mbit/s."""
    if not avant or not apres or apres[2] <= avant[2]:
        return None
    def ecart(a, b):
        d = b - a
        return d + 2**32 if d < 0 else d   # le compteur de Windows repart parfois de 0
    secondes = apres[2] - avant[2]
    return (ecart(avant[0], apres[0]) * 8 / secondes / 1e6,
            ecart(avant[1], apres[1]) * 8 / secondes / 1e6)


def lire_tout():
    """Toutes les mesures d'un coup (appelée en arrière-plan toutes les 2 s)."""
    def essayer(fonction):   # si une mesure plante, les autres continuent
        try:
            return fonction()
        except Exception:
            return None
    resultat = {"gpu": essayer(lire_gpu), "ram": essayer(lire_ram), "cpu_temp": None, "cpu_usage": None,
                "disques": [], "reseau": essayer(compteurs_reseau)}
    capteurs = essayer(lire_hwinfo)
    resultat["hwinfo"] = capteurs is not None
    for composant, nom, type_, valeur, *_ in capteurs or []:
        if type_ == "temp" and sorte_capteur(nom) == "cpu_temp":
            resultat["cpu_temp"] = valeur
        elif type_ == "usage" and sorte_capteur(nom) == "cpu_usage":
            resultat["cpu_usage"] = valeur
        elif type_ == "temp" and sorte_capteur(nom) == "disque_temp":
            disque = composant.replace("S.M.A.R.T.: ", "").split("(")[0].strip()
            lettre = re.search(r"\(([A-Z]):", composant)   # HWiNFO écrit souvent « (C:) » dans le nom
            resultat["disques"].append((disque, valeur, lettre.group(1) if lettre else None))
    return resultat


MODELES_LECTEURS = {}


def modeles_lecteurs():
    """{lettre: nom du disque} via PowerShell (une seule fois), pour relier HWiNFO aux lettres."""
    if MODELES_LECTEURS or sys.platform != "win32":
        return MODELES_LECTEURS
    commande = ("Get-Partition | Where-Object DriveLetter | ForEach-Object { \"$($_.DriveLetter)|$((Get-Disk "
                "-Number $_.DiskNumber).FriendlyName)\" }")
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True,
                                encoding=ENCODAGE, errors="replace", timeout=20,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return MODELES_LECTEURS
    for ligne in sortie.splitlines():
        if "|" in ligne:
            lettre, nom = ligne.strip().split("|", 1)
            MODELES_LECTEURS[lettre.strip().upper()] = nom.strip()
    return MODELES_LECTEURS


def lettre_du_disque(modele):
    """Trouve la lettre (C, D...) d'un disque à partir de son nom HWiNFO."""
    mots = {m for m in re.findall(r"[a-z0-9]{4,}", modele.lower())}
    meilleur, score = None, 0
    for lettre, nom in MODELES_LECTEURS.items():
        commun = len(mots & set(re.findall(r"[a-z0-9]{4,}", nom.lower())))
        if commun > score:
            meilleur, score = lettre, commun
    return meilleur


def lecteurs_fixes():
    """[(lettre, taille, libre), ...] pour chaque disque interne (C:, D:, E:...)."""
    lecteurs = []
    if sys.platform != "win32":
        u = shutil.disk_usage("/")
        return [("C", u.total, u.free)]
    modeles_lecteurs()
    masque = ctypes.windll.kernel32.GetLogicalDrives()
    for i in range(26):
        if masque & (1 << i):
            lettre = chr(65 + i)
            if ctypes.windll.kernel32.GetDriveTypeW(f"{lettre}:\\") == 3:   # 3 = disque fixe
                try:
                    u = shutil.disk_usage(f"{lettre}:\\")
                    lecteurs.append((lettre, u.total, u.free))
                except OSError:
                    pass
    return lecteurs


# =============================================================
#  ⬇ MISES À JOUR AUTOMATIQUES
# =============================================================
#  Le fichier version.json du dépôt dit quelle est la dernière version.
#  Si elle est plus récente, on télécharge le nouveau .pyw, on vérifie
#  qu'il est complet et sans faute, puis on remplace celui-ci et on redémarre.

def numero_version(texte):
    return tuple(int(n) for n in re.findall(r"\d+", str(texte)))


def chercher_maj():
    """Renvoie les infos de la nouvelle version, ou None si on est à jour (ou hors ligne)."""
    try:
        requete = urllib.request.Request(DEPOT_MAJ + "version.json?t=" + str(int(time.time())),
                                         headers={"User-Agent": "BoiteAOutils", "Cache-Control": "no-cache"})
        infos = json.loads(urllib.request.urlopen(requete, timeout=10).read().decode("utf-8"))
    except Exception:
        return None
    return infos if numero_version(infos.get("version", "0")) > numero_version(VERSION) else None


def telecharger(nom):
    requete = urllib.request.Request(DEPOT_MAJ + nom + "?t=" + str(int(time.time())),
                                     headers={"User-Agent": "BoiteAOutils", "Cache-Control": "no-cache"})
    return urllib.request.urlopen(requete, timeout=60).read()


def installer_maj(infos):
    """Remplace ce fichier par la nouvelle version. Renvoie un message d'erreur, ou None si tout va bien."""
    code = telecharger("boite_a_outils.pyw")
    if infos.get("sha256") and hashlib.sha256(code).hexdigest() != infos["sha256"]:
        return "le fichier téléchargé est incomplet (réessaie plus tard)"
    try:
        compile(code.decode("utf-8"), "boite_a_outils.pyw", "exec")   # vérifie qu'il n'y a pas de faute
    except (SyntaxError, UnicodeDecodeError) as e:
        return f"la nouvelle version a un problème ({e})"
    ici = Path(__file__).resolve()
    shutil.copy2(ici, ici.with_name(ici.name + ".ancienne"))   # copie de secours
    temporaire = ici.with_name(ici.name + ".nouvelle")
    temporaire.write_bytes(code)
    os.replace(temporaire, ici)
    # Le plugin Stream Deck, s'il a changé
    if infos.get("plugin") and numero_version(infos["plugin"]) > numero_version(REGLAGES.get("plugin_installe", "0")):
        try:
            fichier = DOSSIER_APPLI / "com.crz.capteurs.streamDeckPlugin"
            fichier.write_bytes(telecharger("com.crz.capteurs.streamDeckPlugin"))
            os.startfile(fichier)   # Stream Deck propose de l'installer
            REGLAGES["plugin_installe"] = infos["plugin"]
            enregistrer_reglages()
        except Exception:
            pass
    return None


# --- Jeux Steam installés ---
# Applis Steam qui tournent en fond mais ne sont pas des jeux
PAS_DES_JEUX = ("Crosshair X", "Wallpaper Engine", "Lossless Scaling", "Soundpad", "OBS", "Medal")
MOTS_EXCLUS = ("Steamworks", "Redistributable", "Proton", "Steam Linux Runtime", "SteamVR", "Dedicated Server", "SDK")


def jeux_steam():
    """Lit les fichiers de Steam pour trouver tes jeux installés : {nom: numéro}."""
    try:
        import winreg   # le "registre" de Windows, où Steam note son dossier
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as cle:
            steam = Path(winreg.QueryValueEx(cle, "SteamPath")[0])
    except (ImportError, OSError):
        return {}
    bibliotheques = {steam}   # un "set" : comme une liste, mais sans doublons
    vdf = steam / "steamapps" / "libraryfolders.vdf"   # la liste de tes dossiers de jeux (C:, E:...)
    if vdf.exists():
        for chemin in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            bibliotheques.add(Path(chemin.replace("\\\\", "\\")))
    jeux = {}
    for dossier in bibliotheques:
        for fiche in (dossier / "steamapps").glob("appmanifest_*.acf"):
            texte = fiche.read_text(encoding="utf-8", errors="ignore")
            numero = re.search(r'"appid"\s+"(\d+)"', texte)
            nom = re.search(r'"name"\s+"([^"]+)"', texte)
            if numero and nom and not any(mot in nom.group(1) for mot in MOTS_EXCLUS):
                jeux[nom.group(1)] = int(numero.group(1))
    return dict(sorted(jeux.items(), key=lambda j: j[0].lower()))


# --- Plan d'alimentation ---
def plan_actif():
    """Renvoie l'identifiant (GUID) du plan d'alimentation actuel."""
    sortie = subprocess.run(["powercfg", "/getactivescheme"], capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    trouve = re.search(r"[0-9a-fA-F-]{36}", sortie)
    return trouve.group(0) if trouve else None


def activer_plan(plan):
    """SCHEME_MIN = le plan "Performances élevées" de Windows."""
    res = subprocess.run(["powercfg", "/setactive", plan], capture_output=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return res.returncode == 0


def chemins_applis(noms):
    """Pour chaque appli ouverte de la liste : {nom.exe: chemin}, pour pouvoir la relancer."""
    noms = [n[:-4] if n.lower().endswith(".exe") else n for n in noms]
    noms = [n for n in noms if re.fullmatch(r"[\w .-]+", n)]   # sécurité : que des noms simples
    if not noms:
        return {}
    commande = ("Get-Process -Name " + ",".join(f"'{n}'" for n in noms) +
                " -ErrorAction SilentlyContinue | ForEach-Object { $_.Name + '|' + $_.Path }")
    sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    chemins = {}
    for ligne in sortie.splitlines():
        if "|" in ligne:
            nom, chemin = ligne.split("|", 1)
            if chemin.strip():
                chemins[nom.strip() + ".exe"] = chemin.strip()
    return chemins


# --- Quel jeu tourne en ce moment ? ---
# Jeux hors Steam : début du nom du programme -> nom affiché
AUTRES_JEUX = {
    "fivem": "FiveM (GTA RP)",
    "javaw": "Minecraft",
    "gta5": "GTA V",
}


def jeu_steam_en_cours():
    """Steam note dans le registre le numéro du jeu lancé (0 = aucun)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as cle:
            return int(winreg.QueryValueEx(cle, "RunningAppID")[0])
    except (ImportError, OSError, ValueError):
        return 0


def programmes_ouverts():
    """Noms (en minuscules) des programmes ouverts, via la commande "tasklist"."""
    try:
        sortie = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True, encoding=ENCODAGE, errors="replace", timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [ligne.split('","')[0].strip('"').lower() for ligne in sortie.splitlines() if ligne]


def jeu_en_cours(jeux_connus):
    """Renvoie le nom du jeu lancé, ou None. jeux_connus = {nom: numéro Steam}."""
    numero = jeu_steam_en_cours()
    if numero:
        nom = next((nom for nom, n in jeux_connus.items() if n == numero), None)
        if not (nom and any(mot.lower() in nom.lower() for mot in PAS_DES_JEUX)):
            return nom or f"Jeu Steam n°{numero}"
    for programme in programmes_ouverts():
        for debut, nom in AUTRES_JEUX.items():
            if programme.startswith(debut):
                return nom
    return None


FICHIER_TEMPS = DOSSIER_APPLI / "temps_de_jeu.json"


def charger_temps():
    """{"2026-11-09": {"Valheim": 3600, ...}, ...} en secondes."""
    try:
        temps = json.loads(FICHIER_TEMPS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    for jour in temps.values():   # on retire les applis qui ne sont pas des jeux (Crosshair X...)
        for jeu in [j for j in jour if any(mot.lower() in j.lower() for mot in PAS_DES_JEUX)]:
            del jour[jeu]
    return temps


def duree_lisible(secondes):
    heures, minutes = divmod(int(secondes) // 60, 60)
    return f"{heures} h {minutes:02d}" if heures else f"{minutes} min"


# --- Mises à jour ---
def version_pilote_nvidia():
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                              capture_output=True, text=True, encoding=ENCODAGE, errors="replace", timeout=5,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


PAGE_PILOTES_NVIDIA = "https://www.nvidia.com/fr-fr/drivers/"


def dernier_pilote_nvidia():
    """Demande au site de NVIDIA la dernière version "Game Ready".
    Le même pilote sert à toutes les RTX récentes, donc on pose la question pour une RTX 30/40."""
    url = ("https://gfwsl.geforce.com/services_toolkit/services/com/nvidia/services/AjaxDriverService.php"
           "?func=DriverManualLookup&psid=120&pfid=929&osID=57&languageCode=1036&beta=0&isWHQL=1"
           "&dltype=-1&dch=1&upCRD=0&qnf=0&sort1=0&numberOfResults=1")
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    donnees = json.loads(urllib.request.urlopen(requete, timeout=15).read().decode("utf-8", errors="ignore"))
    infos = donnees["IDS"][0]["downloadInfo"]
    return infos["Version"], urllib.request.unquote(infos.get("DownloadURL", "")) or PAGE_PILOTES_NVIDIA


def applis_a_mettre_a_jour():
    """Demande à winget (le gestionnaire d'applis de Windows) ce qui a une mise à jour.
    Renvoie une liste de dictionnaires {nom, id, version, dispo}."""
    sortie = subprocess.run(["winget", "upgrade", "--accept-source-agreements", "--disable-interactivity"],
                            capture_output=True, timeout=120,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    lignes = [l.split("\r")[-1] for l in sortie.decode("utf-8", errors="ignore").splitlines()]
    return lire_tableau_winget(lignes)


def lire_tableau_winget(lignes):
    """winget affiche un tableau : on repère la position des colonnes grâce à la ligne de titres."""
    for i, ligne in enumerate(lignes):
        if set(ligne.strip()) == {"-"} and i > 0:
            titres = lignes[i - 1]
            debuts = [m.start() for m in re.finditer(r"\S+", titres)]
            if len(debuts) < 4:
                return []
            applis = []
            for l in lignes[i + 1:]:
                if not l.strip() or len(l) < debuts[3]:
                    break   # fin du tableau
                cases = [l[debuts[k]:debuts[k + 1] if k + 1 < len(debuts) else None].strip() for k in range(len(debuts))]
                if cases[1] and cases[3]:
                    applis.append({"nom": cases[0], "id": cases[1], "version": cases[2], "dispo": cases[3]})
            return applis
    return []


def mettre_a_jour(identifiant):
    res = subprocess.run(["winget", "upgrade", "--id", identifiant, "--exact", "--silent",
                          "--accept-package-agreements", "--accept-source-agreements", "--disable-interactivity"],
                         capture_output=True, timeout=900,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return res.returncode == 0


# --- Autres pilotes (Windows Update) et BIOS ---
PAGE_MSI = "https://www.msi.com/Motherboard/PRO-B760-P-DDR4-II/support"


def pilotes_windows_update():
    """Demande à Windows Update quels pilotes sont disponibles mais pas installés.
    (Pas besoin d'être admin pour CHERCHER, seulement pour installer.)"""
    commande = ("$r = (New-Object -ComObject Microsoft.Update.Session).CreateUpdateSearcher()"
                ".Search(\"IsInstalled=0 and Type='Driver'\"); "
                "$r.Updates | ForEach-Object { $_.Title }")
    res = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                         timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if res.returncode != 0:
        raise OSError(res.stderr.strip()[:200] or "Windows Update ne répond pas")
    return [ligne.strip() for ligne in res.stdout.splitlines() if ligne.strip()]


def version_bios():
    """Version et date du BIOS, lues dans le registre (pas besoin d'être admin)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\BIOS") as cle:
            version = winreg.QueryValueEx(cle, "BIOSVersion")[0]
            date = winreg.QueryValueEx(cle, "BIOSReleaseDate")[0]
            return version, date
    except (ImportError, OSError):
        return None


# --- Santé des disques ---
def etat_disques():
    """Infos de Windows (sans droits admin) + infos SMART de HWiNFO si dispo."""
    commande = ("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,HealthStatus,Size | "
                "ConvertTo-Json -Compress")
    sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                            timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
    try:
        brut = json.loads(sortie) if sortie else []
    except ValueError:
        brut = []
    if isinstance(brut, dict):   # un seul disque : PowerShell ne renvoie pas une liste
        brut = [brut]
    disques = []
    for d in brut:
        disques.append({
            "nom": (d.get("FriendlyName") or "Disque").strip(),
            "type": {3: "HDD", 4: "SSD"}.get(d.get("MediaType"), str(d.get("MediaType") or "")),
            "sante": {0: "Healthy", 1: "Warning", 2: "Unhealthy"}.get(d.get("HealthStatus"), d.get("HealthStatus")),
            "taille": d.get("Size") or 0,
            "vie": None, "temp": None, "ecrit": None, "panne": False,
        })
    # HWiNFO : durée de vie restante, température, données écrites
    for composant, nom, type_, valeur, *reste in lire_hwinfo() or []:
        if not composant.startswith("S.M.A.R.T."):
            continue
        modele = composant.replace("S.M.A.R.T.: ", "").split("(")[0].strip().lower()
        cible = next((d for d in disques if modele and (modele in d["nom"].lower() or d["nom"].lower() in modele)), None)
        if cible is None:
            continue
        sorte = sorte_capteur(nom)
        if sorte == "vie":
            cible["vie"] = valeur
        elif sorte == "disque_temp":
            cible["temp"] = valeur
        elif sorte == "ecrit":
            cible["ecrit"] = (valeur, reste[0] if reste else "")
        elif sorte == "panne" and valeur:
            cible["panne"] = True
    return disques


def categorie_de(fichier):
    for categorie, extensions in CATEGORIES.items():
        if fichier.suffix.lower() in extensions:
            return categorie
    return "Autres"


def plan_rangement():
    """Renvoie {catégorie: [fichiers]} pour le dossier à ranger."""
    plan = {}
    if DOSSIER_A_RANGER.exists():
        for f in DOSSIER_A_RANGER.iterdir():
            if f.is_file():
                plan.setdefault(categorie_de(f), []).append(f)
    return plan


def ranger(plan):
    deplaces = 0
    for categorie, liste in plan.items():
        dossier = DOSSIER_A_RANGER / categorie
        dossier.mkdir(exist_ok=True)
        for f in liste:
            cible = dossier / f.name
            n = 1
            while cible.exists():
                cible = dossier / f"{f.stem} ({n}){f.suffix}"
                n += 1
            try:
                shutil.move(str(f), str(cible))
                deplaces += 1
            except OSError:
                pass
    return deplaces


def trouver_prix(url):
    requete = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    page = urllib.request.urlopen(requete, timeout=15).read().decode("utf-8", errors="ignore")
    trouve = re.findall(r'"price"\s*:\s*"?(\d+(?:[.,]\d+)?)', page)
    if not trouve:
        trouve = re.findall(r"(\d{1,3}(?:[ \u00a0\u202f.]?\d{3})*(?:,\d{2})?)\s?€", page)
    prix = []
    for t in trouve:
        t = re.sub(r"[ \u00a0\u202f]", "", t)
        if "," in t:
            t = t.replace(".", "").replace(",", ".")
        try:
            prix.append(float(t))
        except ValueError:
            pass
    prix = [p for p in prix if p > 50]
    return min(prix) if prix else None


# =============================================================
#  LA FENÊTRE
#  Une "classe" regroupe des données et des fonctions qui vont
#  ensemble. Ici : tout ce qui concerne notre fenêtre.
#  (On verra les classes en détail plus tard, pas de panique.)
# =============================================================

def rectangle_arrondi(canvas, x1, y1, x2, y2, r, **options):
    """Dessine un rectangle à coins arrondis (tkinter n'en a pas : on fait un polygone lissé)."""
    points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
              x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(points, smooth=True, **options)


class Carte(tk.Frame):
    """Une carte à coins arrondis.
    Astuce : un Canvas derrière dessine le fond arrondi, et le vrai cadre (self)
    est posé dessus avec une petite marge. On s'en sert comme un Frame normal."""

    RAYON = 22
    MARGE = 6

    def __init__(self, parent, couleur=CARTE, padx=16, pady=12, bordure=BORD):
        fond_parent = parent.cget("bg")
        self.exterieur = tk.Frame(parent, bg=fond_parent)
        self.fond = tk.Canvas(self.exterieur, bg=fond_parent, highlightthickness=0, bd=0)
        self.fond.place(x=0, y=0, relwidth=1, relheight=1)
        super().__init__(self.exterieur, bg=couleur,
                         padx=max(0, padx - self.MARGE), pady=max(0, pady - self.MARGE))
        tk.Frame.pack(self, fill="both", expand=True, padx=self.MARGE, pady=self.MARGE)
        self.couleur, self.bordure = couleur, bordure
        self.fond.bind("<Configure>", self.dessiner)

    def dessiner(self, _evt=None):
        c = self.fond
        c.delete("all")
        l, h = c.winfo_width(), c.winfo_height()
        if l > 4 and h > 4:
            rectangle_arrondi(c, 1, 1, l - 2, h - 2, self.RAYON, fill=self.couleur, outline=self.bordure)

    # Placer la carte = placer le cadre extérieur
    def pack(self, **kw): self.exterieur.pack(**kw)
    pack_configure = pack
    def pack_forget(self): self.exterieur.pack_forget()
    def grid(self, **kw): self.exterieur.grid(**kw)
    grid_configure = grid
    def grid_forget(self): self.exterieur.grid_forget()
    def grid_remove(self): self.exterieur.grid_remove()
    def place(self, **kw): self.exterieur.place(**kw)
    def destroy(self):
        ext = self.exterieur
        super().destroy()
        ext.destroy()


class Navigation:
    """Le menu à gauche : remplace la barre d'onglets.
    Chaque page est un cadre ; on n'affiche que celle qui est choisie."""

    def __init__(self, menu, zone, titre):
        self.menu, self.zone, self.titre = menu, zone, titre
        self.pages = []   # liste de (cadre, nom, ligne du menu)

    def add(self, cadre, text):
        icone, nom = text.split(" ", 1)
        ligne = tk.Frame(self.menu, bg=MENU, cursor="hand2")
        ligne.pack(fill="x", pady=1)
        barre = tk.Frame(ligne, bg=MENU, width=3)
        barre.pack(side="left", fill="y")
        lbl = tk.Label(ligne, text=f"  {icone}   {nom}", bg=MENU, fg=GRIS, font=("Segoe UI", 10),
                       anchor="w", padx=8, pady=5)
        lbl.pack(side="left", fill="x", expand=True)
        index = len(self.pages)
        for w in (ligne, lbl):
            w.bind("<Button-1>", lambda e, i=index: self.select(i))
        self.pages.append((cadre, nom, ligne, barre, lbl))
        if index == 0:
            self.select(0)

    def organiser(self, groupes):
        """Range le menu en groupes avec un petit titre : [("Surveiller", [noms...]), ...]."""
        ordre = [n for _, noms in groupes for n in noms]
        reste = [p for p in self.pages if p[1] not in ordre]
        self.pages = [p for n in ordre for p in self.pages if p[1] == n] + reste
        for p in self.pages:
            p[2].pack_forget()
        position = 0
        for titre, noms in groupes:
            tk.Label(self.menu, text=espacer(titre), bg=MENU, fg="#55557a", font=("Segoe UI", 7, "bold"),
                     anchor="w").pack(fill="x", padx=22, pady=(10, 2))
            for _ in noms:
                if position < len(self.pages):
                    self.pages[position][2].pack(fill="x", pady=0)
                    position += 1
        for p in self.pages[position:]:
            p[2].pack(fill="x", pady=0)
        for i, p in enumerate(self.pages):
            for w in (p[2], p[4]):
                w.bind("<Button-1>", lambda e, i=i: self.select(i))

    def deplacer(self, nom, apres):
        """Change la place d'une page dans le menu."""
        page = next(p for p in self.pages if p[1] == nom)
        self.pages.remove(page)
        position = next(i for i, p in enumerate(self.pages) if p[1] == apres) + 1
        self.pages.insert(position, page)
        for p in self.pages:   # on réaffiche les lignes du menu dans le bon ordre
            p[2].pack_forget()
        for i, p in enumerate(self.pages):
            p[2].pack(fill="x", pady=1)
            for w in (p[2], p[4]):
                w.bind("<Button-1>", lambda e, i=i: self.select(i))

    def select(self, index):
        for i, (cadre, nom, ligne, barre, lbl) in enumerate(self.pages):
            actif = i == index
            fond = "#0d1b24" if actif else MENU   # fond légèrement cyan pour la page active
            ligne.config(bg=fond)
            lbl.config(bg=fond, fg="white" if actif else GRIS)
            barre.config(bg=CYAN if actif else MENU)
            if actif:
                cadre.pack(fill="both", expand=True)
                self.titre.config(text=nom)
            else:
                cadre.pack_forget()


class BoiteAOutils:

    def __init__(self, racine, cache=False):
        self.racine = racine
        self.icone = None                 # l'icône près de l'horloge
        self.file_icone = queue.Queue()   # messages venant de l'icône (autre "fil")
        self.session = None               # infos de la session gaming en cours
        racine.title("Boîte à outils de Crz")
        racine.geometry("1080x720")
        racine.minsize(980, 660)
        racine.configure(bg=FOND)
        self.style()

        # Menu à gauche
        menu = tk.Frame(racine, bg=MENU, width=210)
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False)   # garde la largeur fixe
        logo = tk.Canvas(menu, bg=MENU, height=74, highlightthickness=0)
        logo.pack(fill="x", padx=(18, 0), pady=(16, 4))
        police = ("Segoe UI", 19, "bold")
        logo.create_text(2, 4, text="⚡", fill=CYAN, anchor="nw", font=police)
        logo.create_text(34, 4, text="CRZ", fill=CYAN, anchor="nw", font=police)
        x = 2
        mesure = tk.font.Font(font=police)
        mot = "TOOLBOX"
        for i, lettre in enumerate(mot):   # chaque lettre un peu plus violette : effet dégradé
            logo.create_text(x, 38, text=lettre, fill=melanger(CYAN, VIOLET, i / (len(mot) - 1)), anchor="nw", font=police)
            x += mesure.measure(lettre) + 1
        tk.Frame(racine, bg=BORD, width=1).pack(side="left", fill="y")   # trait de séparation

        # Zone principale : titre de la page + la page
        principale = tk.Frame(racine, bg=FOND, padx=24, pady=18)
        principale.pack(side="left", fill="both", expand=True)
        entete = tk.Frame(principale, bg=FOND)
        entete.pack(fill="x", pady=(0, 12))
        titre = tk.Label(entete, text="", bg=FOND, fg=TEXTE, font=("Segoe UI", 20, "bold"), anchor="w")
        titre.pack(side="left")
        self.pastille = tk.Label(entete, text="…", bg=FOND, fg=GRIS, font=("Segoe UI", 10, "bold"), padx=12, pady=3)
        self.pastille.pack(side="left", padx=(14, 0))
        self.bouton_maj_appli = tk.Button(entete, text="", relief="flat", bg=CYAN, fg=FOND, activebackground=VERT,
                                 font=("Segoe UI", 10, "bold"), cursor="hand2", padx=12, bd=0, highlightthickness=0,
                                 command=self.lancer_maj_appli)
        self.horloge = tk.Label(entete, text="", bg=FOND, fg=GRIS, font=("Segoe UI", 10))
        self.horloge.pack(side="right", padx=(10, 0))
        self.maj_horloge()
        zone = tk.Frame(principale, bg=FOND)
        zone.pack(fill="both", expand=True)

        onglets = Navigation(menu, zone, titre)
        self.demarrer_serveur()   # pour le téléphone et le Stream Deck
        self.onglet_rapport(self.nouvel_onglet(onglets, "📊 Rapport"))   # créé en 1er (les stats servent partout)
        self.onglet_gpu(self.nouvel_onglet(onglets, "◉ Tableau de bord", carte=False))
        self.onglet_profils(self.nouvel_onglet(onglets, "🎛 Profils"))
        self.onglet_soundboard(self.nouvel_onglet(onglets, "🔊 Soundboard"))
        self.onglet_nettoyeur(self.nouvel_onglet(onglets, "🧹 Nettoyer"))
        self.onglet_gaming(self.nouvel_onglet(onglets, "🎮 Gaming"))
        self.onglet_temps_de_jeu(self.nouvel_onglet(onglets, "⏱ Temps de jeu"))
        self.onglet_sante(self.nouvel_onglet(onglets, "🩺 Santé du PC"))
        self.onglet_rangeur(self.nouvel_onglet(onglets, "📂 Ranger"))
        self.onglet_prix(self.nouvel_onglet(onglets, "🔔 Alerte prix"))
        self.coffre = Coffre(self.nouvel_onglet(onglets, "🔐 Coffre-fort"), racine)
        self.onglet_telephone(self.nouvel_onglet(onglets, "📱 Téléphone"))
        self.onglet_reglages(self.nouvel_onglet(onglets, "⚙ Réglages"))
        onglets.organiser([("Surveiller", ["Tableau de bord", "Santé du PC", "Rapport", "Temps de jeu"]),
                           ("Agir", ["Nettoyer", "Gaming", "Profils", "Soundboard", "Ranger"]),
                           ("Outils", ["Coffre-fort", "Alerte prix", "Téléphone", "Réglages"])])
        onglets.select(0)
        tk.Label(menu, text=f"v{VERSION}", bg=MENU, fg="#44445e", font=("Segoe UI", 8)).pack(side="bottom", pady=8)
        self.maj_dispo = None
        self.racine.after(8000, lambda: self.verifier_maj_appli(au_demarrage=True))
        self.navigation = onglets

        racine.protocol("WM_DELETE_WINDOW", self.fermer)   # clic sur la croix
        self.lire_file_icone()
        if cache:   # lancé au démarrage de Windows : direct près de l'horloge
            if self.creer_icone(demander=False):
                racine.withdraw()
            else:
                racine.iconify()

    # ---------- icône près de l'horloge ----------

    def creer_icone(self, demander=True):
        """Crée l'icône avec pystray (+ Pillow pour dessiner l'image)."""
        if self.icone:
            return True
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            if not demander or not messagebox.askyesno(
                    "Icône près de l'horloge",
                    "Pour se ranger près de l'horloge, il faut 2 petites librairies (pystray et Pillow).\n\n"
                    "Les installer maintenant ? (environ 30 secondes)"):
                return False
            if not installer_paquets("pystray", "pillow"):
                messagebox.showerror("Oups", "Installation ratée. Dans PowerShell :\npython -m pip install pystray pillow")
                return False
            import pystray
            from PIL import Image, ImageDraw

        # On dessine l'icône : une petite caisse à outils bleue
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(image)
        d.rounded_rectangle([4, 20, 60, 58], radius=8, fill=ACCENT)
        d.rounded_rectangle([22, 8, 42, 24], radius=5, outline=ACCENT, width=5)
        d.rectangle([4, 34, 60, 38], fill=FOND)

        envoyer = self.file_icone.put   # l'icône tourne dans un autre fil : elle passe par la file
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir", lambda: envoyer("ouvrir"), default=True),
            pystray.MenuItem("Quitter", lambda: envoyer("quitter")),
        )
        try:
            self.icone = pystray.Icon("boite_a_outils", image, "Boîte à outils de Crz", menu)
            self.icone.run_detached()
        except Exception:   # icône impossible sur ce PC : on fera sans
            self.icone = None
            return False
        return True

    def lire_file_icone(self):
        """Toutes les 200 ms, on regarde si l'icône nous a demandé quelque chose."""
        try:
            while True:
                ordre = self.file_icone.get_nowait()
                if ordre == "ouvrir":
                    self.montrer()
                elif ordre == "quitter":
                    self.quitter()
                    return
                elif isinstance(ordre, tuple) and ordre[0] == "profil":
                    self.activer_profil(ordre[1])
                elif isinstance(ordre, tuple) and ordre[0] == "micro":
                    self.afficher_micro()
        except queue.Empty:
            pass
        self.racine.after(200, self.lire_file_icone)

    def montrer(self):
        self.racine.deiconify()
        self.racine.lift()
        self.racine.focus_force()

    def fermer(self):
        if not REGLAGES["fermer_vers_icone"]:
            self.quitter()
        elif self.creer_icone():
            if self.coffre.mdp_maitre:   # sécurité : on verrouille le coffre en cachant la fenêtre
                self.coffre.verrouiller()
            self.racine.withdraw()
        else:
            self.racine.iconify()   # pas d'icône possible : on réduit dans la barre des tâches

    def quitter(self):
        if self.session:
            self.fin_session()   # remet le plan d'alim et les applis
        if self.icone:
            self.icone.stop()
        if getattr(self, "serveur", None):
            self.serveur.shutdown()
        self.racine.destroy()

    # ---------- petits outils d'affichage ----------

    def style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TNotebook", background=FOND, borderwidth=0)
        s.configure("TNotebook.Tab", background=CARTE, foreground=GRIS,
                    padding=(8, 6), font=("Segoe UI", 10))
        # Style de la liste du coffre-fort
        s.configure("Treeview", background=FOND, fieldbackground=FOND, foreground=TEXTE,
                    rowheight=26, font=("Segoe UI", 10), borderwidth=0)
        s.configure("Treeview.Heading", background=CARTE, foreground=GRIS,
                    font=("Segoe UI", 10, "bold"), relief="flat")
        s.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", FOND)])
        s.configure("TCombobox", fieldbackground=FOND, background=CARTE, foreground=TEXTE, arrowcolor=CYAN,
                    bordercolor=BORD, lightcolor=BORD, darkcolor=BORD)
        s.map("TCombobox", fieldbackground=[("readonly", FOND)], foreground=[("readonly", TEXTE)],
              selectbackground=[("readonly", FOND)], selectforeground=[("readonly", TEXTE)])
        self.racine.option_add("*TCombobox*Listbox.background", CARTE)
        self.racine.option_add("*TCombobox*Listbox.foreground", TEXTE)
        self.racine.option_add("*TCombobox*Listbox.selectBackground", CYAN)
        self.racine.option_add("*TCombobox*Listbox.selectForeground", FOND)
        s.map("TNotebook.Tab", background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

    def nouvel_onglet(self, onglets, nom, carte=True):
        if carte:   # page posée dans une grande carte avec bordure
            cadre = Carte(onglets.zone, padx=20, pady=16)
        else:
            cadre = tk.Frame(onglets.zone, bg=FOND)
        onglets.add(cadre, text=nom)
        return cadre

    def carte(self, parent):
        """Une petite carte sombre avec une bordure fine."""
        return Carte(parent)

    def etiquette(self, parent, texte):
        """Petit titre gris en majuscules, style néon."""
        lbl = tk.Label(parent, text=espacer(texte), bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        lbl.pack(fill="x")
        return lbl

    def jauge(self, parent, couleur):
        """Une barre de progression fine (un Canvas) ; renvoie une fonction pour la remplir."""
        c = tk.Canvas(parent, height=14, width=1, bg=CARTE, highlightthickness=0)
        c.pack(fill="x", pady=(8, 0))

        def remplir(fraction, teinte=couleur):
            c.delete("all")
            larg = max(c.winfo_width(), 50)
            fin = 7 + (larg - 14) * max(0, min(1, fraction))
            c.create_line(7, 7, larg - 7, 7, fill="#1c1c2c", width=7, capstyle="round")
            if fraction > 0:
                c.create_line(7, 7, fin, 7, fill=melanger(CARTE, teinte, 0.25), width=13, capstyle="round")   # lueur
                c.create_line(7, 7, fin, 7, fill=teinte, width=7, capstyle="round")
        return remplir

    def texte(self, parent, contenu="", taille=10, couleur=TEXTE, gras=False):
        lbl = tk.Label(parent, text=contenu, bg=CARTE, fg=couleur, justify="left",
                       anchor="w", font=("Segoe UI", taille, "bold" if gras else "normal"))
        lbl.pack(fill="x", pady=2)
        return lbl

    def bouton(self, parent, contenu, action, couleur=ACCENT):
        btn = tk.Button(parent, text=contenu, command=action, bg=couleur, fg=texte_sur(couleur),
                        activebackground=couleur, activeforeground=texte_sur(couleur), relief="flat",
                        font=("Segoe UI", 10, "bold"), padx=14, pady=6, cursor="hand2")
        btn.pack(anchor="w", pady=6)
        return btn

    def en_fond(self, travail, ensuite):
        """Lance `travail` en arrière-plan (la fenêtre ne gèle pas),
        puis appelle `ensuite(resultat)` quand c'est fini."""
        boite = {}

        def executer():
            try:
                boite["res"] = travail()
            except Exception as e:
                boite["res"] = e
        fil = threading.Thread(target=executer, daemon=True)
        fil.start()

        def verifier():
            if fil.is_alive():
                self.racine.after(100, verifier)   # on revérifie dans 100 ms
            else:
                ensuite(boite.get("res"))
        verifier()

    # ---------- 🧹 NETTOYEUR ----------

    def onglet_nettoyeur(self, cadre):
        self.texte(cadre, "Nettoyer le PC", 13, gras=True)
        self.texte(cadre, "Coche ce que tu veux nettoyer, puis Analyser pour voir la place gagnée.", couleur=GRIS)
        self.cadre_zones = tk.Frame(cadre, bg=CARTE)
        self.cadre_zones.pack(fill="x", pady=4)
        self.construire_zones()
        boutons = tk.Frame(cadre, bg=CARTE)
        boutons.pack(fill="x")
        self.bouton(boutons, "🔍 Analyser", self.analyser).pack(side="left", padx=(0, 8))
        self.btn_nettoyer = self.bouton(boutons, "🧹 Nettoyer", self.nettoyer, VERT)
        self.btn_nettoyer.pack(side="left")
        self.btn_nettoyer.config(state="disabled")
        self.resultat_nettoyage = self.texte(cadre, "", 11, VERT, True)

    def construire_zones(self):
        """(Re)crée une case à cocher par zone de nettoyage."""
        for w in self.cadre_zones.winfo_children():
            w.destroy()
        self.zones = zones_nettoyage()
        self.clips = []
        for zone in self.zones:
            zone["var"] = tk.BooleanVar(value=zone["coche"])
            zone["case"] = tk.Checkbutton(self.cadre_zones, text=zone["nom"], variable=zone["var"],
                                          bg=CARTE, fg=TEXTE, selectcolor=FOND, activebackground=CARTE,
                                          activeforeground=TEXTE, font=("Segoe UI", 10), anchor="w",
                                          highlightthickness=0, bd=0)
            zone["case"].pack(fill="x", pady=1)
            zone["taille"] = 0

    def analyser(self):
        self.resultat_nettoyage.config(text="Analyse en cours...", fg=GRIS)

        def travail():
            tailles = {}
            for zone in self.zones:
                if zone["cle"] == "medal":
                    clips = vieux_clips()
                    tailles["medal"] = (sum(c.stat().st_size for c in clips), clips)
                else:
                    tailles[zone["cle"]] = (sum(taille_dossier(d) for d in zone["dossiers"] if d.exists()), None)
            return tailles

        def ensuite(tailles):
            if isinstance(tailles, Exception):
                self.resultat_nettoyage.config(text=f"Erreur : {tailles}", fg=ROUGE)
                return
            for zone in self.zones:
                zone["taille"], clips = tailles[zone["cle"]]
                texte = f"{zone['nom']}  →  {taille_lisible(zone['taille'])}"
                if zone["cle"] == "medal":
                    self.clips = clips
                    texte = (f"{zone['nom']}  →  {len(clips)} clips, {taille_lisible(zone['taille'])}"
                             if DOSSIER_MEDAL.exists() else f"{zone['nom']}  →  dossier {DOSSIER_MEDAL} introuvable")
                zone["case"].config(text=texte)
            self.resultat_nettoyage.config(text="")
            self.btn_nettoyer.config(state="normal")
        self.en_fond(travail, ensuite)

    def nettoyer(self):
        choisies = [z for z in self.zones if z["var"].get()]
        if not choisies:
            return
        liste = "\n".join(f"• {z['nom'].split(' (')[0]} : {taille_lisible(z['taille'])}" for z in choisies)
        if not messagebox.askyesno("Nettoyer", f"Je nettoie :\n\n{liste}\n\nOn y va ?"):
            return
        self.resultat_nettoyage.config(text="Nettoyage en cours...", fg=GRIS)

        def travail():
            libere = 0
            for zone in choisies:
                if zone["cle"] == "medal":
                    libere += supprimer(self.clips)
                elif zone["cle"] == "maj":
                    if nettoyer_maj_windows():
                        libere += zone["taille"]
                else:
                    avant = sum(taille_dossier(d) for d in zone["dossiers"])
                    for d in zone["dossiers"]:
                        vider_dossier(d)
                    libere += avant - sum(taille_dossier(d) for d in zone["dossiers"])
            return libere

        def ensuite(libere):
            if isinstance(libere, Exception):
                self.resultat_nettoyage.config(text=f"Erreur : {libere}", fg=ROUGE)
                return
            self.resultat_nettoyage.config(text=f"✅ {taille_lisible(libere)} libérés !", fg=VERT)
            self.noter("nettoye", libere, "somme")
            self.analyser()
        self.en_fond(travail, ensuite)

    # ---------- 🌡️ TEMPÉRATURES ----------

    def tuile(self, parent, titre):
        """Une case avec un titre, une grosse température et des détails."""
        cadre = tk.Frame(parent, bg=FOND, padx=14, pady=10)
        cadre.pack(side="left", fill="both", expand=True, padx=4)
        tk.Label(cadre, text=titre, bg=FOND, fg=GRIS, font=("Segoe UI", 10, "bold")).pack()
        temp = tk.Label(cadre, text="-- °C", bg=FOND, fg=VERT, font=("Segoe UI", 34, "bold"))
        temp.pack()
        details = tk.Label(cadre, text="", bg=FOND, fg=TEXTE, font=("Segoe UI", 10), justify="center")
        details.pack()
        return temp, details

    def tuile(self, parent, titre, couleur):
        """Une tuile de mesure : titre + état, grosse valeur + unité, détail, jauge."""
        c = Carte(parent, padx=14, pady=10)
        haut = tk.Frame(c, bg=CARTE)
        haut.pack(fill="x")
        tk.Label(haut, text=espacer(titre), bg=CARTE, fg=GRIS, font=("Segoe UI", 8)).pack(side="left")
        etat = tk.Label(haut, text="", bg=CARTE, fg=VERT, font=("Segoe UI", 8, "bold"))
        etat.pack(side="right")
        ligne = tk.Frame(c, bg=CARTE)
        ligne.pack(fill="x", pady=(2, 0))
        valeur = tk.Label(ligne, text="--", bg=CARTE, fg=couleur, font=("Segoe UI", 26, "bold"))
        valeur.pack(side="left")
        unite = tk.Label(ligne, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 11, "bold"))
        unite.pack(side="left", anchor="s", pady=(0, 8), padx=(2, 0))
        detail = tk.Label(c, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        detail.pack(fill="x")
        return c, {"etat": etat, "valeur": valeur, "unite": unite, "detail": detail,
                   "jauge": self.jauge(c, couleur), "couleur": couleur}

    def remplir_tuile(self, t, valeur, unite, detail, fraction, etat, couleur_etat, couleur_valeur=None):
        t["valeur"].config(text=valeur, fg=couleur_valeur or t["couleur"])
        t["unite"].config(text=unite)
        t["detail"].config(text=detail)
        t["etat"].config(text=espacer(etat), fg=couleur_etat)
        t["jauge"](fraction, couleur_valeur or t["couleur"])

    def action_rapide(self, parent, icone, titre, couleur, commande):
        """Un gros bouton : icône colorée + titre + petite info à droite. Renvoie le label de l'info."""
        fond, survol = "#15152a", "#1d1d36"
        b = tk.Frame(parent, bg=fond, highlightthickness=1, highlightbackground=BORD, cursor="hand2", padx=10, pady=7)
        b.pack(fill="x", pady=3)
        ic = tk.Label(b, text=icone, bg=melanger(fond, couleur, 0.22), fg=TEXTE, font=("Segoe UI", 11), width=2)
        ic.pack(side="left")
        nom = tk.Label(b, text=titre, bg=fond, fg=TEXTE, font=("Segoe UI", 10, "bold"))
        nom.pack(side="left", padx=(10, 0))
        info = tk.Label(b, text="", bg=fond, fg=GRIS, font=("Segoe UI", 9))
        info.pack(side="right")
        widgets = (b, nom, info)

        def teinte(couleur_fond):
            for w in widgets:
                w.config(bg=couleur_fond)
        for w in (b, ic, nom, info):
            w.bind("<Button-1>", lambda e: commande())
            w.bind("<Enter>", lambda e: teinte(survol))
            w.bind("<Leave>", lambda e: teinte(fond))
        return info

    def aller_a(self, nom):
        """Ouvre une page du menu par son nom."""
        noms = [p[1] for p in self.navigation.pages]
        if nom in noms:
            self.navigation.select(noms.index(nom))

    def mode_jeu(self):
        if "Jeu" in REGLAGES.get("profils", {}):
            self.activer_profil("Jeu")
        else:
            self.aller_a("Gaming")

    def menu_profils(self, evt=None):
        menu = tk.Menu(self.racine, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=CYAN, activeforeground=FOND)
        for nom, p in REGLAGES.get("profils", {}).items():
            coche = "✓ " if nom == REGLAGES.get("profil_actif") else "    "
            menu.add_command(label=f"{coche}{p.get('icone', '')} {nom}", command=lambda n=nom: self.activer_profil(n))
        menu.add_separator()
        menu.add_command(label="Modifier les profils…", command=lambda: self.aller_a("Profils"))
        x, y = self.racine.winfo_pointerxy()
        menu.tk_popup(x, y)

    def onglet_gpu(self, cadre):
        """Le tableau de bord : tout le PC sur un écran, clair et lisible."""
        # Ligne 1 : quatre tuiles de mesures
        ligne1 = tk.Frame(cadre, bg=FOND)
        ligne1.pack(fill="x")
        self.tuiles = {}
        for col, (cle, titre, couleur) in enumerate((("cpu", "Processeur", CYAN), ("gpu", "Graphique", ROSE),
                                                      ("ram", "Mémoire", TEXTE), ("net", "Connexion", TEXTE))):
            ligne1.columnconfigure(col, weight=1, uniform="tuile")
            carte, self.tuiles[cle] = self.tuile(ligne1, titre, couleur)
            carte.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5))
        self.tuiles["ram"]["jauge_couleur"] = VIOLET
        self.tuiles["net"]["jauge_couleur"] = VERT

        # Ligne 2 : graphique + actions rapides
        ligne2 = tk.Frame(cadre, bg=FOND)
        ligne2.pack(fill="both", expand=True, pady=10)
        ligne2.columnconfigure(0, weight=1)
        ligne2.rowconfigure(0, weight=1)
        graph = Carte(ligne2, padx=14, pady=10)
        graph.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tete = tk.Frame(graph, bg=CARTE)
        tete.pack(fill="x")
        tk.Label(tete, text=espacer("Températures · 10 dernières minutes"), bg=CARTE, fg=GRIS,
                 font=("Segoe UI", 8)).pack(side="left")
        self.legende_alerte = tk.Label(tete, text="", bg=CARTE, fg=ORANGE, font=("Segoe UI", 8, "bold"))
        self.legende_alerte.pack(side="right")
        tk.Label(tete, text="● GPU   ", bg=CARTE, fg=ROSE, font=("Segoe UI", 8, "bold")).pack(side="right")
        tk.Label(tete, text="● CPU   ", bg=CARTE, fg=CYAN, font=("Segoe UI", 8, "bold")).pack(side="right")
        self.graphique = tk.Canvas(graph, bg=CARTE, height=170, width=1, highlightthickness=0)
        self.graphique.pack(fill="both", expand=True, pady=(6, 0))
        self.graphique.bind("<Configure>", lambda e: self.dessiner_graphique())
        self.astuce_hwinfo = tk.Label(graph, text="", bg=CARTE, fg=ORANGE, font=("Segoe UI", 9), anchor="w",
                                      justify="left", wraplength=560)
        self.astuce_hwinfo.pack(fill="x")
        self.historique = {"cpu": deque(maxlen=300), "gpu": deque(maxlen=300)}

        actions = Carte(ligne2, padx=12, pady=10)
        actions.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        actions.exterieur.config(width=228)
        tk.Label(actions, text=espacer("Actions rapides"), bg=CARTE, fg=GRIS, font=("Segoe UI", 8),
                 anchor="w").pack(fill="x", pady=(0, 4))
        self.info_mode_jeu = self.action_rapide(actions, "🎮", "Mode jeu", CYAN, self.mode_jeu)
        self.info_mode_jeu.config(text="profil Jeu")
        self.action_rapide(actions, "🧹", "Nettoyer", VERT, lambda: self.aller_a("Nettoyer")).config(text="ouvrir ›")
        self.info_micro = self.action_rapide(actions, "🎙", "Micro", ROSE, self.basculer_micro)
        self.info_profil_dash = self.action_rapide(actions, "🎛", "Profil", VIOLET, self.menu_profils)

        # Ligne 3 : disques, jeu, musique
        ligne3 = tk.Frame(cadre, bg=FOND)
        ligne3.pack(fill="x")
        for col, poids in enumerate((6, 5, 6)):
            ligne3.columnconfigure(col, weight=poids, uniform="bas")

        disques = Carte(ligne3, padx=14, pady=10)
        disques.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        tete = tk.Frame(disques, bg=CARTE)
        tete.pack(fill="x")
        tk.Label(tete, text=espacer("Disques"), bg=CARTE, fg=GRIS, font=("Segoe UI", 8)).pack(side="left")
        self.dash_disques = tk.Label(tete, text="", bg=CARTE, fg=VERT, font=("Segoe UI", 8, "bold"))
        self.dash_disques.pack(side="right")
        self.cadre_dash_disques = tk.Frame(disques, bg=CARTE)
        self.cadre_dash_disques.pack(fill="x", pady=(4, 0))
        self.lignes_disques = {}

        jeu = Carte(ligne3, padx=14, pady=10)
        jeu.grid(row=0, column=1, sticky="nsew", padx=5)
        tk.Label(jeu, text=espacer("Jeu"), bg=CARTE, fg=GRIS, font=("Segoe UI", 8), anchor="w").pack(fill="x")
        self.dash_jeu = tk.Label(jeu, text="Aucun jeu", bg=CARTE, fg=GRIS, font=("Segoe UI", 14, "bold"), anchor="w")
        self.dash_jeu.pack(fill="x", pady=(4, 2))
        self.dash_semaine = tk.Label(jeu, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        self.dash_semaine.pack(fill="x")
        self.dash_top = tk.Label(jeu, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        self.dash_top.pack(fill="x")

        musique = Carte(ligne3, padx=14, pady=10)
        musique.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
        tk.Label(musique, text=espacer("Musique · Spotify"), bg=CARTE, fg=GRIS, font=("Segoe UI", 8),
                 anchor="w").pack(fill="x")
        self.dash_musique = tk.Label(musique, text="Rien en lecture", bg=CARTE, fg=GRIS, font=("Segoe UI", 11, "bold"),
                                     anchor="w")
        self.dash_musique.pack(fill="x", pady=(4, 0))
        self.dash_artiste = tk.Label(musique, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        self.dash_artiste.pack(fill="x")
        boutons = tk.Frame(musique, bg=CARTE)
        boutons.pack(fill="x", pady=(6, 0))
        for col, (symbole, action) in enumerate((("⏮", "precedent"), ("⏯", "playpause"), ("⏭", "suivant"),
                                                 ("🔉", "volmoins"), ("🔊", "volplus"))):
            boutons.columnconfigure(col, weight=1, uniform="m")
            tk.Button(boutons, text=symbole, relief="flat", bg="#15152a", fg=CYAN, activebackground=CYAN,
                      activeforeground=FOND, font=("Segoe UI", 10), cursor="hand2", bd=0, highlightthickness=0,
                      command=lambda a=action: touche_media(a)).grid(row=0, column=col, sticky="ew", padx=2, ipady=2)

        # (ancien bouton micro : gardé invisible pour la compatibilité)
        self.btn_micro = tk.Button(cadre)
        self.titre_musique = None
        self.micro_coupe = None
        self.temps_disques = []
        self.racine.after(1500, self.suivre_musique)
        self.max = {"cpu": 0, "gpu": 0}
        self.dernier_reseau = None
        self.max_down = 0
        self.racine.after(500, self.maj_temperatures)
        self.racine.after(800, self.maj_disques_dash)

    def maj_disques_dash(self):
        """Place libre + température de chaque disque (toutes les 30 s)."""
        def ensuite(lecteurs):
            if isinstance(lecteurs, Exception):
                lecteurs = []
            temps = {}
            for modele, t, lettre in self.temps_disques:
                lettre = lettre or lettre_du_disque(modele)
                if lettre:
                    temps.setdefault(lettre, t)
            a_surveiller = 0
            for lettre, total, libre in lecteurs:
                if lettre not in self.lignes_disques:
                    l = tk.Frame(self.cadre_dash_disques, bg=CARTE)
                    l.pack(fill="x", pady=2)
                    tk.Label(l, text=f"{lettre}:", bg=CARTE, fg=TEXTE, font=("Segoe UI", 9, "bold"), width=3,
                             anchor="w").pack(side="left")
                    texte = tk.Label(l, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), width=17, anchor="e")
                    texte.pack(side="right")
                    barre = tk.Canvas(l, height=8, width=1, bg=CARTE, highlightthickness=0)
                    barre.pack(side="left", fill="x", expand=True, padx=(2, 8))
                    self.lignes_disques[lettre] = (barre, texte)
                barre, texte = self.lignes_disques[lettre]
                rempli = 1 - libre / total if total else 0
                temp = temps.get(lettre)
                couleur = ROUGE if rempli > 0.95 or (temp or 0) >= 70 else (ORANGE if rempli > 0.85 or (temp or 0) >= 60 else CYAN)
                a_surveiller += couleur != CYAN
                texte.config(text=f"{libre / 1e9:,.0f} Go libres".replace(",", " ") + (f" · {temp:.0f}°" if temp else ""))
                barre.delete("all")
                larg = max(barre.winfo_width(), 60)
                barre.create_line(4, 4, larg - 4, 4, fill="#1c1c2c", width=6, capstyle="round")
                barre.create_line(4, 4, 4 + (larg - 8) * rempli, 4, fill=couleur, width=6, capstyle="round")
            self.disques_a_surveiller = a_surveiller
            if lecteurs and not getattr(self, "sante_disques_connue", False):
                ok = len(lecteurs) - a_surveiller
                self.dash_disques.config(text=espacer(f"{ok} / {len(lecteurs)} OK"), fg=VERT if not a_surveiller else ORANGE)
            self.racine.after(30000, self.maj_disques_dash)
        self.en_fond(lecteurs_fixes, ensuite)

    def maj_temperatures(self):
        def ensuite(m):
            if isinstance(m, Exception):
                m = {"gpu": None, "ram": None, "cpu_temp": None, "cpu_usage": None, "disques": [], "hwinfo": False,
                     "reseau": None}
            soucis = []
            t = self.tuiles
            # Processeur (température via HWiNFO)
            if m["cpu_temp"] is not None:
                temp = m["cpu_temp"]
                self.max["cpu"] = max(self.max["cpu"], temp)
                etat, couleur = self.etat_temperature(temp, ALERTE_CPU)
                if couleur != VERT:
                    soucis.append(f"CPU {etat.lower()}")
                charge = f"Charge {m['cpu_usage']:.0f} % · " if m["cpu_usage"] is not None else ""
                self.remplir_tuile(t["cpu"], f"{temp:.0f}", "°C", f"{charge}max {self.max['cpu']:.0f} °C",
                                   temp / 100, etat, couleur, ROUGE if couleur == ROUGE else None)
            else:
                charge = f"Charge {m['cpu_usage']:.0f} % · " if m.get("cpu_usage") is not None else ""
                self.remplir_tuile(t["cpu"], "--", "°C", charge + "HWiNFO nécessaire", 0, "?", GRIS, GRIS)
            # Carte graphique (nvidia-smi)
            if m["gpu"]:
                temp, util, vram, watts = m["gpu"]
                self.max["gpu"] = max(self.max["gpu"], temp)
                etat, couleur = self.etat_temperature(temp, ALERTE_GPU)
                if couleur != VERT:
                    soucis.append(f"GPU {etat.lower()}")
                self.remplir_tuile(t["gpu"], f"{temp:.0f}", "°C", f"Charge {util} % · {watts:.0f} W",
                                   temp / 100, etat, couleur, ROUGE if couleur == ROUGE else None)
                self.vram = vram
            else:
                self.remplir_tuile(t["gpu"], "--", "°C", "nvidia-smi introuvable", 0, "?", GRIS, GRIS)
            # Mémoire
            if m["ram"]:
                utilise, total = m["ram"]
                pct = utilise / total * 100
                couleur = ROUGE if pct >= 90 else (ORANGE if pct >= 80 else VERT)
                if couleur != VERT:
                    soucis.append("mémoire presque pleine")
                vram = getattr(self, "vram", None)
                self.remplir_tuile(t["ram"], f"{utilise:.1f}".replace(".", ","), f"/ {total:.0f} Go",
                                   f"VRAM {vram / 1024:.1f} Go utilisés".replace(".", ",") if vram else "",
                                   pct / 100, f"{pct:.0f} %", couleur)
                t["ram"]["jauge"](pct / 100, VIOLET)
            # Connexion : on compare avec le relevé d'il y a 2 s
            vitesse = debit(self.dernier_reseau, m.get("reseau"))
            self.dernier_reseau = m.get("reseau") or self.dernier_reseau
            if vitesse:
                down, up = vitesse
                self.max_down = max(self.max_down, down)
                self.remplir_tuile(t["net"], f"{down:.1f}".replace(".", ",") if down < 10 else f"{down:.0f}",
                                   "Mbit/s ↓", f"↑ {up:.1f} Mbit/s envoi".replace(".", ","),
                                   down / max(self.max_down, 50), "Active" if down + up > 0.2 else "Calme", VERT)
                t["net"]["jauge"](down / max(self.max_down, 50), VERT)
            elif m.get("reseau") is None:
                self.remplir_tuile(t["net"], "--", "Mbit/s", "mesure impossible", 0, "?", GRIS, GRIS)
            # Disques (températures HWiNFO) et conseil HWiNFO
            if m["disques"]:
                self.temps_disques = m["disques"]
                for _, temp, lettre in m["disques"]:
                    if temp >= 60:
                        soucis.append(f"disque {lettre or ''} chaud".replace("  ", " "))
            if not m["hwinfo"]:
                self.astuce_hwinfo.config(text="ⓘ Température CPU : ouvre HWiNFO et coche « Shared Memory Support » "
                                               "dans ses réglages, puis laisse-le ouvert.")
                self.astuce_hwinfo.pack(fill="x")
            else:
                self.astuce_hwinfo.pack_forget()
            if getattr(self, "disques_a_surveiller", 0):
                soucis.append("disque à surveiller")
            self.afficher_pastille(soucis)
            # Actions rapides : profil actif
            self.info_profil_dash.config(text=f"{REGLAGES.get('profil_actif') or 'aucun'} ▾")
            self.dernieres_mesures = m
            self.derniere_vitesse = vitesse or getattr(self, "derniere_vitesse", None)
            self.noter("cpu_max", m["cpu_temp"])
            self.noter("gpu_max", m["gpu"][0] if m["gpu"] else None)
            self.historique["cpu"].append(m["cpu_temp"])
            self.historique["gpu"].append(m["gpu"][0] if m["gpu"] else None)
            self.dessiner_graphique()
            if any(c == ROUGE for c in (t["cpu"]["valeur"].cget("fg"), t["gpu"]["valeur"].cget("fg"))):
                self.racine.bell()
            self.racine.after(2000, self.maj_temperatures)   # et on recommence dans 2 s
        self.en_fond(lire_tout, ensuite)

    @staticmethod
    def etat_temperature(temp, alerte):
        """Un mot simple + sa couleur pour une température."""
        if temp >= alerte:
            return "Brûlant", ROUGE
        if temp >= alerte - 10:
            return "Chaud", ORANGE
        return "Normal", VERT

    def afficher_pastille(self, soucis):
        """La pastille en haut : « Tout va bien » ou le premier souci."""
        if not soucis:
            texte, couleur = "✓  Tout va bien", VERT
        else:
            texte = "⚠  " + soucis[0][0].upper() + soucis[0][1:] + (f"  (+{len(soucis) - 1})" if len(soucis) > 1 else "")
            couleur = ORANGE
        self.pastille.config(text=texte, fg=couleur, bg=melanger(FOND, couleur, 0.12))

    def dessiner_graphique(self):
        c = self.graphique
        c.delete("all")   # on efface et on redessine tout
        larg, haut = max(c.winfo_width(), 200), max(c.winfo_height(), 120)
        gauche, droite, bas, mini, maxi = 34, max(c.winfo_width(), 200) - 8, haut - 20, 20, 100

        def y(temp):
            temp = min(max(temp, mini), maxi)
            return bas - (temp - mini) / (maxi - mini) * (bas - 8)

        for t in (20, 40, 60, 80, 100):   # lignes repères
            c.create_line(gauche, y(t), droite, y(t), fill="#16162a")
            c.create_text(gauche - 6, y(t), text=f"{t}°", fill=GRIS, anchor="e", font=("Segoe UI", 8))
        # ligne d'alerte en pointillés
        c.create_line(gauche, y(ALERTE_GPU), droite, y(ALERTE_GPU), fill=melanger(CARTE, ORANGE, 0.6), dash=(4, 4))
        self.legende_alerte.config(text=f"┄ alerte {ALERTE_GPU}°")
        # repères de temps
        for texte, x, ancre in (("-10 min", gauche, "w"), ("-5 min", (gauche + droite) / 2, "center"),
                                ("maintenant", droite, "e")):
            c.create_text(x, haut - 6, text=texte, fill=GRIS, anchor=ancre, font=("Segoe UI", 8))
        pas = (droite - gauche) / 299
        for cle, couleur in (("cpu", CYAN), ("gpu", ROSE)):
            valeurs = list(self.historique[cle])
            depart = 300 - len(valeurs)   # les nouvelles valeurs arrivent par la droite
            morceaux, points = [], []
            for i, v in enumerate(valeurs):
                if v is None:   # trou dans les mesures : on coupe la ligne
                    morceaux.append(points)
                    points = []
                    continue
                points += [gauche + (depart + i) * pas, y(v)]
            morceaux.append(points)
            for pts in morceaux:
                if len(pts) >= 4:
                    for largeur, force in ((12, 0.06), (8, 0.13), (5, 0.25)):
                        c.create_line(pts, fill=melanger(CARTE, couleur, force), width=largeur, smooth=True,
                                      capstyle="round", joinstyle="round", splinesteps=24)
                    c.create_line(pts, fill=couleur, width=2.5, smooth=True, capstyle="round", splinesteps=24)
            if valeurs and valeurs[-1] is not None:   # un point sur la valeur actuelle
                x, yy = gauche + 299 * pas, y(valeurs[-1])
                c.create_oval(x - 4, yy - 4, x + 4, yy + 4, fill=couleur, outline="")


    # ---------- 🎮 LANCEUR GAMING ----------

    def onglet_gaming(self, cadre):
        self.texte(cadre, "Session gaming", 13, gras=True)
        self.texte(cadre, "Ferme les applis inutiles, passe le PC en mode Performances, lance Discord et le jeu.",
                   couleur=GRIS)
        zone = tk.Frame(cadre, bg=CARTE)
        zone.pack(fill="x", pady=4)
        self.liste_jeux = tk.Listbox(zone, height=9, bg=FOND, fg=TEXTE, selectbackground=ACCENT, selectforeground=FOND,
                                     relief="flat", highlightthickness=0, font=("Segoe UI", 11), activestyle="none")
        barre = tk.Scrollbar(zone, command=self.liste_jeux.yview)
        self.liste_jeux.config(yscrollcommand=barre.set)
        self.liste_jeux.pack(side="left", fill="x", expand=True)
        barre.pack(side="left", fill="y")
        self.liste_jeux.bind("<Double-1>", lambda e: self.lancer())
        boutons = tk.Frame(cadre, bg=CARTE)
        boutons.pack(fill="x")
        self.btn_lancer = self.bouton(boutons, "🚀 Lancer la session", self.lancer, VERT)
        self.btn_lancer.pack(side="left", padx=(0, 8))
        self.btn_fini = self.bouton(boutons, "✅ J'ai fini de jouer", self.fin_session)
        self.btn_fini.pack(side="left", padx=(0, 8))
        self.btn_fini.config(state="disabled")
        self.bouton(boutons, "🔄", self.charger_jeux, CARTE).pack(side="left")
        self.info_gaming = self.texte(cadre, "", couleur=GRIS)
        self.info_gaming.config(wraplength=680)
        self.charger_jeux()

    def charger_jeux(self):
        def ensuite(jeux):
            if isinstance(jeux, Exception) or not jeux:
                jeux = JEUX_SECOURS
                self.info_gaming.config(text="Steam pas trouvé : je montre ta liste de secours.")
            else:
                self.info_gaming.config(text=f"{len(jeux)} jeux Steam trouvés. Double-clic sur un jeu pour le lancer.")
            self.jeux = jeux
            self.liste_jeux.delete(0, "end")
            for nom in jeux:
                self.liste_jeux.insert("end", "  " + nom)
            self.liste_jeux.selection_set(0)
        self.en_fond(jeux_steam, ensuite)

    def lancer(self):
        choix = self.liste_jeux.curselection()
        if not choix or self.session:
            return
        jeu = list(self.jeux)[choix[0]]
        self.btn_lancer.config(state="disabled")
        self.info_gaming.config(text="Préparation...", fg=GRIS)

        def travail():
            session = {"jeu": jeu, "applis": {}, "plan": None}
            # 1) On note où sont les applis, puis on les ferme
            chemins = chemins_applis(APPS_A_FERMER)
            for exe, chemin in chemins.items():
                res = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if res.returncode == 0:
                    session["applis"][exe] = chemin
            # 2) Plan d'alimentation Performances
            if REGLAGES["mode_performances"]:
                avant = plan_actif()
                if avant and activer_plan("SCHEME_MIN"):
                    session["plan"] = avant
            # 3) Discord + le jeu
            discord = Path(LOCALAPPDATA) / "Discord" / "Update.exe"
            if discord.exists():
                subprocess.Popen([str(discord), "--processStart", "Discord.exe"])
            os.startfile(f"steam://rungameid/{self.jeux[jeu]}")
            return session

        def ensuite(session):
            if isinstance(session, Exception):
                self.info_gaming.config(text=f"Erreur : {session}", fg=ROUGE)
                self.btn_lancer.config(state="normal")
                return
            self.session = session
            fermees = ", ".join(session["applis"]) or "aucune"
            perf = "mode Performances ✓" if session["plan"] else "plan d'alim inchangé"
            self.info_gaming.config(text=f"🚀 {jeu} se lance · applis fermées : {fermees} · {perf}. Bon jeu !", fg=TEXTE)
            self.btn_fini.config(state="normal")
        self.en_fond(travail, ensuite)

    def fin_session(self):
        if not self.session:
            return
        for exe, chemin in self.session["applis"].items():
            if Path(chemin).exists():
                subprocess.Popen([chemin])
        if self.session["plan"]:
            activer_plan(self.session["plan"])   # on remet ton plan d'avant
        self.session = None
        self.info_gaming.config(text="👍 Tout est remis comme avant (applis et plan d'alimentation).", fg=GRIS)
        self.btn_fini.config(state="disabled")
        self.btn_lancer.config(state="normal")

    # ---------- 📂 RANGEUR ----------

    def onglet_rangeur(self, cadre):
        self.texte(cadre, "Ranger les fichiers", 13, gras=True)
        self.info_dossier_rangeur = self.texte(cadre, f"Dossier : {DOSSIER_A_RANGER}", couleur=GRIS)
        self.apercu = self.texte(cadre, "Clique sur Aperçu pour voir ce qui sera rangé.")
        self.bouton(cadre, "🔍 Aperçu", self.voir_apercu)
        self.btn_ranger = self.bouton(cadre, "📂 Ranger", self.lancer_rangement, VERT)
        self.btn_ranger.config(state="disabled")
        self.plan = {}

    def voir_apercu(self):
        self.plan = plan_rangement()
        if not self.plan:
            self.apercu.config(text="Rien à ranger, c'est déjà propre ✨")
            self.btn_ranger.config(state="disabled")
            return
        lignes = [f"{cat} : {len(liste)} fichier(s)" for cat, liste in sorted(self.plan.items())]
        self.apercu.config(text="\n".join(lignes))
        self.btn_ranger.config(state="normal")

    def lancer_rangement(self):
        total = sum(len(l) for l in self.plan.values())
        if messagebox.askyesno("Ranger", f"Ranger ces {total} fichiers dans des sous-dossiers ?"):
            n = ranger(self.plan)
            self.apercu.config(text=f"✅ {n} fichier(s) rangé(s) !")
            self.btn_ranger.config(state="disabled")

    # ---------- 🔔 ALERTE PRIX ----------

    def onglet_prix(self, cadre):
        self.texte(cadre, "Alerte prix", 13, gras=True)
        self.texte(cadre, "Lien de la page du produit :", couleur=GRIS)
        self.champ_url = tk.Entry(cadre, bg=FOND, fg=TEXTE, insertbackground=TEXTE, relief="flat",
                                  font=("Segoe UI", 10))
        self.champ_url.pack(fill="x", ipady=5)
        self.texte(cadre, "Prévenir quand le prix passe sous (€) :", couleur=GRIS)
        self.champ_cible = tk.Entry(cadre, bg=FOND, fg=TEXTE, insertbackground=TEXTE, relief="flat",
                                    font=("Segoe UI", 10), width=12)
        self.champ_cible.pack(anchor="w", ipady=5)
        self.btn_surveiller = self.bouton(cadre, "🔔 Surveiller", self.basculer_surveillance)
        self.info_prix = self.texte(cadre, "", 11)
        self.surveillance = False
        self.prochaine_verif = None

    def basculer_surveillance(self):
        if self.surveillance:
            self.surveillance = False
            if self.prochaine_verif:
                self.racine.after_cancel(self.prochaine_verif)   # annule la vérif prévue
                self.prochaine_verif = None
            self.btn_surveiller.config(text="🔔 Surveiller", bg=ACCENT)
            self.info_prix.config(text="Surveillance arrêtée.")
            return
        try:
            self.cible = float(self.champ_cible.get().replace(",", "."))
        except ValueError:
            messagebox.showwarning("Alerte prix", "Le prix cible doit être un nombre.")
            return
        self.url = self.champ_url.get().strip()
        if not self.url.startswith("http"):
            messagebox.showwarning("Alerte prix", "Colle un lien qui commence par http.")
            return
        self.surveillance = True
        self.btn_surveiller.config(text="⏹ Arrêter", bg=ROUGE)
        self.verifier_prix()

    def verifier_prix(self):
        if not self.surveillance:
            return
        self.info_prix.config(text="Vérification du prix...")

        def ensuite(prix):
            if not self.surveillance:
                return
            heure = time.strftime("%H:%M")
            if isinstance(prix, Exception):
                self.info_prix.config(text=f"[{heure}] Page illisible : {prix}")
            elif prix is None:
                self.info_prix.config(text=f"[{heure}] Pas de prix trouvé (le site bloque peut-être les scripts).")
            elif prix <= self.cible:
                self.info_prix.config(text=f"[{heure}] 🎉 {prix:.2f} € : prix atteint !", fg=VERT)
                self.basculer_surveillance()
                self.racine.bell()
                self.montrer()   # si la fenêtre était cachée près de l'horloge
                messagebox.showinfo("Alerte prix 🎉", f"Prix atteint : {prix:.2f} €\n\n{self.url}")
                return
            else:
                self.info_prix.config(
                    text=f"[{heure}] {prix:.2f} € (cible {self.cible:.2f} €). Prochaine vérif dans {MINUTES_ENTRE_PRIX} min.",
                    fg=TEXTE)
            self.prochaine_verif = self.racine.after(MINUTES_ENTRE_PRIX * 60 * 1000, self.verifier_prix)
        self.en_fond(lambda: trouver_prix(self.url), ensuite)


# =============================================================
#  DÉMARRAGE
# =============================================================

# La suite de la classe BoiteAOutils : l'onglet Temps de jeu.

def onglet_temps_de_jeu(self, cadre):
    self.texte(cadre, "Temps de jeu", 13, gras=True)
    self.info_jeu_actuel = self.texte(cadre, "", 11)
    self.info_totaux = self.texte(cadre, "", 11)
    self.texte(cadre, "Par jeu, sur les 7 derniers jours", 10, GRIS, True)
    self.graph_jeux = tk.Canvas(cadre, bg=FOND, height=170, highlightthickness=0)
    self.graph_jeux.pack(fill="x", pady=(2, 8))
    self.texte(cadre, "Par jour", 10, GRIS, True)
    self.graph_jours = tk.Canvas(cadre, bg=FOND, height=120, highlightthickness=0)
    self.graph_jours.pack(fill="x", pady=2)
    self.texte(cadre, "Le suivi marche tant que la boîte à outils est ouverte (ou rangée près de l'horloge).",
               9, GRIS)
    self.temps = charger_temps()
    self.jeu_actuel, self.debut_jeu, self.dernier_releve = None, None, time.time()
    self.racine.after(1500, self.suivre_jeu)
    # Quand l'onglet s'affiche (ou change de taille), on redessine les graphiques à la bonne largeur
    self.graph_jeux.bind("<Configure>", lambda e: self.afficher_temps())
    self.graph_jours.bind("<Configure>", lambda e: self.afficher_temps())


def suivre_jeu(self):
    """Toutes les 30 s : quel jeu tourne ? On ajoute le temps écoulé à ce jeu."""
    def ensuite(jeu):
        maintenant = time.time()
        ecoule = min(maintenant - self.dernier_releve, 60)   # max 60 s (si le PC était en veille)
        self.dernier_releve = maintenant
        if isinstance(jeu, Exception):
            jeu = None
        if jeu and jeu == self.jeu_actuel:
            jour = time.strftime("%Y-%m-%d")
            self.temps.setdefault(jour, {})
            self.temps[jour][jeu] = self.temps[jour].get(jeu, 0) + ecoule
            try:
                DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
                FICHIER_TEMPS.write_text(json.dumps(self.temps, indent=1, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        if jeu != self.jeu_actuel:
            self.jeu_actuel, self.debut_jeu = jeu, maintenant
        self.afficher_temps()
        self.racine.after(30 * 1000, self.suivre_jeu)
    self.en_fond(lambda: jeu_en_cours(getattr(self, "jeux", {})), ensuite)


def afficher_temps(self):
    if self.jeu_actuel:
        self.info_jeu_actuel.config(text=f"🎮 En ce moment : {self.jeu_actuel} "
                                         f"(depuis {duree_lisible(time.time() - self.debut_jeu)})", fg=VERT)
    else:
        self.info_jeu_actuel.config(text="💤 Aucun jeu lancé", fg=GRIS)

    # Les 7 derniers jours, du plus ancien au plus récent
    jours = [time.strftime("%Y-%m-%d", time.localtime(time.time() - i * 86400)) for i in range(6, -1, -1)]
    par_jeu, par_jour = {}, []
    for jour in jours:
        total = 0
        for jeu, sec in self.temps.get(jour, {}).items():
            par_jeu[jeu] = par_jeu.get(jeu, 0) + sec
            total += sec
        par_jour.append(total)
    self.info_totaux.config(text=f"Aujourd'hui : {duree_lisible(par_jour[-1])}   ·   "
                                 f"7 derniers jours : {duree_lisible(sum(par_jour))}")
    # Et sur le tableau de bord
    if self.jeu_actuel:
        self.dash_jeu.config(text=f"{self.jeu_actuel} · {duree_lisible(time.time() - self.debut_jeu)}", fg=CYAN)
    else:
        self.dash_jeu.config(text="Aucun jeu", fg=GRIS)
    self.dash_semaine.config(text=f"7 derniers jours : {duree_lisible(sum(par_jour))}")
    if par_jeu:
        top = max(par_jeu, key=par_jeu.get)
        self.dash_top.config(text=f"Le plus joué : {top}")

    # Graphique 1 : une barre horizontale par jeu (les 5 plus joués)
    c = self.graph_jeux
    c.delete("all")
    larg = max(c.winfo_width(), 300)
    classement = sorted(par_jeu.items(), key=lambda j: j[1], reverse=True)[:5]
    if not classement:
        c.create_text(larg / 2, 85, text="Pas encore de partie enregistrée. Lance un jeu !", fill=GRIS,
                      font=("Segoe UI", 10))
    plus_long = max([sec for _, sec in classement], default=1)
    couleurs = [CYAN, ROSE, VIOLET, VERT, ORANGE]
    for i, (jeu, sec) in enumerate(classement):
        y = 14 + i * 31
        c.create_text(10, y + 9, text=jeu[:22], fill=TEXTE, anchor="w", font=("Segoe UI", 10))
        fin = 190 + (larg - 290) * sec / plus_long
        c.create_rectangle(190, y, fin, y + 18, fill=couleurs[i], width=0)
        c.create_text(fin + 8, y + 9, text=duree_lisible(sec), fill=GRIS, anchor="w", font=("Segoe UI", 9))

    # Graphique 2 : une colonne par jour
    c = self.graph_jours
    c.delete("all")
    larg = max(c.winfo_width(), 300)
    plus_long = max(par_jour + [3600])
    pas = (larg - 20) / 7
    noms_jours = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
    for i, (jour, sec) in enumerate(zip(jours, par_jour)):
        x = 10 + i * pas
        haut = (120 - 40) * sec / plus_long
        c.create_rectangle(x + pas * 0.2, 98 - haut, x + pas * 0.8, 98, fill=VIOLET if i < 6 else CYAN, width=0)
        nom = noms_jours[time.strptime(jour, "%Y-%m-%d").tm_wday]
        c.create_text(x + pas / 2, 110, text=nom, fill=GRIS, font=("Segoe UI", 9))
        if sec >= 60:
            c.create_text(x + pas / 2, 90 - haut, text=duree_lisible(sec), fill=TEXTE, font=("Segoe UI", 8))


BoiteAOutils.onglet_temps_de_jeu = onglet_temps_de_jeu
BoiteAOutils.suivre_jeu = suivre_jeu
BoiteAOutils.afficher_temps = afficher_temps


# La suite de la classe BoiteAOutils : l'onglet Santé (mises à jour + disques).

def onglet_sante(self, cadre):
    self.texte(cadre, "Mises à jour", 13, gras=True)
    ligne = tk.Frame(cadre, bg=CARTE)
    ligne.pack(fill="x")
    self.info_pilote = tk.Label(ligne, text="Pilote NVIDIA : vérification...", bg=CARTE, fg=TEXTE,
                                font=("Segoe UI", 10), anchor="w")
    self.info_pilote.pack(side="left")
    self.btn_pilote = tk.Button(ligne, text="⬇️ Télécharger", relief="flat", bg=VERT, fg=FOND,
                                font=("Segoe UI", 9, "bold"), cursor="hand2")
    self.lien_pilote = PAGE_PILOTES_NVIDIA
    self.btn_pilote.config(command=lambda: os.startfile(self.lien_pilote))

    self.liste_maj = tk.Listbox(cadre, height=5, bg=FOND, fg=TEXTE, selectbackground=ACCENT, selectforeground=FOND, relief="flat",
                                highlightthickness=0, font=("Segoe UI", 10), activestyle="none",
                                selectmode="extended")
    self.liste_maj.pack(fill="x", pady=(6, 2))
    boutons = tk.Frame(cadre, bg=CARTE)
    boutons.pack(fill="x")
    self.bouton(boutons, "🔍 Vérifier", lambda: (self.verifier_maj(), self.verifier_pilotes())).pack(side="left", padx=(0, 8))
    self.btn_maj = self.bouton(boutons, "⬆️ Mettre à jour la sélection", self.lancer_maj, VERT)
    self.btn_maj.pack(side="left")
    self.btn_maj.config(state="disabled")
    self.info_maj = self.texte(cadre, "", 9, GRIS)

    # Autres pilotes + carte mère
    ligne_wu = tk.Frame(cadre, bg=CARTE)
    ligne_wu.pack(fill="x", pady=(6, 0))
    self.info_pilotes = tk.Label(ligne_wu, text="Autres pilotes : vérification via Windows Update...", bg=CARTE,
                                 fg=TEXTE, font=("Segoe UI", 10), anchor="w", justify="left", wraplength=560)
    self.info_pilotes.pack(side="left")
    tk.Button(ligne_wu, text="🪟 Windows Update", relief="flat", bg=ACCENT, fg=FOND, font=("Segoe UI", 9, "bold"),
              cursor="hand2", command=lambda: os.startfile("ms-settings:windowsupdate-optionalupdates")).pack(side="right")
    ligne_msi = tk.Frame(cadre, bg=CARTE)
    ligne_msi.pack(fill="x", pady=(4, 0))
    bios = version_bios()
    texte_bios = f"Carte mère MSI PRO B760-P : BIOS {bios[0]} du {bios[1]}" if bios else "Carte mère MSI PRO B760-P"
    tk.Label(ligne_msi, text=texte_bios + "  (compare avec la page MSI)", bg=CARTE, fg=TEXTE,
             font=("Segoe UI", 10), anchor="w").pack(side="left")
    tk.Button(ligne_msi, text="🌐 Page MSI", relief="flat", bg=ACCENT, fg=FOND, font=("Segoe UI", 9, "bold"),
              cursor="hand2", command=lambda: os.startfile(PAGE_MSI)).pack(side="right")
    self.racine.after(5000, self.verifier_pilotes)

    self.texte(cadre, "Santé des disques", 13, gras=True).pack_configure(pady=(10, 2))
    self.cadre_disques = tk.Frame(cadre, bg=CARTE)
    self.cadre_disques.pack(fill="x")
    self.bouton(cadre, "🔄 Revérifier les disques", self.verifier_disques)
    self.applis_maj = []
    self.racine.after(3000, self.verifier_maj)
    self.racine.after(4000, self.verifier_disques)


def verifier_maj(self):
    self.info_maj.config(text="Je demande à Windows quelles applis ont une mise à jour (ça peut prendre 30 s)...")

    def travail():
        installe = version_pilote_nvidia()
        try:
            dernier, lien = dernier_pilote_nvidia()
        except Exception:
            dernier, lien = None, PAGE_PILOTES_NVIDIA
        try:
            applis = applis_a_mettre_a_jour()
        except (OSError, subprocess.TimeoutExpired):
            applis = None
        return installe, dernier, lien, applis

    def ensuite(res):
        if isinstance(res, Exception):
            self.info_maj.config(text=f"Erreur : {res}")
            return
        installe, dernier, self.lien_pilote, applis = res
        self.btn_pilote.pack_forget()
        if installe and dernier:
            try:
                a_jour = float(installe) >= float(dernier)
            except ValueError:
                a_jour = installe == dernier
            if a_jour:
                self.info_pilote.config(text=f"✅ Pilote NVIDIA à jour ({installe})", fg=VERT)
            else:
                self.info_pilote.config(text=f"🆕 Nouveau pilote NVIDIA : {dernier} (tu as {installe})  ", fg=ORANGE)
                self.btn_pilote.pack(side="left")
        else:
            self.info_pilote.config(text=f"Pilote NVIDIA : {installe or '?'} (impossible de vérifier en ligne)  ",
                                    fg=TEXTE)
            self.btn_pilote.config(text="🌐 Page des pilotes")
            self.btn_pilote.pack(side="left")
        self.liste_maj.delete(0, "end")
        if applis is None:
            self.info_maj.config(text="winget introuvable : il s'installe avec « Programme d'installation "
                                      "d'application » dans le Microsoft Store.")
            return
        self.applis_maj = applis
        for a in applis:
            self.liste_maj.insert("end", f"  {a['nom']}   {a['version']} → {a['dispo']}")
        if applis:
            self.info_maj.config(text=f"{len(applis)} appli(s) à mettre à jour. Sélectionne-les (Ctrl+clic pour "
                                      f"plusieurs) puis clique sur Mettre à jour.")
            self.btn_maj.config(state="normal")
        else:
            self.info_maj.config(text="✅ Toutes tes applis sont à jour.")
            self.btn_maj.config(state="disabled")
    self.en_fond(travail, ensuite)


def lancer_maj(self):
    choisies = [self.applis_maj[i] for i in self.liste_maj.curselection()]
    if not choisies:
        self.info_maj.config(text="Sélectionne d'abord une ou plusieurs applis 👆")
        return
    noms = ", ".join(a["nom"] for a in choisies)
    if not messagebox.askyesno("Mises à jour", f"Mettre à jour : {noms} ?\n\n"
                                               "Certaines applis demanderont l'accès admin, et il vaut mieux "
                                               "les fermer avant."):
        return
    self.btn_maj.config(state="disabled")
    self.info_maj.config(text=f"Mise à jour en cours : {noms}... (laisse tourner)")

    def travail():
        return [(a["nom"], mettre_a_jour(a["id"])) for a in choisies]

    def ensuite(res):
        if isinstance(res, Exception):
            self.info_maj.config(text=f"Erreur : {res}")
            return
        ok = [n for n, r in res if r]
        self.noter("maj", len(ok), "somme")
        rate = [n for n, r in res if not r]
        texte = (f"✅ À jour : {', '.join(ok)}. " if ok else "") + (f"❌ Raté : {', '.join(rate)}." if rate else "")
        self.verifier_maj()
        self.racine.after(200, lambda: self.info_maj.config(text=texte))
    self.en_fond(travail, ensuite)


def verifier_disques(self):
    for w in self.cadre_disques.winfo_children():
        w.destroy()
    tk.Label(self.cadre_disques, text="Analyse...", bg=CARTE, fg=GRIS, font=("Segoe UI", 10)).pack(anchor="w")

    def ensuite(disques):
        for w in self.cadre_disques.winfo_children():
            w.destroy()
        if isinstance(disques, Exception) or not disques:
            tk.Label(self.cadre_disques, text="Impossible de lire les disques.", bg=CARTE, fg=GRIS,
                     font=("Segoe UI", 10)).pack(anchor="w")
            return
        nb_ok = 0
        for d in disques:
            probleme = d["panne"] or d["sante"] not in ("Healthy", None) or (d["vie"] is not None and d["vie"] < 20)
            fatigue = d["vie"] is not None and d["vie"] < 50
            icone, couleur = ("⚠️", ROUGE) if probleme else (("🟠", ORANGE) if fatigue else ("✅", VERT))
            nb_ok += not probleme
            morceaux = [f"{d['nom']} ({d['type']}, {d['taille'] / 1e9:.0f} Go)"]
            morceaux.append("bon état" if not probleme else "PROBLÈME : sauvegarde tes fichiers !")
            if d["vie"] is not None:
                morceaux.append(f"vie restante {d['vie']:.0f} %")
            if d["temp"] is not None:
                morceaux.append(f"{d['temp']:.0f} °C")
            if d["ecrit"]:
                valeur, unite = d["ecrit"]
                morceaux.append(f"{valeur:,.0f} {unite} écrits".replace(",", " "))
            tk.Label(self.cadre_disques, text=f"{icone}  " + "  ·  ".join(morceaux), bg=CARTE, fg=couleur,
                     font=("Segoe UI", 10), anchor="w").pack(fill="x", pady=1)
        self.sante_disques_connue = True
        self.dash_disques.config(text=espacer(f"{nb_ok} / {len(disques)} OK"), fg=VERT if nb_ok == len(disques) else ROUGE)
        if not any(d["vie"] is not None for d in disques):
            tk.Label(self.cadre_disques, text="Pour l'usure des SSD : active « Shared Memory Support » dans HWiNFO.",
                     bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w").pack(fill="x")
    self.en_fond(etat_disques, ensuite)


def verifier_pilotes(self):
    def ensuite(pilotes):
        if isinstance(pilotes, Exception):
            self.info_pilotes.config(text=f"Autres pilotes : impossible de demander à Windows Update ({pilotes})", fg=GRIS)
        elif pilotes:
            liste = "\n".join("   • " + p[:80] for p in pilotes[:6])
            self.info_pilotes.config(text=f"🆕 {len(pilotes)} pilote(s) dispo dans Windows Update "
                                          f"(Mises à jour facultatives) :\n{liste}", fg=ORANGE)
        else:
            self.info_pilotes.config(text="✅ Autres pilotes : rien de nouveau dans Windows Update", fg=VERT)
    self.en_fond(pilotes_windows_update, ensuite)


BoiteAOutils.verifier_pilotes = verifier_pilotes
BoiteAOutils.onglet_sante = onglet_sante
BoiteAOutils.verifier_maj = verifier_maj
BoiteAOutils.lancer_maj = lancer_maj
BoiteAOutils.verifier_disques = verifier_disques


# La suite de la classe BoiteAOutils : l'onglet Réglages.
# (On peut ajouter une fonction à une classe après coup.)

def onglet_reglages(self, cadre):
    self.texte(cadre, "Réglages", 13, gras=True)
    grille = tk.Frame(cadre, bg=CARTE)
    grille.pack(fill="x", pady=4)
    self.champs_reglages = {}
    lignes = [
        ("dossier_medal", "Dossier des clips Medal", True),
        ("jours_clips", "Clips Medal : supprimer après (jours)", False),
        ("dossier_a_ranger", "Dossier à ranger", True),
        ("alerte_cpu", "Alerte température CPU (°C)", False),
        ("alerte_gpu", "Alerte température GPU (°C)", False),
        ("apps_a_fermer", "Applis à fermer pour jouer (séparées par des virgules)", False),
        ("minutes_entre_prix", "Alerte prix : vérifier toutes les (minutes)", False),
        ("verrou_minutes", "Coffre : verrouiller après (minutes)", False),
    ]
    for i, (cle, titre, dossier) in enumerate(lignes):
        tk.Label(grille, text=titre, bg=CARTE, fg=GRIS, font=("Segoe UI", 10), anchor="w").grid(
            row=i, column=0, sticky="w", pady=3, padx=(0, 10))
        champ = tk.Entry(grille, bg=FOND, fg=TEXTE, insertbackground=TEXTE, relief="flat",
                         font=("Segoe UI", 10), width=26 if dossier or cle == "apps_a_fermer" else 8)
        valeur = REGLAGES[cle]
        champ.insert(0, ", ".join(valeur) if isinstance(valeur, list) else str(valeur))
        champ.grid(row=i, column=1, sticky="w", ipady=3)
        if dossier:   # petit bouton pour choisir un dossier
            def choisir(c=champ):
                choix = filedialog.askdirectory(initialdir=c.get() or str(Path.home()))
                if choix:
                    c.delete(0, "end")
                    c.insert(0, str(Path(choix)))
            tk.Button(grille, text="📁", command=choisir, relief="flat", bg=FOND, fg=TEXTE).grid(row=i, column=2, padx=4)
        self.champs_reglages[cle] = champ

    self.cases_reglages = {}
    for cle, titre in [("mode_performances", "Passer en mode Performances pendant les sessions gaming"),
                       ("fermer_vers_icone", "La croix range la fenêtre près de l'horloge (au lieu de quitter)"),
                       ("demarrage_windows", "Lancer la boîte à outils au démarrage de Windows"),
                       ("maj_auto", "Installer les mises à jour toute seule au démarrage")]:
        var = tk.BooleanVar(value=REGLAGES.get(cle, True))
        tk.Checkbutton(cadre, text=titre, variable=var, bg=CARTE, fg=TEXTE, selectcolor=FOND,
                       activebackground=CARTE, activeforeground=TEXTE, font=("Segoe UI", 10), anchor="w",
                       highlightthickness=0, bd=0).pack(fill="x", pady=1)
        self.cases_reglages[cle] = var
    # Le micro que le bouton Micro coupe (utile avec Voicemeeter : choisis celui que Discord utilise)
    ligne_micro = tk.Frame(cadre, bg=CARTE)
    ligne_micro.pack(fill="x", pady=(8, 2))
    tk.Label(ligne_micro, text="Micro coupé par le bouton Micro :", bg=CARTE, fg=GRIS, font=("Segoe UI", 10)).pack(side="left")
    self.choix_micro = ttk.Combobox(ligne_micro, state="readonly", width=44, values=["Micro par défaut de Windows"])
    self.choix_micro.set(REGLAGES.get("micro_nom") or "Micro par défaut de Windows")
    self.choix_micro.pack(side="left", padx=8)
    self.texte(cadre, "Avec Voicemeeter, choisis le même micro que le « Périphérique d'entrée » de Discord.", 9, GRIS)

    def remplir_micros(micros):
        if not isinstance(micros, Exception) and micros:
            self.choix_micro.config(values=["Micro par défaut de Windows"] + [nom for nom, _ in micros])
    self.en_fond(lister_micros, remplir_micros)
    self.bouton(cadre, "💾 Enregistrer", self.sauver_reglages, VERT)
    self.info_reglages = self.texte(cadre, "", 10, VERT)


def sauver_reglages(self):
    nouveaux = {}
    for cle, champ in self.champs_reglages.items():
        valeur = champ.get().strip()
        if cle == "apps_a_fermer":
            nouveaux[cle] = [a.strip() for a in valeur.split(",") if a.strip()]
        elif cle.startswith("dossier"):
            nouveaux[cle] = valeur
        else:
            if not valeur.isdigit() or int(valeur) <= 0:
                self.info_reglages.config(text=f"« {valeur} » n'est pas un nombre valide.", fg=ROUGE)
                return
            nouveaux[cle] = int(valeur)
    for cle, var in self.cases_reglages.items():
        nouveaux[cle] = var.get()
    micro_choisi = self.choix_micro.get()
    nouveaux["micro_nom"] = "" if micro_choisi.startswith("Micro par défaut") else micro_choisi
    try:
        if nouveaux["demarrage_windows"] != REGLAGES["demarrage_windows"] or nouveaux["demarrage_windows"]:
            regler_demarrage(nouveaux["demarrage_windows"])
    except OSError as e:
        self.info_reglages.config(text=f"Démarrage Windows impossible à régler : {e}", fg=ROUGE)
        return
    if nouveaux["fermer_vers_icone"] and not REGLAGES["fermer_vers_icone"]:
        self.creer_icone()
    REGLAGES.update(nouveaux)
    enregistrer_reglages()
    # On met à jour ce qui est affiché dans les autres onglets
    self.construire_zones()
    self.info_dossier_rangeur.config(text=f"Dossier : {DOSSIER_A_RANGER}")
    self.info_reglages.config(text="✅ Réglages enregistrés !", fg=VERT)


BoiteAOutils.onglet_reglages = onglet_reglages
BoiteAOutils.sauver_reglages = sauver_reglages


# =============================================================
#  🔐 COFFRE-FORT  -  gestionnaire de mots de passe chiffré
# =============================================================
#  COMMENT C'EST PROTÉGÉ ?
#  1. Ton mot de passe maître n'est JAMAIS enregistré nulle part.
#  2. On le transforme en "clé" avec scrypt : un calcul volontairement
#     lent (~0,5 s), pour qu'un pirate ne puisse pas tester des millions
#     de mots de passe par seconde.
#  3. Avec cette clé, on chiffre tout le coffre en AES-256-GCM, le même
#     chiffrement que les banques et les VPN. Sans le bon mot de passe,
#     le fichier n'est qu'un tas d'octets illisibles.
#  ⚠️ Mot de passe maître oublié = coffre perdu. Personne ne peut le
#     récupérer, même pas moi. C'est le principe d'un coffre-fort !
#
#  Le chiffrement AES vient de la librairie "cryptography".
#  Si elle manque, l'onglet propose de l'installer tout seul.
# =============================================================

FICHIER_COFFRE = Path.home() / "CoffreFort" / "coffre.dat"
VERROU_MINUTES = 5          # verrouillage auto après X minutes sans rien toucher
EFFACER_PRESSE_PAPIER = 30  # secondes avant d'effacer un mdp copié

AESGCM = None       # rempli par charger_crypto()
InvalidTag = None


def charger_crypto():
    """Importe "cryptography". Renvoie True si c'est bon."""
    global AESGCM, InvalidTag
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM as _AESGCM
        from cryptography.exceptions import InvalidTag as _InvalidTag
    except ImportError:
        return False
    AESGCM, InvalidTag = _AESGCM, _InvalidTag
    return True


def installer_crypto():
    return installer_paquets("cryptography")


# Format du fichier : [16 octets de sel][12 octets de nonce][données chiffrées]
#  - le sel rend ta clé unique même si quelqu'un a le même mdp maître
#  - le nonce change à chaque sauvegarde (obligatoire pour AES-GCM)

def deriver_cle(mot_de_passe, sel):
    """Mot de passe maître + sel -> clé de 32 octets (256 bits)."""
    return hashlib.scrypt(mot_de_passe.encode("utf-8"), salt=sel,
                          n=2**17, r=8, p=1, maxmem=2**28, dklen=32)


def chiffrer(donnees, mot_de_passe):
    sel = secrets.token_bytes(16)
    nonce = secrets.token_bytes(12)
    cle = deriver_cle(mot_de_passe, sel)
    texte = json.dumps(donnees, ensure_ascii=False).encode("utf-8")
    return sel + nonce + AESGCM(cle).encrypt(nonce, texte, None)


def dechiffrer(contenu, mot_de_passe):
    """Renvoie les données, ou lève InvalidTag si le mot de passe est faux."""
    sel, nonce, chiffre = contenu[:16], contenu[16:28], contenu[28:]
    cle = deriver_cle(mot_de_passe, sel)
    return json.loads(AESGCM(cle).decrypt(nonce, chiffre, None).decode("utf-8"))


def sauvegarder_coffre(donnees, mot_de_passe):
    FICHIER_COFFRE.parent.mkdir(parents=True, exist_ok=True)
    temporaire = FICHIER_COFFRE.with_suffix(".tmp")
    temporaire.write_bytes(chiffrer(donnees, mot_de_passe))
    if FICHIER_COFFRE.exists():   # on garde la version d'avant en secours (.bak)
        os.replace(FICHIER_COFFRE, FICHIER_COFFRE.with_suffix(".bak"))
    os.replace(temporaire, FICHIER_COFFRE)   # remplacement "d'un coup" : jamais de fichier à moitié écrit


def generer_mdp(longueur=20):
    """Un mot de passe vraiment aléatoire (module secrets = qualité crypto)."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*-_=+?"
    while True:
        mdp = "".join(secrets.choice(alphabet) for _ in range(longueur))
        if any(c.islower() for c in mdp) and any(c.isupper() for c in mdp) and any(c.isdigit() for c in mdp):
            return mdp


class Coffre:
    """L'onglet coffre-fort. Il vit dans un cadre de la fenêtre principale."""

    def __init__(self, cadre, racine):
        self.cadre = cadre
        self.racine = racine
        self.mdp_maitre = None
        self.entrees = []          # liste de dictionnaires {site, identifiant, mdp, note}
        self.minuteur_verrou = None
        self.minuteur_presse_papier = None
        # Chaque clic ou touche remet à zéro le compte à rebours du verrouillage
        racine.bind_all("<Any-KeyPress>", self.activite, add="+")
        racine.bind_all("<Any-Button>", self.activite, add="+")
        self.ecran_verrouille()

    def vider(self):
        for w in self.cadre.winfo_children():
            w.destroy()

    def bouton(self, parent, texte, action, couleur=ACCENT, cote="left"):
        b = tk.Button(parent, text=texte, command=action, bg=couleur, fg=texte_sur(couleur),
                      activebackground=couleur, activeforeground=texte_sur(couleur), relief="flat",
                      font=("Segoe UI", 9, "bold"), padx=10, pady=5, cursor="hand2")
        b.pack(side=cote, padx=3)
        return b

    def champ(self, parent, cache=False, largeur=28):
        return tk.Entry(parent, show="•" if cache else "", bg=FOND, fg=TEXTE, insertbackground=TEXTE,
                        relief="flat", font=("Segoe UI", 11), width=largeur)

    # ---------- ÉCRAN VERROUILLÉ ----------

    def ecran_verrouille(self):
        self.vider()
        self.mdp_maitre = None
        self.entrees = []
        premiere_fois = not FICHIER_COFFRE.exists()

        boite = tk.Frame(self.cadre, bg=CARTE)
        boite.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(boite, text="🔐", bg=CARTE, fg=TEXTE, font=("Segoe UI", 30)).pack()
        titre = "Crée ton mot de passe maître" if premiere_fois else "Coffre verrouillé"
        tk.Label(boite, text=titre, bg=CARTE, fg=TEXTE, font=("Segoe UI", 13, "bold")).pack(pady=(0, 8))

        self.champ_maitre = self.champ(boite, cache=True)
        self.champ_maitre.pack(ipady=5, pady=3)
        self.champ_maitre.bind("<Return>", lambda e: self.deverrouiller())
        self.champ_confirm = None
        if premiere_fois:
            tk.Label(boite, text="Confirme-le :", bg=CARTE, fg=GRIS, font=("Segoe UI", 9)).pack()
            self.champ_confirm = self.champ(boite, cache=True)
            self.champ_confirm.pack(ipady=5, pady=3)
            self.champ_confirm.bind("<Return>", lambda e: self.deverrouiller())
            tk.Label(boite, text="⚠️ Si tu l'oublies, personne ne pourra ouvrir le coffre.\n"
                                 "Choisis une phrase longue que tu retiens facilement.",
                     bg=CARTE, fg=GRIS, font=("Segoe UI", 9)).pack(pady=4)

        self.info_verrou = tk.Label(boite, text="", bg=CARTE, fg=ROUGE, font=("Segoe UI", 10))
        self.info_verrou.pack(pady=3)
        self.bouton(boite, "Créer le coffre" if premiere_fois else "Déverrouiller",
                    self.deverrouiller, VERT, cote="top")

    def deverrouiller(self):
        if AESGCM is None and not charger_crypto():
            if messagebox.askyesno("Coffre-fort", "Il manque la librairie « cryptography » pour chiffrer.\n\n"
                                                  "L'installer maintenant ? (environ 30 secondes)"):
                self.info_verrou.config(text="Installation...", fg=GRIS)
                self.racine.update()
                if installer_crypto() and charger_crypto():
                    self.info_verrou.config(text="Installé ✅", fg=VERT)
                else:
                    self.info_verrou.config(text="Échec. Dans PowerShell : python -m pip install cryptography", fg=ROUGE)
                    return
            else:
                return

        mdp = self.champ_maitre.get()
        if self.champ_confirm is not None:   # création du coffre
            if len(mdp) < 10:
                self.info_verrou.config(text="Au moins 10 caractères, s'il te plaît.", fg=ROUGE)
                return
            if mdp != self.champ_confirm.get():
                self.info_verrou.config(text="Les deux mots de passe ne sont pas pareils.", fg=ROUGE)
                return
            sauvegarder_coffre([], mdp)
            self.entrees = []
        else:
            self.info_verrou.config(text="Ouverture...", fg=GRIS)
            self.racine.update()
            try:
                self.entrees = dechiffrer(FICHIER_COFFRE.read_bytes(), mdp)
            except InvalidTag:
                self.info_verrou.config(text="Mauvais mot de passe.", fg=ROUGE)
                self.champ_maitre.delete(0, "end")
                return
            except Exception as e:
                self.info_verrou.config(text=f"Coffre illisible : {e}", fg=ROUGE)
                return
        self.mdp_maitre = mdp
        self.ecran_principal()
        self.activite()

    # ---------- VERROUILLAGE AUTO ----------

    def activite(self, _evenement=None):
        if self.mdp_maitre is None:
            return
        if self.minuteur_verrou:
            self.racine.after_cancel(self.minuteur_verrou)
        self.minuteur_verrou = self.racine.after(VERROU_MINUTES * 60 * 1000, self.verrouiller)

    def verrouiller(self):
        for w in self.racine.winfo_children():   # ferme une fenêtre d'édition restée ouverte
            if isinstance(w, tk.Toplevel):
                w.destroy()
        self.ecran_verrouille()

    # ---------- COFFRE OUVERT ----------

    def ecran_principal(self):
        self.vider()
        haut = tk.Frame(self.cadre, bg=CARTE)
        haut.pack(fill="x", pady=(0, 8))
        tk.Label(haut, text="🔎", bg=CARTE, fg=GRIS).pack(side="left")
        self.recherche = tk.StringVar()
        self.recherche.trace_add("write", lambda *a: self.rafraichir())
        tk.Entry(haut, textvariable=self.recherche, bg=FOND, fg=TEXTE, insertbackground=TEXTE,
                 relief="flat", font=("Segoe UI", 10), width=22).pack(side="left", ipady=4, padx=6)
        self.bouton(haut, "🔒 Verrouiller", self.verrouiller, ROUGE, cote="right")

        self.liste = ttk.Treeview(self.cadre, columns=("site", "identifiant", "note"), show="headings", height=8)
        for col, titre, larg in [("site", "Site / appli", 170), ("identifiant", "Identifiant", 190), ("note", "Note", 170)]:
            self.liste.heading(col, text=titre)
            self.liste.column(col, width=larg)
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<Double-1>", lambda e: self.copier("mdp"))

        bas = tk.Frame(self.cadre, bg=CARTE)
        bas.pack(fill="x", pady=(8, 0))
        self.bouton(bas, "➕ Ajouter", lambda: self.fenetre_edition(None), VERT)
        self.bouton(bas, "✏️ Modifier", self.modifier)
        self.bouton(bas, "📋 Copier mdp", lambda: self.copier("mdp"))
        self.bouton(bas, "👤 Copier identifiant", lambda: self.copier("identifiant"))
        self.bouton(bas, "🗑", self.supprimer, ROUGE)
        self.info = tk.Label(self.cadre, text="Astuce : double-clic sur une ligne = copier le mot de passe",
                             bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w")
        self.info.pack(fill="x", pady=(6, 0))
        self.rafraichir()

    def rafraichir(self):
        """Réaffiche la liste en tenant compte de la recherche."""
        self.liste.delete(*self.liste.get_children())
        filtre = self.recherche.get().lower()
        for i, e in sorted(enumerate(self.entrees), key=lambda x: x[1]["site"].lower()):
            if filtre in e["site"].lower() or filtre in e["identifiant"].lower():
                self.liste.insert("", "end", iid=str(i), values=(e["site"], e["identifiant"], e.get("note", "")))

    def selection(self):
        choix = self.liste.selection()
        if not choix:
            self.info.config(text="Sélectionne d'abord une ligne 👆", fg=ROUGE)
            return None
        return int(choix[0])

    def enregistrer(self):
        sauvegarder_coffre(self.entrees, self.mdp_maitre)
        self.rafraichir()

    def copier(self, champ):
        i = self.selection()
        if i is None:
            return
        self.racine.clipboard_clear()
        self.racine.clipboard_append(self.entrees[i][champ])
        if champ == "mdp":
            self.info.config(text=f"📋 Mot de passe copié ! Effacé du presse-papier dans {EFFACER_PRESSE_PAPIER} s.", fg=VERT)
            if self.minuteur_presse_papier:
                self.racine.after_cancel(self.minuteur_presse_papier)
            self.minuteur_presse_papier = self.racine.after(EFFACER_PRESSE_PAPIER * 1000, self.effacer_presse_papier)
        else:
            self.info.config(text="👤 Identifiant copié !", fg=VERT)

    def effacer_presse_papier(self):
        self.minuteur_presse_papier = None
        self.racine.clipboard_clear()
        self.racine.clipboard_append("")
        if self.mdp_maitre:
            self.info.config(text="Presse-papier effacé 🧽", fg=GRIS)

    def supprimer(self):
        i = self.selection()
        if i is None:
            return
        if messagebox.askyesno("Supprimer", f"Supprimer « {self.entrees[i]['site']} » du coffre ?"):
            del self.entrees[i]
            self.enregistrer()
            self.info.config(text="Supprimé.", fg=GRIS)

    def modifier(self):
        i = self.selection()
        if i is not None:
            self.fenetre_edition(i)

    def fenetre_edition(self, index):
        """Petite fenêtre pour ajouter (index=None) ou modifier une entrée."""
        e = self.entrees[index] if index is not None else {"site": "", "identifiant": "", "mdp": "", "note": ""}
        f = tk.Toplevel(self.racine, bg=CARTE, padx=18, pady=14)
        f.title("Modifier" if index is not None else "Ajouter")
        f.transient(self.racine)
        f.grab_set()   # on ne peut pas cliquer ailleurs tant qu'elle est ouverte

        champs = {}
        for ligne, (cle, titre) in enumerate([("site", "Site / appli"), ("identifiant", "Identifiant / e-mail"),
                                              ("mdp", "Mot de passe"), ("note", "Note")]):
            tk.Label(f, text=titre, bg=CARTE, fg=GRIS, font=("Segoe UI", 10)).grid(row=ligne, column=0, sticky="w", pady=4)
            c = self.champ(f, cache=(cle == "mdp"))
            c.insert(0, e.get(cle, ""))
            c.grid(row=ligne, column=1, ipady=4, padx=8)
            champs[cle] = c

        def basculer_affichage():
            champs["mdp"].config(show="" if champs["mdp"].cget("show") else "•")

        def generer():
            champs["mdp"].delete(0, "end")
            champs["mdp"].insert(0, generer_mdp())
            champs["mdp"].config(show="")

        outils = tk.Frame(f, bg=CARTE)
        outils.grid(row=2, column=2)
        tk.Button(outils, text="👁", command=basculer_affichage, relief="flat", bg=FOND, fg=TEXTE).pack(side="left", padx=2)
        tk.Button(outils, text="🎲", command=generer, relief="flat", bg=FOND, fg=TEXTE).pack(side="left", padx=2)

        def valider():
            nouveau = {cle: c.get().strip() for cle, c in champs.items()}
            nouveau["mdp"] = champs["mdp"].get()   # on ne retire pas les espaces d'un mdp
            if not nouveau["site"] or not nouveau["mdp"]:
                messagebox.showwarning("Oups", "Il faut au moins un site et un mot de passe.", parent=f)
                return
            if index is None:
                self.entrees.append(nouveau)
            else:
                self.entrees[index] = nouveau
            self.enregistrer()
            self.info.config(text=f"✅ « {nouveau['site']} » enregistré (chiffré).", fg=VERT)
            f.destroy()

        bas = tk.Frame(f, bg=CARTE)
        bas.grid(row=5, column=0, columnspan=3, pady=(12, 0))
        self.bouton(bas, "Enregistrer", valider, VERT)
        self.bouton(bas, "Annuler", f.destroy, GRIS)
        tk.Label(f, text="🎲 = générer un mot de passe solide   👁 = afficher / cacher",
                 bg=CARTE, fg=GRIS, font=("Segoe UI", 9)).grid(row=6, column=0, columnspan=3, pady=(8, 0))
        champs["site"].focus_set()


# =============================================================
#  📊 RAPPORT DE LA SEMAINE  -  statistiques au jour le jour
# =============================================================

FICHIER_STATS = DOSSIER_APPLI / "stats.json"


def charger_json(fichier, defaut):
    try:
        return json.loads(Path(fichier).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def ecrire_json(fichier, donnees):
    try:
        DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
        Path(fichier).write_text(json.dumps(donnees, indent=1, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def jours_semaine(decalage=0):
    """Les 7 dates (lundi -> dimanche) de la semaine. decalage=-1 : semaine dernière."""
    aujourd_hui = time.time()
    lundi = aujourd_hui - time.localtime(aujourd_hui).tm_wday * 86400 + decalage * 7 * 86400
    return [time.strftime("%Y-%m-%d", time.localtime(lundi + i * 86400)) for i in range(7)]


def bilan_semaine(stats, temps, decalage=0):
    jours = jours_semaine(decalage)
    par_jeu = {}
    for j in jours:
        for jeu, sec in temps.get(j, {}).items():
            par_jeu[jeu] = par_jeu.get(jeu, 0) + sec
    valeurs = lambda cle: [stats.get(j, {}).get(cle, 0) for j in jours]
    return {
        "jours": jours,
        "jeu_total": sum(par_jeu.values()),
        "top": sorted(par_jeu.items(), key=lambda x: x[1], reverse=True)[:3],
        "cpu_max": max(valeurs("cpu_max")),
        "gpu_max": max(valeurs("gpu_max")),
        "nettoye": sum(valeurs("nettoye")),
        "maj": sum(valeurs("maj")),
    }


def noter(self, cle, valeur, mode="max"):
    """Ajoute une statistique du jour (mode "max" = on garde la plus grande, "somme" = on additionne)."""
    if valeur is None:
        return
    jour = self.stats.setdefault(time.strftime("%Y-%m-%d"), {})
    jour[cle] = max(jour.get(cle, 0), valeur) if mode == "max" else jour.get(cle, 0) + valeur
    self.stats_a_sauver = True


def sauver_stats(self):
    if self.stats_a_sauver:
        ecrire_json(FICHIER_STATS, self.stats)
        self.stats_a_sauver = False
    self.racine.after(60 * 1000, self.sauver_stats)


def onglet_rapport(self, cadre):
    self.stats = charger_json(FICHIER_STATS, {})
    self.stats_a_sauver = False
    self.racine.after(60 * 1000, self.sauver_stats)
    haut = tk.Frame(cadre, bg=CARTE)
    haut.pack(fill="x")
    self.texte(haut, "Rapport de la semaine", 13, gras=True).pack_configure(side="left")
    self.choix_semaine = tk.IntVar(value=-1)
    for valeur, nom in ((0, "Cette semaine"), (-1, "Semaine dernière")):
        tk.Radiobutton(haut, text=nom, variable=self.choix_semaine, value=valeur, command=self.afficher_rapport,
                       bg=CARTE, fg=TEXTE, selectcolor=FOND, activebackground=CARTE, activeforeground=TEXTE,
                       font=("Segoe UI", 10), highlightthickness=0, bd=0).pack(side="right", padx=6)
    self.cadre_rapport = tk.Frame(cadre, bg=CARTE)
    self.cadre_rapport.pack(fill="both", expand=True, pady=(10, 0))
    self.afficher_rapport()
    # Le lundi (ou au 1er lancement de la semaine), on te le montre
    semaine = time.strftime("%G-%V")
    if REGLAGES.get("dernier_rapport") != semaine:
        REGLAGES["dernier_rapport"] = semaine
        enregistrer_reglages()
        if any(bilan_semaine(self.stats, charger_temps(), -1).values()):
            self.racine.after(2500, self.annoncer_rapport)


def annoncer_rapport(self):
    page = next((i for i, p in enumerate(self.navigation.pages) if p[1] == "Rapport"), None)
    if page is not None:
        self.choix_semaine.set(-1)
        self.afficher_rapport()
        self.navigation.select(page)
    if self.icone:
        try:
            self.icone.notify("Ton rapport de la semaine est prêt 📊", "Boîte à outils")
        except Exception:
            pass


def afficher_rapport(self):
    for w in self.cadre_rapport.winfo_children():
        w.destroy()
    decalage = self.choix_semaine.get()
    b = bilan_semaine(self.stats, charger_temps(), decalage)
    avant = bilan_semaine(self.stats, charger_temps(), decalage - 1)
    debut = time.strftime("%d/%m", time.strptime(b["jours"][0], "%Y-%m-%d"))
    fin = time.strftime("%d/%m", time.strptime(b["jours"][-1], "%Y-%m-%d"))
    tk.Label(self.cadre_rapport, text=f"Du {debut} au {fin}", bg=CARTE, fg=GRIS, font=("Segoe UI", 10),
             anchor="w").pack(fill="x")

    grille = tk.Frame(self.cadre_rapport, bg=CARTE)
    grille.pack(fill="x", pady=8)
    ecart = b["jeu_total"] - avant["jeu_total"]
    tendance = (f"{'+' if ecart >= 0 else '−'}{duree_lisible(abs(ecart))} vs semaine d'avant"
                if avant["jeu_total"] else "")
    cases = [
        ("Temps de jeu", duree_lisible(b["jeu_total"]), tendance, CYAN),
        ("CPU le plus chaud", f"{b['cpu_max']:.0f}°" if b["cpu_max"] else "--",
         "⚠️ a dépassé l'alerte" if b["cpu_max"] >= ALERTE_CPU else "RAS", ROUGE if b["cpu_max"] >= ALERTE_CPU else CYAN),
        ("GPU le plus chaud", f"{b['gpu_max']:.0f}°" if b["gpu_max"] else "--",
         "⚠️ a dépassé l'alerte" if b["gpu_max"] >= ALERTE_GPU else "RAS", ROUGE if b["gpu_max"] >= ALERTE_GPU else ROSE),
        ("Place libérée", taille_lisible(b["nettoye"]), "avec le nettoyeur", VERT),
        ("Mises à jour", str(int(b["maj"])), "applis mises à jour", VIOLET),
    ]
    for col, (titre, valeur, detail, couleur) in enumerate(cases):
        grille.columnconfigure(col, weight=1, uniform="r")
        c = Carte(grille, couleur=FOND, padx=12, pady=10)
        c.grid(row=0, column=col, sticky="nsew", padx=4)
        tk.Label(c, text=titre.upper(), bg=FOND, fg=GRIS, font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x")
        tk.Label(c, text=valeur, bg=FOND, fg=couleur, font=("Segoe UI", 20, "bold"), anchor="w").pack(fill="x")
        tk.Label(c, text=detail, bg=FOND, fg=GRIS, font=("Segoe UI", 9), anchor="w").pack(fill="x")

    tk.Label(self.cadre_rapport, text="TES JEUX LES PLUS JOUÉS", bg=CARTE, fg=GRIS, font=("Segoe UI", 9, "bold"),
             anchor="w").pack(fill="x", pady=(10, 4))
    if not b["top"]:
        tk.Label(self.cadre_rapport, text="Pas de partie cette semaine-là.", bg=CARTE, fg=GRIS,
                 font=("Segoe UI", 10), anchor="w").pack(fill="x")
    for rang, (jeu, sec) in enumerate(b["top"], start=1):
        medaille = ["🥇", "🥈", "🥉"][rang - 1]
        tk.Label(self.cadre_rapport, text=f"{medaille}  {jeu}  ·  {duree_lisible(sec)}", bg=CARTE, fg=TEXTE,
                 font=("Segoe UI", 12), anchor="w").pack(fill="x", pady=1)


# =============================================================
#  🎛 PROFILS  -  Jeu / Travail / Silence en un clic
# =============================================================

PROFILS_DEFAUT = {
    "Jeu":     {"icone": "🎮", "plan": "SCHEME_MIN", "fermer": ["OneDrive.exe"], "ouvrir": ["Discord", "steam://open/main"], "volume": 80},
    "Travail": {"icone": "💼", "plan": "SCHEME_BALANCED", "fermer": [], "ouvrir": [], "volume": 50},
    "Silence": {"icone": "🌙", "plan": "SCHEME_MAX", "fermer": ["Steam.exe"], "ouvrir": [], "volume": 15},
}
NOMS_PLANS = {"SCHEME_MIN": "Performances", "SCHEME_BALANCED": "Utilisation normale", "SCHEME_MAX": "Économie d'énergie"}
REGLAGES_DEFAUT["profils"] = PROFILS_DEFAUT
REGLAGES.setdefault("profils", json.loads(json.dumps(PROFILS_DEFAUT)))


def regler_volume(pourcentage):
    """Règle le volume en « appuyant » sur les touches volume du clavier (chaque appui = 2 %)."""
    import ctypes
    appuyer = lambda touche: (ctypes.windll.user32.keybd_event(touche, 0, 0, 0),
                              ctypes.windll.user32.keybd_event(touche, 0, 2, 0))
    for _ in range(50):
        appuyer(0xAE)   # volume -
    for _ in range(round(pourcentage / 2)):
        appuyer(0xAF)   # volume +


def appliquer_profil(nom):
    """Fait tout le travail d'un profil. Renvoie un petit compte rendu."""
    p = REGLAGES["profils"][nom]
    fait = []
    if p.get("plan") and activer_plan(p["plan"]):
        fait.append(f"plan {NOMS_PLANS.get(p['plan'], p['plan'])}")
    for exe in p.get("fermer", []):
        res = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if res.returncode == 0:
            fait.append(f"{exe} fermé")
    for appli in p.get("ouvrir", []):
        try:
            if appli.lower() == "discord":
                subprocess.Popen([str(Path(LOCALAPPDATA) / "Discord" / "Update.exe"), "--processStart", "Discord.exe"])
            else:
                os.startfile(appli)
            fait.append(f"{appli} ouvert")
        except OSError:
            pass
    if p.get("volume") is not None:
        try:
            regler_volume(int(p["volume"]))
            fait.append(f"volume {p['volume']} %")
        except (AttributeError, OSError, ValueError):
            pass
    REGLAGES["profil_actif"] = nom
    enregistrer_reglages()
    return fait


def onglet_profils(self, cadre):
    self.texte(cadre, "Profils", 13, gras=True)
    self.texte(cadre, "Un clic change le plan d'alimentation, ferme ou ouvre des applis et règle le volume.", couleur=GRIS)
    self.cadre_profils = tk.Frame(cadre, bg=CARTE)
    self.cadre_profils.pack(fill="x", pady=8)
    self.info_profil = self.texte(cadre, "", 10, VERT)
    self.texte(cadre, "Modifier les profils", 11, gras=True).pack_configure(pady=(14, 2))
    self.texte(cadre, "Applis séparées par des virgules. Pour ouvrir : un chemin, un lien (steam://...) ou « Discord ».",
               9, GRIS)
    edition = tk.Frame(cadre, bg=CARTE)
    edition.pack(fill="x", pady=4)
    self.champs_profils = {}
    for col, titre in enumerate(["", "Plan d'alim", "Fermer", "Ouvrir", "Volume %"]):
        tk.Label(edition, text=titre, bg=CARTE, fg=GRIS, font=("Segoe UI", 9, "bold")).grid(row=0, column=col, sticky="w", padx=4)
    for ligne, (nom, p) in enumerate(REGLAGES["profils"].items(), start=1):
        tk.Label(edition, text=f"{p.get('icone', '')} {nom}", bg=CARTE, fg=TEXTE, font=("Segoe UI", 10, "bold")).grid(
            row=ligne, column=0, sticky="w", padx=4, pady=3)
        plan = ttk.Combobox(edition, values=list(NOMS_PLANS.values()), state="readonly", width=18)
        plan.set(NOMS_PLANS.get(p.get("plan"), "Utilisation normale"))
        plan.grid(row=ligne, column=1, padx=4)
        champs = {"plan": plan}
        for col, cle, larg in ((2, "fermer", 18), (3, "ouvrir", 22), (4, "volume", 5)):
            e = tk.Entry(edition, bg=FOND, fg=TEXTE, insertbackground=TEXTE, relief="flat", font=("Segoe UI", 10), width=larg)
            v = p.get(cle, "")
            e.insert(0, ", ".join(v) if isinstance(v, list) else str(v))
            e.grid(row=ligne, column=col, padx=4, ipady=3)
            champs[cle] = e
        self.champs_profils[nom] = champs
    self.bouton(cadre, "💾 Enregistrer les profils", self.sauver_profils, VERT)
    self.dessiner_profils()


def dessiner_profils(self):
    for w in self.cadre_profils.winfo_children():
        w.destroy()
    actif = REGLAGES.get("profil_actif")
    for col, (nom, p) in enumerate(REGLAGES["profils"].items()):
        self.cadre_profils.columnconfigure(col, weight=1, uniform="p")
        couleur = [CYAN, VIOLET, ROSE][col % 3]
        c = tk.Frame(self.cadre_profils, bg=FOND, padx=14, pady=12, highlightthickness=2 if nom == actif else 1,
                     highlightbackground=couleur if nom == actif else BORD)
        c.grid(row=0, column=col, sticky="nsew", padx=5)
        tk.Label(c, text=f"{p.get('icone', '')} {nom}", bg=FOND, fg=couleur, font=("Segoe UI", 16, "bold"),
                 anchor="w").pack(fill="x")
        resume = [NOMS_PLANS.get(p.get("plan"), "")]
        if p.get("fermer"):
            resume.append("ferme " + ", ".join(p["fermer"]))
        if p.get("ouvrir"):
            resume.append("ouvre " + ", ".join(a.split("://")[0] if "://" in a else Path(a).stem for a in p["ouvrir"]))
        resume.append(f"volume {p.get('volume', '--')} %")
        tk.Label(c, text="\n".join(resume), bg=FOND, fg=GRIS, font=("Segoe UI", 9), anchor="w", justify="left",
                 wraplength=220).pack(fill="x", pady=(4, 8))
        tk.Button(c, text="✓ Actif" if nom == actif else "Activer", relief="flat", bg=couleur, fg=texte_sur(couleur),
                  font=("Segoe UI", 10, "bold"), cursor="hand2", padx=12, pady=4,
                  command=lambda n=nom: self.activer_profil(n)).pack(anchor="w")


def activer_profil(self, nom):
    self.info_profil.config(text=f"Profil {nom} en cours...", fg=GRIS)

    def ensuite(fait):
        if isinstance(fait, Exception):
            self.info_profil.config(text=f"Erreur : {fait}", fg=ROUGE)
            return
        self.info_profil.config(text=f"✅ Profil {nom} : " + (", ".join(fait) or "rien à changer"), fg=VERT)
        self.dessiner_profils()
    self.en_fond(lambda: appliquer_profil(nom), ensuite)


def sauver_profils(self):
    plans = {v: k for k, v in NOMS_PLANS.items()}
    for nom, champs in self.champs_profils.items():
        p = REGLAGES["profils"][nom]
        p["plan"] = plans.get(champs["plan"].get(), "SCHEME_BALANCED")
        p["fermer"] = [a.strip() for a in champs["fermer"].get().split(",") if a.strip()]
        p["ouvrir"] = [a.strip() for a in champs["ouvrir"].get().split(",") if a.strip()]
        volume = champs["volume"].get().strip()
        p["volume"] = max(0, min(100, int(volume))) if volume.isdigit() else None
    enregistrer_reglages()
    self.dessiner_profils()
    self.info_profil.config(text="✅ Profils enregistrés", fg=VERT)


# =============================================================
#  🔊 SOUNDBOARD  -  des sons envoyés dans Discord comme ton micro
# =============================================================
#  Le principe : on joue le son DEUX fois en même temps :
#   - dans un « câble audio virtuel » (VB-CABLE) que Discord écoute comme un micro
#   - dans ton casque, pour que tu l'entendes aussi
#  Les librairies sounddevice et soundfile servent à choisir la sortie audio.

DOSSIER_SONS = DOSSIER_APPLI / "sons"
REGLAGES_DEFAUT.update({"sons": [], "sortie_discord": "", "sortie_ecoute": ""})
for _cle in ("sons", "sortie_discord", "sortie_ecoute"):
    REGLAGES.setdefault(_cle, REGLAGES_DEFAUT[_cle])
COULEURS_SONS = [CYAN, ROSE, VIOLET, VERT, ORANGE, "#4f8cff"]
lectures_en_cours = []   # pour pouvoir tout arrêter


def charger_audio(demander_parent=None):
    """Importe sounddevice + soundfile (propose de les installer s'il manque)."""
    try:
        import sounddevice
        import soundfile
        return sounddevice, soundfile
    except (ImportError, OSError):
        pass
    if demander_parent is None or not messagebox.askyesno(
            "Soundboard", "Le soundboard a besoin de 2 librairies (sounddevice et soundfile).\n\n"
                          "Les installer maintenant ? (environ 30 secondes)", parent=demander_parent):
        return None
    if not installer_paquets("sounddevice", "soundfile"):
        messagebox.showerror("Oups", "Installation ratée. Dans PowerShell :\npython -m pip install sounddevice soundfile")
        return None
    try:
        import sounddevice
        import soundfile
        return sounddevice, soundfile
    except (ImportError, OSError):
        return None


def sorties_audio(sd):
    """Noms des sorties audio (on garde celles de l'API « MME », la plus tolérante)."""
    mme = next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == "MME"), None)
    noms = []
    for d in sd.query_devices():
        if d["max_output_channels"] > 0 and (mme is None or d["hostapi"] == mme) and d["name"] not in noms:
            noms.append(d["name"])
    return noms


def index_sortie(sd, nom):
    mme = next((i for i, h in enumerate(sd.query_hostapis()) if h["name"] == "MME"), None)
    for i, d in enumerate(sd.query_devices()):
        if d["name"] == nom and d["max_output_channels"] > 0 and (mme is None or d["hostapi"] == mme):
            return i
    return None


def jouer_son(son_id):
    """Joue un son du soundboard (appelé depuis la fenêtre, le Stream Deck ou le téléphone)."""
    son = next((s for s in REGLAGES["sons"] if s["id"] == son_id), None)
    audio = charger_audio()
    if not son or not audio:
        return False
    sd, sf = audio
    donnees, frequence = sf.read(son["fichier"], dtype="float32", always_2d=True)
    donnees = donnees * (son.get("volume", 80) / 100)
    cibles = []
    if REGLAGES.get("sortie_discord"):   # le câble virtuel écouté par Discord
        cibles.append(index_sortie(sd, REGLAGES["sortie_discord"]))
    ecoute = REGLAGES.get("sortie_ecoute")
    if ecoute == "":                     # "" = la sortie par défaut de Windows (ton casque)
        cibles.append(sd.default.device[1])
    elif ecoute:
        cibles.append(index_sortie(sd, ecoute))
    for index in dict.fromkeys(c for c in cibles if c is not None and c >= 0):   # sans doublons
        canaux = min(donnees.shape[1], sd.query_devices(index)["max_output_channels"])

        def lire(i=index, c=canaux):
            flux = None
            try:
                flux = sd.OutputStream(device=i, samplerate=frequence, channels=c, dtype="float32")
                lectures_en_cours.append(flux)
                with flux:
                    flux.write(donnees[:, :c].copy())
            except Exception:
                pass
            finally:
                if flux in lectures_en_cours:
                    lectures_en_cours.remove(flux)
        threading.Thread(target=lire, daemon=True).start()
    return True


def stopper_sons():
    for flux in list(lectures_en_cours):
        try:
            flux.abort()
        except Exception:
            pass


def onglet_soundboard(self, cadre):
    haut = tk.Frame(cadre, bg=CARTE)
    haut.pack(fill="x")
    self.texte(haut, "Soundboard", 13, gras=True).pack_configure(side="left")
    tk.Button(haut, text="⏹ Stop", relief="flat", bg=ROUGE, fg="white", font=("Segoe UI", 10, "bold"),
              cursor="hand2", padx=10, command=stopper_sons).pack(side="right")
    tk.Button(haut, text="➕ Ajouter un son", relief="flat", bg=VERT, fg=FOND, font=("Segoe UI", 10, "bold"),
              cursor="hand2", padx=10, command=self.ajouter_son).pack(side="right", padx=8)

    sorties = tk.Frame(cadre, bg=CARTE)
    sorties.pack(fill="x", pady=(8, 2))
    tk.Label(sorties, text="Vers Discord (câble virtuel) :", bg=CARTE, fg=GRIS, font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
    tk.Label(sorties, text="Dans ton casque :", bg=CARTE, fg=GRIS, font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w")
    self.choix_discord = ttk.Combobox(sorties, state="readonly", width=40)
    self.choix_ecoute = ttk.Combobox(sorties, state="readonly", width=40)
    self.choix_discord.grid(row=0, column=1, padx=8, pady=2, sticky="w")
    self.choix_ecoute.grid(row=1, column=1, padx=8, pady=2, sticky="w")
    for c in (self.choix_discord, self.choix_ecoute):
        c.bind("<<ComboboxSelected>>", lambda e: self.sauver_sorties())
    tk.Button(sorties, text="🔄", relief="flat", bg=FOND, fg=TEXTE, command=self.lister_sorties).grid(row=0, column=2)
    self.aide_soundboard = tk.Label(cadre, text="", bg=CARTE, fg=GRIS, font=("Segoe UI", 9), anchor="w",
                                    justify="left", wraplength=780)
    self.aide_soundboard.pack(fill="x", pady=(2, 8))
    self.grille_sons = tk.Frame(cadre, bg=CARTE)
    self.grille_sons.pack(fill="both", expand=True)
    self.texte(cadre, "Clic = jouer  ·  clic droit = renommer, volume, couleur, supprimer  ·  "
                      "les mêmes sons sont dispo sur le Stream Deck et le téléphone", 9, GRIS)
    self.lister_sorties()
    self.dessiner_sons()


def lister_sorties(self):
    audio = charger_audio()
    if not audio:
        self.aide_soundboard.config(text="⚠️ Clique sur « Ajouter un son » : je te proposerai d'installer ce qu'il faut.")
        return
    noms = sorties_audio(audio[0])
    self.choix_discord.config(values=["(aucune)"] + noms)
    self.choix_ecoute.config(values=["(sortie par défaut)", "(aucune)"] + noms)
    self.choix_discord.set(REGLAGES.get("sortie_discord") or "(aucune)")
    self.choix_ecoute.set(REGLAGES.get("sortie_ecoute") or "(sortie par défaut)")
    cable = [n for n in noms if "CABLE Input" in n or "VoiceMeeter Input" in n]
    if cable and not REGLAGES.get("sortie_discord"):
        self.choix_discord.set(cable[0])
        self.sauver_sorties()
    if not cable:
        self.aide_soundboard.config(text="⚠️ Pour que Discord entende les sons, installe VB-CABLE (gratuit, vb-audio.com/Cable), "
                                         "puis relance. Je t'expliquerai les 2 réglages Discord/Windows à faire.")
    else:
        self.aide_soundboard.config(text="✅ Câble virtuel trouvé. Dans Discord : Paramètres > Voix et vidéo > Périphérique d'entrée "
                                         "= « CABLE Output ». Et pour ta voix : Windows > Son > ton micro > Propriétés > "
                                         "Écouter > coche « Écouter ce périphérique » et choisis « CABLE Input ».")


def sauver_sorties(self):
    d, e = self.choix_discord.get(), self.choix_ecoute.get()
    REGLAGES["sortie_discord"] = "" if d.startswith("(") else d
    REGLAGES["sortie_ecoute"] = "" if e == "(sortie par défaut)" else (None if e == "(aucune)" else e)
    enregistrer_reglages()


def dessiner_sons(self):
    for w in self.grille_sons.winfo_children():
        w.destroy()
    if not REGLAGES["sons"]:
        tk.Label(self.grille_sons, text="Aucun son pour l'instant. Ajoute des .mp3, .wav ou .ogg !", bg=CARTE, fg=GRIS,
                 font=("Segoe UI", 11)).pack(pady=30)
        return
    for i, son in enumerate(REGLAGES["sons"]):
        self.grille_sons.columnconfigure(i % 4, weight=1, uniform="s")
        couleur = son.get("couleur", CYAN)
        pad = tk.Button(self.grille_sons, text=son["nom"], bg=FOND, fg=couleur, activebackground=couleur,
                        activeforeground=FOND, relief="flat", font=("Segoe UI", 12, "bold"), wraplength=150,
                        highlightthickness=2, highlightbackground=couleur, cursor="hand2", height=3,
                        command=lambda s=son["id"]: threading.Thread(target=jouer_son, args=(s,), daemon=True).start())
        pad.grid(row=i // 4, column=i % 4, sticky="nsew", padx=5, pady=5)
        pad.bind("<Button-3>", lambda e, s=son: self.menu_son(e, s))


def ajouter_son(self):
    if not charger_audio(self.racine):
        return
    self.lister_sorties()
    fichiers = filedialog.askopenfilenames(title="Choisis un ou plusieurs sons",
                                           filetypes=[("Sons", "*.mp3 *.wav *.ogg *.flac"), ("Tous", "*.*")])
    DOSSIER_SONS.mkdir(parents=True, exist_ok=True)
    for f in fichiers:
        source = Path(f)
        copie = DOSSIER_SONS / source.name   # on garde une copie, même si tu supprimes l'original
        if not copie.exists():
            shutil.copy2(source, copie)
        REGLAGES["sons"].append({"id": secrets.token_hex(4), "nom": source.stem[:24], "fichier": str(copie),
                                 "volume": 80, "couleur": COULEURS_SONS[len(REGLAGES["sons"]) % len(COULEURS_SONS)]})
    enregistrer_reglages()
    self.dessiner_sons()


def menu_son(self, evenement, son):
    from tkinter import simpledialog
    menu = tk.Menu(self.racine, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=CYAN, activeforeground=FOND)

    def renommer():
        nom = simpledialog.askstring("Renommer", "Nouveau nom :", initialvalue=son["nom"], parent=self.racine)
        if nom:
            son["nom"] = nom[:24]
            enregistrer_reglages()
            self.dessiner_sons()

    def volume():
        v = simpledialog.askinteger("Volume", "Volume (0 à 150 %) :", initialvalue=son.get("volume", 80),
                                    minvalue=0, maxvalue=150, parent=self.racine)
        if v is not None:
            son["volume"] = v
            enregistrer_reglages()

    def couleur():
        son["couleur"] = COULEURS_SONS[(COULEURS_SONS.index(son.get("couleur", CYAN)) + 1) % len(COULEURS_SONS)] \
            if son.get("couleur") in COULEURS_SONS else CYAN
        enregistrer_reglages()
        self.dessiner_sons()

    def supprimer_son():
        if messagebox.askyesno("Supprimer", f"Retirer « {son['nom']} » du soundboard ?"):
            REGLAGES["sons"].remove(son)
            enregistrer_reglages()
            self.dessiner_sons()
    menu.add_command(label="✏️ Renommer", command=renommer)
    menu.add_command(label="🔉 Volume", command=volume)
    menu.add_command(label="🎨 Changer la couleur", command=couleur)
    menu.add_separator()
    menu.add_command(label="🗑 Supprimer", command=supprimer_son)
    menu.tk_popup(evenement.x_root, evenement.y_root)


# =============================================================
#  🎵 MUSIQUE + 🎙️ MICRO
# =============================================================
#  La musique : on « appuie » sur les touches multimédia du clavier
#  (celles que Spotify, YouTube... écoutent toutes).
#  Le micro : on passe par pycaw, une librairie qui parle au son de Windows.

TOUCHES_MEDIA = {"playpause": 0xB3, "suivant": 0xB0, "precedent": 0xB1, "volplus": 0xAF, "volmoins": 0xAE}


def touche_media(action):
    import ctypes
    touche = TOUCHES_MEDIA.get(action)
    if touche is None:
        return False
    repetitions = 3 if action.startswith("vol") else 1   # 3 crans = 6 % de volume
    for _ in range(repetitions):
        ctypes.windll.user32.keybd_event(touche, 0, 0, 0)
        ctypes.windll.user32.keybd_event(touche, 0, 2, 0)   # 2 = touche relâchée
    return True


def musique_en_cours():
    """Le titre de la fenêtre de Spotify, c'est « Artiste - Titre » (ou « Spotify » en pause)."""
    try:
        sortie = subprocess.run(["tasklist", "/v", "/fo", "csv", "/nh", "/fi", "imagename eq Spotify.exe"],
                                capture_output=True, text=True, encoding=ENCODAGE, errors="replace", timeout=10,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for ligne in sortie.splitlines():
        titre = ligne.rsplit('","', 1)[-1].strip('"')   # dernière colonne = titre de la fenêtre
        if " - " in titre:
            return titre
    return None


def lister_micros():
    """Noms des micros (périphériques d'enregistrement) actifs : [(nom, id), ...]."""
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities
    except ImportError:
        return []
    comtypes.CoInitialize()
    micros = []
    for d in AudioUtilities.GetAllDevices():
        try:
            actif = "Active" in str(getattr(d, "state", "Active"))
            if actif and d.id and d.id.startswith("{0.0.1.") and d.FriendlyName:   # {0.0.1.* = enregistrement
                micros.append((d.FriendlyName, d.id))
        except Exception:
            pass
    return sorted(micros)


def volume_micro():
    """L'objet qui contrôle le micro choisi dans les Réglages (sinon celui par défaut de Windows)."""
    try:
        import comtypes
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    except ImportError:
        return None
    comtypes.CoInitialize()   # obligatoire dans chaque « fil » qui parle au son de Windows
    choisi = REGLAGES.get("micro_nom")
    if choisi:
        for nom, ident in lister_micros():
            if nom == choisi:
                from ctypes import POINTER, cast
                appareil = AudioUtilities.GetDeviceEnumerator().GetDevice(ident)
                interface = appareil.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
                return cast(interface, POINTER(IAudioEndpointVolume))
    micro = AudioUtilities.GetMicrophone()
    if micro is None:
        return None
    if hasattr(micro, "EndpointVolume"):   # nouvelles versions de pycaw
        return micro.EndpointVolume
    from ctypes import POINTER, cast
    interface = micro.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def micro(action="etat"):
    """action = "etat", "basculer", "couper" ou "activer". Renvoie True si le micro est coupé (None si inconnu)."""
    try:
        v = volume_micro()
        if v is None:
            return None
        coupe = bool(v.GetMute())
        if action in ("basculer", "couper", "activer"):
            coupe = {"basculer": not coupe, "couper": True, "activer": False}[action]
            v.SetMute(int(coupe), None)
        return coupe
    except Exception:
        return None


def suivre_musique(self):
    """Toutes les 3 s : titre en cours + état du micro."""
    def ensuite(res):
        if not isinstance(res, Exception):
            self.titre_musique, self.micro_coupe = res
            artiste, _, morceau = (self.titre_musique or "").partition(" - ")
            self.dash_musique.config(text=(morceau or artiste or "Rien en lecture")[:34],
                                     fg=TEXTE if self.titre_musique else GRIS)
            self.dash_artiste.config(text=artiste if morceau else "")
            self.afficher_micro()
        self.racine.after(3000, self.suivre_musique)
    self.en_fond(lambda: (musique_en_cours(), micro("etat")), ensuite)


def afficher_micro(self):
    if self.micro_coupe is None:
        self.info_micro.config(text="?", fg=GRIS)
    elif self.micro_coupe:
        self.info_micro.config(text="COUPÉ · réactiver", fg=ROUGE)
    else:
        self.info_micro.config(text="actif · couper", fg=VERT)


def basculer_micro(self):
    try:
        import pycaw  # noqa: F401  (on vérifie juste qu'elle est là)
    except ImportError:
        if not messagebox.askyesno("Micro", "Pour couper le micro, il faut la librairie pycaw.\n\nL'installer maintenant ?"):
            return
        if not installer_paquets("pycaw"):
            messagebox.showerror("Oups", "Installation ratée. Dans PowerShell :\npython -m pip install pycaw")
            return

    def ensuite(coupe):
        if not isinstance(coupe, Exception):
            self.micro_coupe = coupe
            self.afficher_micro()
    self.en_fond(lambda: micro("basculer"), ensuite)


JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def maj_horloge(self):
    t = time.localtime()
    self.horloge.config(text=f"{JOURS[t.tm_wday]} {t.tm_mday} {MOIS[t.tm_mon - 1]} · {t.tm_hour:02d}:{t.tm_min:02d}")
    self.racine.after(5000, self.maj_horloge)


def verifier_maj_appli(self, au_demarrage=False):
    """Regarde s'il y a une nouvelle version (au démarrage puis toutes les 6 h)."""
    def ensuite(infos):
        if isinstance(infos, dict):
            self.maj_dispo = infos
            self.bouton_maj_appli.config(text=f"⬇  Mise à jour v{infos['version']}", state="normal")
            self.bouton_maj_appli.pack(side="right", padx=(12, 0))
            if au_demarrage and REGLAGES.get("maj_auto", True) and not self.session:
                self.lancer_maj_appli(sans_question=True)
        self.racine.after(6 * 3600 * 1000, self.verifier_maj_appli)
    self.en_fond(chercher_maj, ensuite)


def lancer_maj_appli(self, sans_question=False):
    infos = self.maj_dispo
    if not infos:
        return
    if not sans_question:
        notes = infos.get("notes", "")
        if not messagebox.askyesno("Mise à jour", f"Installer la version {infos['version']} ?\n\n{notes}\n\n"
                                                  "La boîte à outils va redémarrer toute seule."):
            return
    self.bouton_maj_appli.config(text="⏳  Installation...", state="disabled")

    def ensuite(erreur):
        if isinstance(erreur, Exception):
            erreur = str(erreur)
        if erreur:
            self.bouton_maj_appli.config(text=f"⬇  Mise à jour v{infos['version']}", state="normal")
            messagebox.showerror("Mise à jour", f"Mise à jour impossible : {erreur}\nTa version actuelle continue de marcher.")
            return
        # On relance la nouvelle version, puis on ferme celle-ci
        arguments = [sys.executable, str(Path(__file__).resolve()), "--apres-maj"]
        if self.racine.state() == "withdrawn":
            arguments.append("--cache")
        subprocess.Popen(arguments, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.quitter()
    self.en_fond(lambda: installer_maj(infos), ensuite)


for _nom in ("maj_horloge", "verifier_maj_appli", "lancer_maj_appli"):
    setattr(BoiteAOutils, _nom, globals()[_nom])


for _nom in ("suivre_musique", "afficher_micro", "basculer_micro"):
    setattr(BoiteAOutils, _nom, globals()[_nom])


# =============================================================
#  📱 TÉLÉPHONE + STREAM DECK  -  un petit serveur web local
# =============================================================
#  La boîte à outils ouvre un mini site sur ton réseau (port 8765).
#  - Ton téléphone (même Wi-Fi) l'ouvre dans le navigateur, avec un code PIN.
#  - Le plugin Stream Deck lui parle pour jouer les sons / changer de profil.

import http.server
import socket

PORT_SERVEUR = 8765
REGLAGES.setdefault("pin_telephone", "".join(secrets.choice("0123456789") for _ in range(6)))


def ip_locale():
    """L'adresse de ton PC sur ton réseau (genre 192.168.1.20)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))   # aucun paquet n'est envoyé, ça sert juste à trouver la bonne carte
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def adresses_mac():
    """Cartes réseau branchées : [(nom, adresse MAC)] (utile pour allumer le PC à distance)."""
    commande = ("Get-NetAdapter -Physical | Where-Object Status -eq 'Up' | "
                "ForEach-Object { $_.InterfaceDescription + '|' + $_.MacAddress }")
    try:
        sortie = subprocess.run(["powershell", "-NoProfile", "-Command", commande], capture_output=True, text=True, encoding=ENCODAGE, errors="replace",
                                timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return [tuple(l.split("|", 1)) for l in sortie.splitlines() if "|" in l]


# La page du téléphone (HTML + CSS + JavaScript), rangée dans une grande chaîne de texte
PAGE_TELEPHONE = r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#07070c">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="CRZ PC">
<title>CRZ PC</title>
<style>
  :root { --fond:#07070c; --carte:#0f0f19; --bord:#23233a; --texte:#e9e9ff; --gris:#8a8aa8; --cyan:#00e5ff; --rose:#ff2bd6; --violet:#8b5cff; --vert:#3dffa2; --rouge:#ff4d6d; }
  * { box-sizing:border-box; margin:0; -webkit-tap-highlight-color:transparent; }
  body { background:var(--fond); color:var(--texte); font-family:-apple-system,"Segoe UI",Roboto,sans-serif; padding:16px 16px calc(24px + env(safe-area-inset-bottom)); }
  header { display:flex; justify-content:space-between; align-items:center; margin:4px 0 16px; }
  .logo { font-weight:800; font-size:20px; } .logo b { color:var(--cyan); } .logo i { color:var(--rose); font-style:normal; }
  #etat { font-size:12px; color:var(--gris); }
  h2 { font-size:11px; letter-spacing:2px; color:var(--gris); text-transform:uppercase; margin:18px 0 8px; }
  .grille { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
  .carte { background:var(--carte); border:1px solid var(--bord); border-radius:14px; padding:14px; }
  .lbl { font-size:11px; letter-spacing:1.5px; color:var(--gris); text-transform:uppercase; }
  .grand { font-size:40px; font-weight:800; line-height:1.1; }
  .moyen { font-size:20px; font-weight:700; }
  .sub { font-size:12px; color:var(--gris); }
  .cyan { color:var(--cyan); text-shadow:0 0 14px #00e5ff88; } .rose { color:var(--rose); text-shadow:0 0 14px #ff2bd688; }
  .barre { height:5px; background:#1c1c2c; border-radius:3px; margin-top:8px; } .barre i { display:block; height:100%; border-radius:3px; }
  button { font:inherit; border:none; cursor:pointer; }
  .pad { background:var(--carte); border:2px solid; border-radius:14px; padding:18px 8px; font-weight:700; font-size:15px; min-height:70px; }
  .pad:active { transform:scale(.96); filter:brightness(1.4); }
  .action { background:var(--carte); border:1px solid var(--bord); color:var(--texte); border-radius:12px; padding:14px; font-weight:600; font-size:14px; }
  .action.danger { border-color:#ff4d6d66; color:var(--rouge); }
  .profil { border-radius:12px; padding:14px 6px; font-weight:700; font-size:14px; background:var(--carte); color:var(--texte); border:1px solid var(--bord); }
  .profil.actif { border-color:var(--cyan); color:var(--cyan); box-shadow:0 0 12px #00e5ff44 inset; }
  .trois { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }
  #pin { position:fixed; inset:0; background:var(--fond); display:none; flex-direction:column; align-items:center; justify-content:center; gap:16px; padding:24px; }
  #pin input { background:var(--carte); border:1px solid var(--bord); color:var(--texte); font-size:28px; letter-spacing:10px; text-align:center; padding:12px; border-radius:12px; width:240px; }
  #pin button { background:var(--cyan); color:var(--fond); font-weight:800; padding:12px 28px; border-radius:12px; font-size:16px; }
  .note { font-size:12px; color:var(--gris); line-height:1.5; }
  #toast { position:fixed; left:50%; bottom:24px; transform:translateX(-50%); background:var(--carte); border:1px solid var(--cyan); color:var(--cyan); padding:10px 16px; border-radius:20px; font-size:13px; opacity:0; transition:opacity .2s; pointer-events:none; }
</style>
</head>
<body>
<header><div class="logo">⚡ <b>CRZ</b> <i>PC</i></div><div id="etat">connexion...</div></header>

<div class="grille">
  <div class="carte"><div class="lbl">CPU</div><div class="grand cyan" id="cpu">--°</div><div class="sub" id="cpuSub"></div><div class="barre"><i id="cpuBar" style="background:var(--cyan);width:0"></i></div></div>
  <div class="carte"><div class="lbl">GPU</div><div class="grand rose" id="gpu">--°</div><div class="sub" id="gpuSub"></div><div class="barre"><i id="gpuBar" style="background:var(--rose);width:0"></i></div></div>
  <div class="carte"><div class="lbl">RAM</div><div class="moyen" id="ram">--</div></div>
  <div class="carte"><div class="lbl">Connexion</div><div class="moyen" id="net">--</div></div>
</div>
<div class="carte" style="margin-top:10px"><div class="lbl">En jeu</div><div class="moyen cyan" id="jeu">--</div></div>

<h2>Musique</h2>
<div class="carte"><div class="moyen" id="musique" style="font-size:16px">Rien en lecture</div>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:12px">
    <button class="action" onclick="envoyer('media/precedent')">⏮</button><button class="action" onclick="envoyer('media/playpause')">⏯</button>
    <button class="action" onclick="envoyer('media/suivant')">⏭</button><button class="action" onclick="envoyer('media/volmoins')">🔉</button>
    <button class="action" onclick="envoyer('media/volplus')">🔊</button></div></div>
<button class="action" id="micro" style="width:100%;margin-top:10px;font-size:16px" onclick="envoyer('micro/basculer')">🎙 Micro</button>

<h2>Soundboard</h2>
<div class="grille" id="sons"></div>
<button class="action" style="width:100%;margin-top:10px" onclick="envoyer('stop/tout')">⏹ Stop les sons</button>

<h2>Profils</h2>
<div class="trois" id="profils"></div>

<h2>PC</h2>
<div class="grille">
  <button class="action" onclick="pc('verrouiller','Verrouiller le PC ?')">🔒 Verrouiller</button>
  <button class="action" onclick="pc('veille','Mettre le PC en veille ?')">🌙 Veille</button>
  <button class="action" onclick="pc('redemarrer','Redémarrer le PC dans 10 s ?')">🔄 Redémarrer</button>
  <button class="action danger" onclick="pc('eteindre','Éteindre le PC dans 10 s ?')">⏻ Éteindre</button>
</div>
<h2>Allumer le PC</h2>
<p class="note">Quand le PC est éteint, cette page ne répond plus. Pour l'allumer, utilise l'appli « Wake On LAN » configurée avec l'adresse MAC affichée dans la boîte à outils (page Téléphone).</p>

<div id="pin"><div class="logo" style="font-size:26px">⚡ <b>CRZ</b> <i>PC</i></div><div class="note">Entre le code PIN affiché dans la boîte à outils</div><input id="pinInput" inputmode="numeric" maxlength="6" autocomplete="off"><button onclick="validerPin()">Entrer</button></div>
<div id="toast"></div>

<script>
  let pin = localStorage.getItem("pin") || "";
  let profilsDessines = "", sonsDessines = "";
  const $ = (id) => document.getElementById(id);

  function toast(t) { $("toast").textContent = t; $("toast").style.opacity = 1; setTimeout(() => $("toast").style.opacity = 0, 1500); }
  function demanderPin() { $("pin").style.display = "flex"; $("pinInput").focus(); }
  function validerPin() { pin = $("pinInput").value.trim(); localStorage.setItem("pin", pin); $("pin").style.display = "none"; rafraichir(); }

  async function api(chemin, methode = "GET") {
    const r = await fetch("/api/" + chemin, { method: methode, headers: { "X-Pin": pin } });
    if (r.status === 401) { demanderPin(); throw new Error("PIN"); }
    return r.json();
  }
  async function envoyer(chemin) { try { await api(chemin, "POST"); toast("✓"); setTimeout(rafraichir, 400); } catch (e) {} }
  function pc(action, question) { if (confirm(question)) envoyer("pc/" + action); }

  function echapper(t) { return String(t).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

  async function rafraichir() {
    try {
      const e = await api("etat");
      $("etat").textContent = "● en ligne"; $("etat").style.color = "var(--vert)";
      if (e.cpu_temp != null) { $("cpu").textContent = Math.round(e.cpu_temp) + "°"; $("cpuBar").style.width = e.cpu_temp + "%"; }
      $("cpuSub").textContent = e.cpu_usage != null ? "Charge " + Math.round(e.cpu_usage) + " %" : "";
      if (e.gpu) { $("gpu").textContent = e.gpu[0] + "°"; $("gpuBar").style.width = e.gpu[0] + "%"; $("gpuSub").textContent = e.gpu[1] + " % · " + Math.round(e.gpu[3]) + " W"; }
      if (e.ram) $("ram").textContent = e.ram[0].toFixed(1) + " / " + Math.round(e.ram[1]) + " Go";
      if (e.reseau) $("net").textContent = "↓ " + e.reseau[0].toFixed(1) + "  ↑ " + e.reseau[1].toFixed(1);
      $("jeu").textContent = e.jeu || "Aucun jeu";
      $("musique").textContent = e.musique || "Rien en lecture";
      const m = $("micro");
      if (e.micro_coupe === true) { m.textContent = "🔇 Micro coupé (appuie pour réactiver)"; m.style.background = "var(--rouge)"; m.style.color = "#fff"; }
      else if (e.micro_coupe === false) { m.textContent = "🎙 Micro actif (appuie pour couper)"; m.style.background = "var(--carte)"; m.style.color = "var(--vert)"; }
      const s = JSON.stringify(e.sons);
      if (s !== sonsDessines) {
        sonsDessines = s;
        $("sons").innerHTML = e.sons.length ? e.sons.map((x) => `<button class="pad" style="border-color:${x.couleur};color:${x.couleur}" onclick="envoyer('son/${x.id}')">${echapper(x.nom)}</button>`).join("")
          : `<p class="note">Ajoute des sons dans la boîte à outils (page Soundboard).</p>`;
      }
      const p = JSON.stringify([e.profils, e.profil]);
      if (p !== profilsDessines) {
        profilsDessines = p;
        $("profils").innerHTML = e.profils.map((n) => `<button class="profil ${n === e.profil ? "actif" : ""}" onclick="envoyer('profil/${encodeURIComponent(n)}')">${echapper(n)}</button>`).join("");
      }
    } catch (err) {
      if (err.message !== "PIN") { $("etat").textContent = "● hors ligne"; $("etat").style.color = "var(--rouge)"; }
    }
  }
  if (!pin) demanderPin();
  rafraichir();
  setInterval(rafraichir, 2000);
</script>
</body>
</html>
'''



class ServeurLocal(http.server.BaseHTTPRequestHandler):
    app = None   # la boîte à outils, remplie au démarrage

    def log_message(self, *args):   # pas de messages dans la console
        pass

    def autorise(self):
        """Le PC lui-même (Stream Deck) n'a pas besoin du PIN, le téléphone oui."""
        if self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        return self.headers.get("X-Pin") == REGLAGES["pin_telephone"]

    def repondre(self, code, donnees, type_contenu="application/json; charset=utf-8"):
        corps = donnees if isinstance(donnees, bytes) else json.dumps(donnees, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", type_contenu)
        self.send_header("Access-Control-Allow-Origin", "*")   # le réglage du Stream Deck peut lire la liste des sons
        self.send_header("Access-Control-Allow-Headers", "X-Pin")
        self.end_headers()
        self.wfile.write(corps)

    def do_OPTIONS(self):
        self.repondre(204, b"")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.repondre(200, PAGE_TELEPHONE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if not self.autorise():
            self.repondre(401, {"erreur": "PIN"})
            return
        if self.path == "/api/etat":
            self.repondre(200, self.app.etat_pour_api())
        elif self.path == "/api/sons":
            self.repondre(200, [{"id": s["id"], "nom": s["nom"], "couleur": s.get("couleur", CYAN)}
                                for s in REGLAGES["sons"]])
        elif self.path == "/api/profils":
            self.repondre(200, {"profils": list(REGLAGES["profils"]), "actif": REGLAGES.get("profil_actif")})
        else:
            self.repondre(404, {"erreur": "inconnu"})

    def do_POST(self):
        if not self.autorise():
            self.repondre(401, {"erreur": "PIN"})
            return
        morceaux = self.path.strip("/").split("/")   # ex : api/son/ab12cd34
        if len(morceaux) != 3 or morceaux[0] != "api":
            self.repondre(404, {"erreur": "inconnu"})
            return
        _, quoi, valeur = morceaux
        valeur = urllib.request.unquote(valeur)
        if quoi == "son":
            self.repondre(200, {"ok": jouer_son(valeur)})
        elif quoi == "stop":
            stopper_sons()
            self.repondre(200, {"ok": True})
        elif quoi == "media":
            self.repondre(200, {"ok": touche_media(valeur)})
        elif quoi == "micro" and valeur in ("basculer", "couper", "activer"):
            coupe = micro(valeur)
            self.app.micro_coupe = coupe
            self.app.file_icone.put(("micro", coupe))   # pour mettre à jour le bouton de la fenêtre
            self.repondre(200, {"ok": coupe is not None, "micro_coupe": coupe})
        elif quoi == "profil" and valeur in REGLAGES["profils"]:
            self.app.file_icone.put(("profil", valeur))   # la fenêtre s'en occupe (elle seule touche à l'affichage)
            self.repondre(200, {"ok": True})
        elif quoi == "pc" and valeur in ("veille", "verrouiller", "eteindre", "redemarrer"):
            self.repondre(200, {"ok": True})
            action_pc(valeur)
        else:
            self.repondre(400, {"erreur": "action inconnue"})


def action_pc(action):
    import ctypes
    if action == "verrouiller":
        ctypes.windll.user32.LockWorkStation()
    elif action == "veille":
        # SetSuspendState(hibernation=False) = vraie mise en veille
        ctypes.windll.powrprof.SetSuspendState(False, False, False)
    elif action == "eteindre":
        subprocess.run(["shutdown", "/s", "/t", "10"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    elif action == "redemarrer":
        subprocess.run(["shutdown", "/r", "/t", "10"], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def demarrer_serveur(self):
    ServeurLocal.app = self
    try:
        self.serveur = http.server.ThreadingHTTPServer(("0.0.0.0", PORT_SERVEUR), ServeurLocal)
    except OSError:
        self.serveur = None   # port déjà pris (boîte à outils déjà ouverte ?)
        return
    threading.Thread(target=self.serveur.serve_forever, daemon=True).start()


def etat_pour_api(self):
    m = getattr(self, "dernieres_mesures", {}) or {}
    return {
        "cpu_temp": m.get("cpu_temp"), "cpu_usage": m.get("cpu_usage"),
        "gpu": m.get("gpu"), "ram": m.get("ram"), "reseau": getattr(self, "derniere_vitesse", None),
        "jeu": getattr(self, "jeu_actuel", None), "profil": REGLAGES.get("profil_actif"),
        "musique": getattr(self, "titre_musique", None), "micro_coupe": getattr(self, "micro_coupe", None),
        "sons": [{"id": s["id"], "nom": s["nom"], "couleur": s.get("couleur", CYAN)} for s in REGLAGES["sons"]],
        "profils": list(REGLAGES["profils"]),
    }


def onglet_telephone(self, cadre):
    enregistrer_reglages()   # pour garder le même code PIN
    self.texte(cadre, "Ton téléphone", 13, gras=True)
    if self.serveur is None:
        self.texte(cadre, f"⚠️ Le port {PORT_SERVEUR} est déjà utilisé : la boîte à outils est peut-être déjà ouverte.",
                   10, ROUGE)
    adresse = f"http://{ip_locale()}:{PORT_SERVEUR}"
    carte = Carte(cadre, couleur=FOND)
    carte.pack(fill="x", pady=8)
    tk.Label(carte, text="1. CONNECTE TON TÉLÉPHONE AU WI-FI DE LA MAISON, PUIS OUVRE :", bg=FOND, fg=GRIS,
             font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x")
    tk.Label(carte, text=adresse, bg=FOND, fg=CYAN, font=("Segoe UI", 22, "bold"), anchor="w").pack(fill="x")
    tk.Label(carte, text="2. TON CODE PIN :", bg=FOND, fg=GRIS, font=("Segoe UI", 9, "bold"), anchor="w").pack(fill="x", pady=(8, 0))
    tk.Label(carte, text=" ".join(REGLAGES["pin_telephone"]), bg=FOND, fg=ROSE, font=("Segoe UI", 22, "bold"),
             anchor="w").pack(fill="x")
    tk.Label(carte, text="3. Dans le navigateur du téléphone : Partager / ⋮ > « Ajouter à l'écran d'accueil » pour avoir une vraie icône.",
             bg=FOND, fg=GRIS, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(8, 0))
    self.texte(cadre, "Sur le téléphone : températures en direct, soundboard, profils, veille, verrouiller, éteindre.", 10)
    self.texte(cadre, "Si Windows demande l'autorisation du pare-feu au premier lancement, coche « Réseaux privés ».", 9, GRIS)

    self.texte(cadre, "Allumer le PC à distance (Wake-on-LAN)", 12, gras=True).pack_configure(pady=(14, 2))
    self.info_mac = self.texte(cadre, "Recherche de ta carte réseau...", 10)
    self.texte(cadre, "Quand le PC est éteint, il ne peut pas répondre lui-même : c'est une appli « Wake On LAN » sur ton "
                      "téléphone (ou ta box) qui le réveille avec l'adresse MAC ci-dessus. Je te guide ce soir pour les "
                      "réglages du BIOS MSI et de Windows.", 9, GRIS).config(wraplength=780)

    def ensuite(cartes):
        if isinstance(cartes, Exception) or not cartes:
            self.info_mac.config(text="Adresse MAC : introuvable (lance « getmac » dans PowerShell)")
        else:
            self.info_mac.config(text="   ".join(f"{nom[:40]} : {mac}" for nom, mac in cartes), fg=VERT)
    self.en_fond(adresses_mac, ensuite)


for _nom, _fonction in list(globals().items()):
    if _nom in ("noter", "sauver_stats", "onglet_rapport", "annoncer_rapport", "afficher_rapport",
                "onglet_profils", "dessiner_profils", "activer_profil", "sauver_profils",
                "onglet_soundboard", "lister_sorties", "sauver_sorties", "dessiner_sons", "ajouter_son", "menu_son",
                "demarrer_serveur", "etat_pour_api", "onglet_telephone"):
        setattr(BoiteAOutils, _nom, _fonction)   # on range ces fonctions dans la classe


if __name__ == "__main__":
    if "--apres-maj" in sys.argv:
        time.sleep(3)   # le temps que l'ancienne version se ferme
    charger_reglages()
    racine = tk.Tk()
    BoiteAOutils(racine, cache="--cache" in sys.argv)
    racine.mainloop()   # la fenêtre reste ouverte et attend tes clics
