# =============================================================
#  BOÎTE À OUTILS DE CRZ  -  version 3
# =============================================================
#  Lancer : double-clic sur ce fichier (.pyw = pas de console noire)
#           ou dans PowerShell :  python boite_a_outils.pyw
#
#  La fenêtre est faite avec "tkinter", la boîte à outils graphique
#  livrée avec Python (rien à installer).
#
#  Rien n'est supprimé ou déplacé sans que tu cliques "Oui".
#
#  COMMENT CE FICHIER EST RANGÉ (de haut en bas) :
#   1. Les réglages et les couleurs
#   2. La « logique » : nettoyer, lire les capteurs, trouver les jeux...
#      (des fonctions qui RENVOIENT un résultat, sans rien afficher)
#   3. Les briques d'affichage (cartes, boutons, onglets...)
#   4. La fenêtre et ses pages (classe BoiteAOutils)
#   5. Le coffre-fort, puis le petit serveur pour le téléphone et le Stream Deck
#   6. Le démarrage, tout en bas
#
#  Le coffre est rangé dans  C:\Users\<toi>\CoffreFort\coffre.dat
#  Tes réglages sont dans   C:\Users\<toi>\BoiteAOutils\reglages.json
# =============================================================

import base64
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

# Le son de Windows (voir FilAudio plus bas) : ce réglage doit être posé avant tout le reste.
sys.coinit_flags = 0


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

VERSION = "3.0.3"
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
    "micro_nom": "",             # "" = le micro par défaut de Windows
    # --- nouveautés de la v3 ---
    "notifications": True,       # petites alertes Windows (surchauffe, disque plein, fin de partie...)
    "alerte_disque": 90,         # % de remplissage à partir duquel un disque est signalé
    "auto_profil": False,        # changer de profil tout seul quand un jeu démarre / s'arrête
    "profil_en_jeu": "Jeu",
    "accent": "Cyan",            # couleur des boutons : Cyan, Rose, Violet ou Vert
    "mini_fenetre": False,       # petite fenêtre toujours visible avec les températures
    "mini_pos": None,
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
            return f"{octets:.1f} {unite}".replace(".", ",")
        octets /= 1024
    return f"{octets:.1f} To".replace(".", ",")


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


# Lecture du GPU directement par le pilote NVIDIA (nvml.dll), sans relancer nvidia-smi toutes les 2 s
# (lancer nvidia-smi en boucle peut provoquer des petites saccades / mini freeze).
_NVML = {"lib": None, "h": None, "ko": False}
_NVML_VERROU = threading.Lock()


def lire_gpu_nvml():
    import ctypes
    with _NVML_VERROU:
        if _NVML["ko"]:
            return None
        if _NVML["h"] is None:
            lib = None
            for chemin in ("nvml.dll", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(chemin)
                    break
                except (OSError, AttributeError):
                    pass
            h = ctypes.c_void_p()
            if lib is None or lib.nvmlInit_v2() != 0 or lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(h)) != 0:
                _NVML["ko"] = True
                return None
            _NVML["lib"], _NVML["h"] = lib, h
    lib, h = _NVML["lib"], _NVML["h"]

    class Utilisation(ctypes.Structure):
        _fields_ = [("gpu", ctypes.c_uint), ("memoire", ctypes.c_uint)]

    class Memoire(ctypes.Structure):
        _fields_ = [("total", ctypes.c_ulonglong), ("libre", ctypes.c_ulonglong), ("utilisee", ctypes.c_ulonglong)]

    temp, util, mem, watts = ctypes.c_uint(), Utilisation(), Memoire(), ctypes.c_uint()
    if (lib.nvmlDeviceGetTemperature(h, 0, ctypes.byref(temp)) != 0
            or lib.nvmlDeviceGetUtilizationRates(h, ctypes.byref(util)) != 0
            or lib.nvmlDeviceGetMemoryInfo(h, ctypes.byref(mem)) != 0):
        return None
    if lib.nvmlDeviceGetPowerUsage(h, ctypes.byref(watts)) != 0:
        watts.value = 0
    return temp.value, util.gpu, round(mem.utilisee / 1048576), watts.value / 1000


# --- LibreHardwareMonitor lu une seule fois par seconde, partagé par tous les capteurs ---
_LHM = {"quand": 0.0, "arbre": None}
_LHM_VERROU = threading.Lock()


def arbre_lhm():
    """Le contenu de http://127.0.0.1:8085/data.json (gardé 1 s pour ne pas le demander deux fois), ou None."""
    import urllib.request
    with _LHM_VERROU:
        if time.time() - _LHM["quand"] < 1.0:
            return _LHM["arbre"]
        try:
            _LHM["arbre"] = json.loads(urllib.request.urlopen("http://127.0.0.1:8085/data.json", timeout=1.5).read().decode("utf-8"))
        except Exception:
            _LHM["arbre"] = None
        _LHM["quand"] = time.time()
        return _LHM["arbre"]


def lire_gpu_lhm():
    """La carte graphique NVIDIA vue par LibreHardwareMonitor : (température, charge %, VRAM en Mo, watts) ou None.
    On la lit là en priorité : moins de programmes qui interrogent le pilote NVIDIA en même temps = moins de risques."""
    arbre = arbre_lhm()
    if not arbre:
        return None
    valeurs = {}

    def nombre(texte):
        trouve = re.match(r"\s*(-?[\d]+(?:[.,]\d+)?)\s*(\w*)", str(texte or ""))
        if not trouve:
            return None
        v = float(trouve.group(1).replace(",", "."))
        return v * 1024 if trouve.group(2).upper() == "GB" else v

    def parcourir(noeud, dans_gpu, groupe):
        image = str(noeud.get("ImageURL") or "").rsplit("/", 1)[-1].lower()
        enfants = noeud.get("Children") or []
        if enfants:
            if image in IMAGES_MATERIEL:
                dans_gpu = image == "nvidia.png"
            elif dans_gpu:
                groupe = str(noeud.get("Text") or "").lower()
            for enfant in enfants:
                parcourir(enfant, dans_gpu, groupe)
            return
        if not dans_gpu:
            return
        t, v = str(noeud.get("Text") or "").lower(), nombre(noeud.get("Value"))
        if v is None:
            return
        if groupe.startswith("temp") and t == "gpu core":
            valeurs.setdefault("temp", v)
        elif groupe.startswith("load") and t == "gpu core":
            valeurs.setdefault("charge", v)
        elif t == "gpu memory used":
            valeurs.setdefault("vram", v)
        elif groupe.startswith("power") and t == "gpu package":
            valeurs.setdefault("watts", v)

    parcourir(arbre, False, "")
    if "temp" not in valeurs or "charge" not in valeurs:
        return None
    return round(valeurs["temp"]), round(valeurs["charge"]), round(valeurs.get("vram", 0)), float(valeurs.get("watts", 0))


def lire_gpu():
    try:
        res = lire_gpu_lhm()
        if res:
            return res
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            res = lire_gpu_nvml()
            if res:
                return res
        except Exception:
            pass
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

TYPES_HWINFO = {1: "temp", 3: "fan", 7: "usage"}   # 1 = température, 3 = ventilateur, 7 = utilisation en %


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
        return lire_lhm()   # HWiNFO ne partage rien : on essaie LibreHardwareMonitor
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


# --- Plan B : LibreHardwareMonitor (gratuit, sans la limite de 12 h de HWiNFO gratuit) ---
# Dans LibreHardwareMonitor : Options > Remote Web Server > Run (port 8085).
# Les images que LibreHardwareMonitor donne aux COMPOSANTS (les groupes ont d'autres images)
IMAGES_MATERIEL = {"cpu.png", "nvidia.png", "ati.png", "amd.png", "intel.png", "hdd.png", "ram.png",
                   "mainboard.png", "chip.png", "nic.png", "battery.png", "psu.png", "bigng.png"}


def lire_lhm():
    """Lit http://127.0.0.1:8085/data.json et renvoie les capteurs au même format que HWiNFO (ou None)."""
    arbre = arbre_lhm()
    if arbre is None:
        return None

    def nombre(texte):
        trouve = re.match(r"\s*(-?[\d]+(?:[.,]\d+)?)", str(texte or ""))
        return float(trouve.group(1).replace(",", ".")) if trouve else None

    capteurs = []

    def parcourir(noeud, materiel, groupe):
        image = str(noeud.get("ImageURL") or "")
        texte = str(noeud.get("Text") or "")
        enfants = noeud.get("Children") or []
        if enfants:
            if image.rsplit("/", 1)[-1].lower() in IMAGES_MATERIEL:
                materiel = (image, texte)   # un composant : processeur, disque, carte graphique...
            elif materiel:
                groupe = texte              # un groupe : Temperatures, Load, Levels, Data...
            for enfant in enfants:
                parcourir(enfant, materiel, groupe)
            return
        valeur = nombre(noeud.get("Value"))
        if valeur is None or not materiel:
            return
        image_m, nom_m = materiel
        g, t = (groupe or "").lower(), texte.lower()
        if "cpu" in image_m:
            if g.startswith("temp") and t in ("cpu package", "core (tctl/tdie)"):
                capteurs.append(("CPU", "CPU Package", "temp", valeur, "°C"))
            elif g.startswith("temp") and t == "core average":
                secours_cpu.append(("CPU", "CPU Package", "temp", valeur, "°C"))
            elif g.startswith("load") and t == "cpu total":
                capteurs.append(("CPU", "Total CPU Usage", "usage", valeur, "%"))
        elif "hdd" in image_m:
            disque = "S.M.A.R.T.: " + nom_m
            if g.startswith("temp") and "temperature" in t and not capteurs_disque_temp.get(nom_m):
                capteurs_disque_temp[nom_m] = True
                capteurs.append((disque, "Drive Temperature", "temp", valeur, "°C"))
            elif t == "remaining life":
                capteurs.append((disque, "Drive Remaining Life", "autre", valeur, "%"))
            elif t == "percentage used":
                capteurs.append((disque, "Drive Remaining Life", "autre", max(0.0, 100 - valeur), "%"))
            elif t == "data written":
                capteurs.append((disque, "Total Host Writes", "autre", valeur, "GB"))
        # (v3) ventilateurs, températures en plus, puissance consommée
        if any(m in image_m for m in ("nvidia", "ati.", "intel.")):
            lieu = "Carte graphique"
        elif "mainboard" in image_m or "chip" in image_m:
            lieu = "Carte mère"
        elif "cpu" in image_m:
            lieu = "Processeur"
        elif "ram" in image_m:
            lieu = "Mémoire"
        else:
            return
        if g.startswith("fan") and lieu in ("Carte graphique", "Carte mère"):
            capteurs.append((lieu, texte, "fan", valeur, "RPM"))
        elif g.startswith("control") and lieu in ("Carte graphique", "Carte mère"):
            capteurs.append((lieu, texte, "commande", valeur, "%"))
        elif g.startswith("temp") and not t.startswith(("warning", "critical", "distance")):
            if lieu != "Processeur" or t in ("core max", "core average"):
                capteurs.append((lieu, texte, "temp_plus", valeur, "°C"))
        elif g.startswith("power") and t in ("cpu package", "gpu package"):
            capteurs.append((lieu, "Puissance", "watts", valeur, "W"))

    capteurs_disque_temp, secours_cpu = {}, []
    parcourir(arbre, None, None)
    if not any(c[0] == "CPU" and c[2] == "temp" for c in capteurs):
        capteurs += secours_cpu[:1]
    # un seul « CPU Package » (le premier trouvé)
    vus, uniques = set(), []
    for c in capteurs:
        if c[:2] in vus and c[0] == "CPU":
            continue
        vus.add(c[:2])
        uniques.append(c)
    return uniques or None


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
                "disques": [], "reseau": essayer(compteurs_reseau), "ventilos": [], "temps": [], "watts": {}}
    capteurs = essayer(lire_hwinfo)
    resultat["hwinfo"] = capteurs is not None
    commandes = {(c, n): v for c, n, type_, v, *_ in capteurs or [] if type_ == "commande"}
    for composant, nom, type_, valeur, *_ in capteurs or []:
        if type_ == "fan":   # un ventilateur : tours par minute + la vitesse demandée (en %) si on la connaît
            resultat["ventilos"].append({"ou": composant, "nom": nom, "rpm": valeur, "pct": commandes.get((composant, nom))})
        elif type_ == "temp_plus":
            resultat["temps"].append((composant, nom, valeur))
        elif type_ == "watts":
            resultat["watts"][composant] = valeur
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

def journal(texte):
    """Petit carnet de bord (~/BoiteAOutils/journal.txt) pour comprendre un problème après coup."""
    try:
        DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
        fichier = DOSSIER_APPLI / "journal.txt"
        if fichier.exists() and fichier.stat().st_size > 200_000:
            fichier.write_text("", encoding="utf-8")
        with open(fichier, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + f"[v{VERSION} pid {os.getpid()}] " + texte + "\n")
    except OSError:
        pass

FICHIER_EN_MARCHE = DOSSIER_APPLI / "en_marche.json"
FICHIER_ARRETS = DOSSIER_APPLI / "arrets.json"
_FICHIER_PLANTAGE = None   # doit rester ouvert tant que l'appli tourne


def surveiller_plantages():
    """Si Windows tue le programme d'un coup (plantage « natif »), Python n'a pas le temps d'écrire
    dans le journal. Le module faulthandler, lui, y arrive : il note dans plantage.txt ce que
    faisait chaque fil à ce moment-là. C'est ce fichier qu'on regarde pour comprendre."""
    global _FICHIER_PLANTAGE
    try:
        import faulthandler
        DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
        chemin = DOSSIER_APPLI / "plantage.txt"
        if chemin.exists() and chemin.stat().st_size > 300_000:   # trop gros : on ne garde que la fin
            chemin.write_bytes(chemin.read_bytes()[-100_000:])
        _FICHIER_PLANTAGE = open(chemin, "a", encoding="utf-8")
        _FICHIER_PLANTAGE.write(f"\n===== Démarrage v{VERSION} le {time.strftime('%Y-%m-%d %H:%M:%S')} (pid {os.getpid()}) =====\n")
        _FICHIER_PLANTAGE.flush()
        faulthandler.enable(file=_FICHIER_PLANTAGE, all_threads=True)
    except Exception as e:
        journal(f"Surveillance des plantages impossible : {e}")


def noter_demarrage():
    """Laisse un petit mot « je tourne ». S'il est encore là au démarrage suivant, c'est que la boîte
    s'est arrêtée sans passer par la sortie normale : on le note (journal + arrets.json)."""
    try:
        ancien = json.loads(FICHIER_EN_MARCHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        ancien = None
    if isinstance(ancien, dict):
        trace = False
        try:   # y a-t-il une trace de plantage écrite pendant cette session-là ?
            texte = (DOSSIER_APPLI / "plantage.txt").read_text(encoding="utf-8", errors="replace")
            trace = "exception" in texte.rsplit("===== Démarrage", 1)[-1]
        except OSError:
            pass
        journal(f"⚠ La session précédente (v{ancien.get('version')}, lancée le {ancien.get('debut')}) s'est arrêtée "
                "sans prévenir" + (" : détails dans plantage.txt" if trace else " (plantage, ou PC éteint d'un coup)"))
        try:
            arrets = json.loads(FICHIER_ARRETS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            arrets = []
        arrets.append({"debut": ancien.get("debut"), "vu": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "version": ancien.get("version"), "trace": trace})
        try:
            FICHIER_ARRETS.write_text(json.dumps(arrets[-30:], indent=1), encoding="utf-8")
        except OSError:
            pass
    try:
        DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
        FICHIER_EN_MARCHE.write_text(json.dumps({"version": VERSION, "debut": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                 "pid": os.getpid()}), encoding="utf-8")
    except OSError:
        pass


def noter_arret_propre():
    try:
        FICHIER_EN_MARCHE.unlink()
    except OSError:
        pass


def reparer_raccourci():
    """Si le raccourci « Boîte à outils » du Bureau pointe ailleurs (fichier déplacé), on le refait pointer ici."""
    if sys.platform != "win32":
        return
    ici = str(Path(__file__).resolve())
    lanceur = str(Path(sys.executable).with_name("pythonw.exe"))
    script = (
        "$b=[Environment]::GetFolderPath('Desktop');$l=Join-Path $b 'Boîte à outils.lnk';"
        "if(Test-Path -LiteralPath $l){$s=(New-Object -ComObject WScript.Shell).CreateShortcut($l);"
        f"$f='{ici}';$d=Split-Path $f;"
        "if($s.TargetPath -like '*.pyw'){if($s.TargetPath -ne $f){$s.TargetPath=$f;$s.WorkingDirectory=$d;$s.Save();'repare'}}"
        "elseif($s.Arguments.Trim([char]34) -ne $f){"
        f"if(-not (Test-Path -LiteralPath $s.TargetPath)){{$s.TargetPath='{lanceur}'}};"
        "$s.Arguments=[char]34+$f+[char]34;$s.WorkingDirectory=$d;$s.Save();'repare'}}"
    )
    try:
        res = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand",
                              base64.b64encode(script.encode("utf-16-le")).decode()], capture_output=True, text=True,
                             encoding=ENCODAGE, errors="replace", timeout=20,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if "repare" in (res.stdout or ""):
            journal(f"Raccourci du Bureau réparé -> {ici}")
    except (OSError, subprocess.SubprocessError):
        pass

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
    DOSSIER_APPLI.mkdir(exist_ok=True)
    shutil.copy2(ici, DOSSIER_APPLI / (ici.name + ".ancienne"))   # copie de secours, rangée hors du Bureau
    vieille = ici.with_name(ici.name + ".ancienne")   # celle que les anciennes versions laissaient à côté du fichier
    if vieille.exists():
        try:
            vieille.unlink()
        except OSError:
            pass
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


# =============================================================
#  DÉMARRAGE
# =============================================================


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


# =============================================================
#  🎛 PROFILS  -  Jeu / Travail / Silence en un clic
# =============================================================

PROFILS_DEFAUT = {
    "Jeu":     {"icone": "🎮", "plan": "SCHEME_MIN", "fermer": ["OneDrive.exe"], "ouvrir": ["Discord", "steam://open/main"], "volume": None},
    "Travail": {"icone": "💼", "plan": "SCHEME_BALANCED", "fermer": [], "ouvrir": [], "volume": None},
    "Silence": {"icone": "🌙", "plan": "SCHEME_MAX", "fermer": ["Steam.exe"], "ouvrir": [], "volume": None},
}
NOMS_PLANS = {"SCHEME_MIN": "Performances", "SCHEME_BALANCED": "Utilisation normale", "SCHEME_MAX": "Économie d'énergie"}
REGLAGES_DEFAUT["profils"] = PROFILS_DEFAUT
REGLAGES.setdefault("profils", json.loads(json.dumps(PROFILS_DEFAUT)))
if not REGLAGES.get("profils_sans_volume"):   # v2.0.7 : les profils ne touchent plus au son du casque (demande de Crz)
    for _p in REGLAGES["profils"].values():
        _p["volume"] = None
    REGLAGES["profils_sans_volume"] = True


def regler_volume(pourcentage):
    """Règle le volume en « appuyant » sur les touches volume du clavier (chaque appui = 2 %)."""
    import ctypes
    appuyer = lambda touche: (ctypes.windll.user32.keybd_event(touche, 0, 0, 0),
                              ctypes.windll.user32.keybd_event(touche, 0, 2, 0))
    for _ in range(50):
        appuyer(0xAE)   # volume -
    for _ in range(round(pourcentage / 2)):
        appuyer(0xAF)   # volume +


def appliquer_profil(nom, ouvrir=True):
    """Fait tout le travail d'un profil. Renvoie un petit compte rendu.
    ouvrir=False : on n'ouvre aucune appli (utile quand le profil se met tout seul au lancement d'un jeu)."""
    p = REGLAGES["profils"][nom]
    fait = []
    if p.get("plan") and activer_plan(p["plan"]):
        fait.append(f"plan {NOMS_PLANS.get(p['plan'], p['plan'])}")
    for exe in p.get("fermer", []):
        res = subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if res.returncode == 0:
            fait.append(f"{exe} fermé")
    for appli in (p.get("ouvrir", []) if ouvrir else []):
        try:
            if appli.lower() == "discord":
                subprocess.Popen([str(Path(LOCALAPPDATA) / "Discord" / "Update.exe"), "--processStart", "Discord.exe"])
            else:
                os.startfile(appli)
            fait.append(f"{appli} ouvert")
        except OSError:
            pass
    REGLAGES["profil_actif"] = nom
    enregistrer_reglages()
    return fait


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
    return AUDIO.demander(_son_lister, defaut=[]) or []


# -------------------------------------------------------------
#  LE SON DE WINDOWS : UN SEUL FIL LUI PARLE
# -------------------------------------------------------------
#  Windows range le son derrière une technologie appelée « COM ». Elle
#  est très stricte : si plusieurs « fils » (threads) lui parlent chacun
#  leur tour puis disparaissent, elle peut faire planter le programme
#  d'un coup, sans message. C'est ce qui fermait la boîte à outils.
#  Maintenant : UN fil, créé une fois, qui reste là. Tout le monde lui
#  demande poliment (AUDIO.demander) et attend sa réponse.

class FilAudio:
    def __init__(self):
        self.taches = queue.Queue()
        self.fil = None
        self.verrou = threading.Lock()

    def demander(self, fonction, *args, attente=8, defaut=None):
        """Fait tourner fonction(*args) dans le fil du son et renvoie sa réponse (`defaut` si ça rate ou traîne)."""
        if threading.current_thread() is self.fil:
            return fonction(*args)
        with self.verrou:
            if self.fil is None or not self.fil.is_alive():
                self.fil = threading.Thread(target=self.boucle, name="son", daemon=True)
                self.fil.start()
        if self.taches.qsize() >= 5:   # le fil est occupé : on n'empile pas les demandes
            return defaut
        boite = {"fini": threading.Event(), "res": defaut}
        self.taches.put((fonction, args, boite))
        boite["fini"].wait(attente)
        return boite["res"]

    def boucle(self):
        while True:
            fonction, args, boite = self.taches.get()
            try:
                boite["res"] = fonction(*args)
            except ImportError:
                pass   # pycaw pas installé : le bouton Micro proposera de l'installer
            except Exception as e:
                _son_oublier()   # micro débranché, casque éteint... : on repartira de zéro
                if time.time() - SON["derniere_erreur"] > 600:   # une ligne toutes les 10 min au maximum
                    SON["derniere_erreur"] = time.time()
                    journal(f"Son : {type(e).__name__} {e}")
            finally:
                boite["fini"].set()


AUDIO = FilAudio()
# Ce que le fil du son garde sous la main (lui seul y touche)
SON = {"pret": False, "enum": None, "id": None, "volume": None, "niveau": None, "appareil": None,
       "verifie": 0.0, "ids": {}, "derniere_erreur": 0.0}
MICRO_SILENCE = {"depuis": None, "vu_son": False}   # pour deviner une coupure faite avec le bouton du casque


def _son_oublier():
    for cle in ("id", "volume", "niveau", "appareil"):
        SON[cle] = None
    SON["verifie"] = 0.0


def _son_enumerateur():
    """(fil du son) L'objet Windows qui connaît tous les périphériques audio. Créé une seule fois."""
    import comtypes
    if not SON["pret"]:
        try:
            comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
        except OSError:
            pass   # déjà prêt dans ce fil
        SON["pret"] = True
    if SON["enum"] is None:
        from pycaw.pycaw import AudioUtilities
        SON["enum"] = AudioUtilities.GetDeviceEnumerator()
    return SON["enum"]


def _son_lister():
    """(fil du son) Les micros branchés : [(nom, id), ...]."""
    import comtypes
    from pycaw.pycaw import PROPERTYKEY
    cle_nom = PROPERTYKEY()   # la « case » où Windows range le nom affiché d'un périphérique
    cle_nom.fmtid = comtypes.GUID("{a45c254e-df1c-4efd-8020-67d146a850e0}")
    cle_nom.pid = 14
    collection = _son_enumerateur().EnumAudioEndpoints(1, 1)   # 1 = enregistrement, 1 = actifs seulement
    micros = []
    for i in range(collection.GetCount()):
        try:
            appareil = collection.Item(i)
            ident = appareil.GetId()
            valeur = appareil.OpenPropertyStore(0).GetValue(cle_nom)   # 0 = lecture seule
            nom = valeur.GetValue()
            valeur.clear()
            if ident and isinstance(nom, str) and nom:
                micros.append((nom, ident))
        except Exception:
            pass
    SON["ids"] = dict(micros)
    return sorted(micros)


def _son_brancher():
    """(fil du son) Prépare le réglage de volume et le niveau sonore du micro choisi. On les garde ensuite
    sous la main : on revérifie juste toutes les 15 s que le micro est toujours le même."""
    if SON["volume"] is not None and time.time() - SON["verifie"] < 15:
        return
    import comtypes
    from pycaw.pycaw import IAudioEndpointVolume, IAudioMeterInformation
    enumerateur = _son_enumerateur()
    appareil = None
    choisi = REGLAGES.get("micro_nom")
    if choisi:   # un micro précis choisi dans les Réglages
        if choisi not in SON["ids"]:
            _son_lister()
        if choisi in SON["ids"]:
            try:
                appareil = enumerateur.GetDevice(SON["ids"][choisi])
            except Exception:
                SON["ids"] = {}
    if appareil is None:
        appareil = enumerateur.GetDefaultAudioEndpoint(1, 1)   # 1 = enregistrement, 1 = multimédia
    ident = appareil.GetId()
    SON["verifie"] = time.time()
    if SON["volume"] is not None and ident == SON["id"]:
        return   # toujours le même micro : on garde tout
    # QueryInterface = la façon propre de demander « la partie volume » de l'appareil
    # (avant, un raccourci appelé cast() libérait le même objet deux fois : c'était LE plantage)
    volume = appareil.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)
    try:
        niveau = appareil.Activate(IAudioMeterInformation._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(IAudioMeterInformation)
    except Exception:
        niveau = None
    SON.update(id=ident, volume=volume, niveau=niveau, appareil=appareil)
    MICRO_SILENCE.update(depuis=None, vu_son=False)


def _son_capture_active():
    """(fil du son) Une appli écoute-t-elle le micro en ce moment (Discord en vocal, un jeu...) ?
    Si personne n'écoute, Windows donne un niveau de 0 même micro ouvert. None = impossible à savoir."""
    try:
        import comtypes
        from pycaw.pycaw import IAudioSessionManager2
        gestion = SON["appareil"].Activate(IAudioSessionManager2._iid_, comtypes.CLSCTX_ALL, None).QueryInterface(IAudioSessionManager2)
        sessions = gestion.GetSessionEnumerator()
        for i in range(sessions.GetCount()):
            if sessions.GetSession(i).GetState() == 1:   # 1 = en train de tourner
                return True
        return False
    except Exception:
        return None


def _son_coupe_par_le_casque():
    """(fil du son) Le casque HyperX coupe le micro sans prévenir Windows : on le devine quand le micro
    donne 0 pile pendant 2,5 s alors qu'une appli l'écoute."""
    niveau = SON["niveau"]
    if niveau is None:
        return False
    crete = 0.0
    for _ in range(8):   # ~0,15 s d'écoute
        crete = max(crete, niveau.GetPeakValue())
        time.sleep(0.02)
    if crete > 0:
        MICRO_SILENCE["vu_son"] = True
        MICRO_SILENCE["depuis"] = None
        return False
    MICRO_SILENCE["depuis"] = MICRO_SILENCE["depuis"] or time.time()
    if not MICRO_SILENCE["vu_son"] or time.time() - MICRO_SILENCE["depuis"] < 2.5:
        return False
    return _son_capture_active() is not False


def _son_micro(action):
    """(fil du son) Le vrai travail de micro()."""
    _son_brancher()
    v = SON["volume"]
    if v is None:
        return None
    # Certains casques sans fil (HyperX...) ignorent le « muet » de Windows : on se fie au VOLUME du micro.
    # Couper = volume à 0 (+ muet), réactiver = on remet le volume d'avant (et on enlève le muet).
    volume = v.GetMasterVolumeLevelScalar()
    coupe = volume < 0.01
    casque = False
    if not coupe:
        casque = coupe = _son_coupe_par_le_casque()
    if action in ("basculer", "couper", "activer"):
        coupe = {"basculer": not coupe, "couper": True, "activer": False}[action]
        if coupe:
            REGLAGES["volume_micro_avant"] = round(volume, 3) if volume >= 0.01 else REGLAGES.get("volume_micro_avant", 1.0)
            enregistrer_reglages()
            v.SetMasterVolumeLevelScalar(0.0, None)
            v.SetMute(1, None)
        else:
            if casque:   # coupé avec le bouton du casque : muet puis plus muet, pour que le pilote HyperX le réactive aussi
                v.SetMute(1, None)
                time.sleep(0.3)
            v.SetMute(0, None)
            v.SetMasterVolumeLevelScalar(float(REGLAGES.get("volume_micro_avant", 1.0)) if volume < 0.01 else volume, None)
        MICRO_SILENCE.update(depuis=None, vu_son=False)
    return coupe


def micro(action="etat"):
    """action = "etat", "basculer", "couper" ou "activer". Renvoie True si le micro est coupé (None si inconnu)."""
    return AUDIO.demander(_son_micro, action)


JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


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


# =============================================================
#  LES BRIQUES D'AFFICHAGE
#  Des petits éléments réutilisés partout (boutons, onglets,
#  interrupteurs...). Les écrire une seule fois ici garantit que
#  toutes les pages se ressemblent.
# =============================================================

SURFACE = "#15152a"    # fond des boutons discrets et des lignes cliquables
SURVOL = "#1d1d36"     # le même, quand la souris passe dessus
CHAMP = "#0a0a12"      # fond des zones où on écrit
ETEINT = "#55557a"     # texte désactivé
COULEURS_ACCENT = {"Cyan": CYAN, "Rose": ROSE, "Violet": VIOLET, "Vert": VERT}
COULEUR_NIVEAU = {"alerte": ROUGE, "attention": ORANGE, "info": CYAN, "ok": VERT, "inconnu": GRIS}


def police(taille=10, gras=False):
    return ("Segoe UI", taille, "bold" if gras else "normal")


def pluriel(phrase, nombre):
    """« 1 appli(s) » -> « 1 appli », « 3 appli(s) » -> « 3 applis »."""
    return phrase.replace("(s)", "s" if nombre > 1 else "")


def sans_accents(texte):
    """« Réglages » -> « reglages » : pour que la recherche trouve même sans les accents."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


class Bouton(tk.Label):
    """Un bouton plat. style = "principal" (couleur d'accent), "succes", "danger" ou "discret"."""

    def __init__(self, parent, texte, commande=None, style="discret", petit=False):
        self.commande, self.style, self.actif = commande, style, True
        fond, encre = self.couleurs()
        super().__init__(parent, text=texte, bg=fond, fg=encre, font=police(9 if petit else 10, True),
                         padx=10 if petit else 14, pady=3 if petit else 6, cursor="hand2",
                         highlightthickness=1, highlightbackground=BORD if style == "discret" else fond)
        self.bind("<Button-1>", self.clic)
        self.bind("<Enter>", lambda e: self.actif and self.config(bg=self.couleurs(survol=True)[0]))
        self.bind("<Leave>", lambda e: self.actif and self.config(bg=self.couleurs()[0]))

    def couleurs(self, survol=False):
        base = {"principal": ACCENT, "succes": VERT, "danger": ROUGE}.get(self.style)
        if base is None:
            return (SURVOL if survol else SURFACE), TEXTE
        return (melanger(base, "#ffffff", 0.25) if survol else base), texte_sur(base)

    def clic(self, _evt=None):
        if self.actif and self.commande:
            self.commande()

    def activer(self, oui=True):
        """Bouton utilisable (True) ou grisé (False)."""
        self.actif = bool(oui)
        fond, encre = self.couleurs() if oui else ("#12121c", ETEINT)
        self.config(bg=fond, fg=encre, cursor="hand2" if oui else "arrow",
                    highlightbackground=BORD if self.style == "discret" or not oui else fond)

    def changer(self, texte=None, style=None):
        if style:
            self.style = style
        if texte is not None:
            self.config(text=texte)
        self.activer(self.actif)


class Interrupteur(tk.Canvas):
    """Un interrupteur oui / non (comme sur un téléphone)."""

    def __init__(self, parent, valeur=False, commande=None, fond=CARTE):
        super().__init__(parent, width=42, height=22, bg=fond, highlightthickness=0, cursor="hand2")
        self.valeur, self.commande = bool(valeur), commande
        self.bind("<Button-1>", self.basculer)
        self.dessiner()

    def dessiner(self):
        self.delete("all")
        self.create_line(11, 11, 31, 11, width=18, capstyle="round", fill=ACCENT if self.valeur else "#2a2a44")
        x = 31 if self.valeur else 11
        self.create_oval(x - 7, 4, x + 7, 18, fill="white" if self.valeur else "#9a9ab8", outline="")

    def basculer(self, _evt=None):
        self.valeur = not self.valeur
        self.dessiner()
        if self.commande:
            self.commande(self.valeur)

    def get(self):
        return self.valeur

    def set(self, valeur):
        self.valeur = bool(valeur)
        self.dessiner()


class Jauge(tk.Canvas):
    """Une barre de progression fine aux bouts arrondis."""

    def __init__(self, parent, couleur=CYAN, fond=CARTE, epaisseur=7):
        super().__init__(parent, height=epaisseur + 7, width=1, bg=fond, highlightthickness=0)
        self.couleur, self.fond, self.epaisseur, self.fraction = couleur, fond, epaisseur, 0
        self.bind("<Configure>", lambda e: self.regler(self.fraction, self.couleur))

    def regler(self, fraction, couleur=None):
        self.fraction, self.couleur = max(0, min(1, fraction or 0)), couleur or self.couleur
        self.delete("all")
        larg, milieu, e = max(self.winfo_width(), 40), (self.epaisseur + 7) // 2, self.epaisseur
        self.create_line(e, milieu, larg - e, milieu, fill="#1c1c2c", width=e, capstyle="round")
        if self.fraction > 0:
            fin = e + (larg - 2 * e) * self.fraction
            self.create_line(e, milieu, fin, milieu, fill=melanger(self.fond, self.couleur, 0.25), width=e + 6, capstyle="round")
            self.create_line(e, milieu, fin, milieu, fill=self.couleur, width=e, capstyle="round")


class Onglets(tk.Frame):
    """Des onglets en haut d'une page. Chaque onglet a son propre cadre ; on ne montre que celui choisi."""

    def __init__(self, parent, fond=FOND):
        super().__init__(parent, bg=fond)
        self.fond = fond
        self.barre = tk.Frame(self, bg=fond)
        self.barre.pack(fill="x")
        self.zone = tk.Frame(self, bg=fond)
        self.zone.pack(fill="both", expand=True, pady=(10, 0))
        self.pages, self.actif, self.quand_change = {}, None, None

    def ajouter(self, nom, carte=True):
        """Crée l'onglet et renvoie le cadre à remplir."""
        bouton = tk.Label(self.barre, text=nom, bg=self.fond, fg=GRIS, font=police(10, True), padx=14, pady=6, cursor="hand2")
        bouton.pack(side="left", padx=(0, 6))
        bouton.bind("<Button-1>", lambda e: self.choisir(nom))
        bouton.bind("<Enter>", lambda e: nom != self.actif and bouton.config(fg=TEXTE))
        bouton.bind("<Leave>", lambda e: nom != self.actif and bouton.config(fg=GRIS))
        cadre = Carte(self.zone, padx=20, pady=16) if carte else tk.Frame(self.zone, bg=self.fond)
        self.pages[nom] = (bouton, cadre)
        if self.actif is None:
            self.choisir(nom)
        return cadre

    def choisir(self, nom):
        if nom not in self.pages:
            return
        self.actif = nom
        for n, (bouton, cadre) in self.pages.items():
            if n == nom:
                bouton.config(bg=melanger(self.fond, ACCENT, 0.16), fg=ACCENT)
                cadre.pack(fill="both", expand=True)
            else:
                bouton.config(bg=self.fond, fg=GRIS)
                cadre.pack_forget()
        if self.quand_change:
            self.quand_change(nom)

    def pastille(self, nom, texte):
        """Ajoute un petit compteur à côté du nom de l'onglet (« Mises à jour  3 »)."""
        if nom in self.pages:
            self.pages[nom][0].config(text=f"{nom}   {texte}" if texte else nom)


class Defilant(tk.Frame):
    """Un cadre qu'on peut faire défiler à la molette quand le contenu est trop haut.
    On met le contenu dans `.dedans`."""

    def __init__(self, parent, fond=CARTE):
        super().__init__(parent, bg=fond)
        self.toile = tk.Canvas(self, bg=fond, highlightthickness=0, bd=0)
        self.barre = ttk.Scrollbar(self, orient="vertical", command=self.toile.yview)
        self.dedans = tk.Frame(self.toile, bg=fond)
        self.fenetre = self.toile.create_window(0, 0, window=self.dedans, anchor="nw")
        self.toile.configure(yscrollcommand=self.regler_barre)
        self.toile.pack(side="left", fill="both", expand=True)
        self.dedans.bind("<Configure>", lambda e: self.toile.configure(scrollregion=self.toile.bbox("all")))
        self.toile.bind("<Configure>", lambda e: self.toile.itemconfigure(self.fenetre, width=e.width))
        self.bind("<Enter>", lambda e: self.toile.bind_all("<MouseWheel>", self.molette))
        self.bind("<Leave>", lambda e: self.toile.unbind_all("<MouseWheel>"))

    def regler_barre(self, debut, fin):
        self.barre.set(debut, fin)
        if float(debut) <= 0 and float(fin) >= 1:   # tout tient à l'écran : pas besoin de barre
            self.barre.pack_forget()
        else:
            self.barre.pack(side="right", fill="y")

    def molette(self, evt):
        if self.toile.yview() != (0.0, 1.0):
            self.toile.yview_scroll(-1 if evt.delta > 0 else 1, "units")


class Bulle:
    """Une petite explication qui apparaît quand la souris reste sur un élément."""

    def __init__(self, widget, texte):
        self.widget, self.texte, self.fenetre, self.attente = widget, texte, None, None
        widget.bind("<Enter>", self.prevoir, add="+")
        widget.bind("<Leave>", self.cacher, add="+")
        widget.bind("<Button-1>", self.cacher, add="+")

    def prevoir(self, _evt=None):
        self.attente = self.widget.after(500, self.montrer)

    def montrer(self):
        if self.fenetre or not self.texte:
            return
        self.fenetre = f = tk.Toplevel(self.widget)
        f.overrideredirect(True)
        f.attributes("-topmost", True)
        tk.Label(f, text=self.texte, bg="#1a1a2e", fg=TEXTE, font=police(9), padx=8, pady=4, justify="left",
                 wraplength=320, highlightthickness=1, highlightbackground=BORD).pack()
        f.geometry(f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 6}")

    def cacher(self, _evt=None):
        if self.attente:
            self.widget.after_cancel(self.attente)
            self.attente = None
        if self.fenetre:
            self.fenetre.destroy()
            self.fenetre = None


def champ(parent, largeur=24, cache=False, valeur=""):
    """Une zone où on écrit, au style de l'appli."""
    c = tk.Entry(parent, show="•" if cache else "", bg=CHAMP, fg=TEXTE, insertbackground=TEXTE, relief="flat",
                 font=police(10), width=largeur, highlightthickness=1, highlightbackground=BORD, highlightcolor=ACCENT)
    if valeur != "":
        c.insert(0, str(valeur))
    return c


def petit_titre(parent, texte, fond=CARTE, couleur=GRIS):
    """PETIT TITRE GRIS en majuscules écartées, au-dessus d'un bloc."""
    return tk.Label(parent, text=espacer(texte), bg=fond, fg=couleur, font=police(8), anchor="w")


def libelle(parent, texte="", taille=10, couleur=TEXTE, gras=False, fond=CARTE, largeur=None, **options):
    """Une ligne de texte. largeur = nombre de pixels avant de passer à la ligne."""
    return tk.Label(parent, text=texte, bg=fond, fg=couleur, font=police(taille, gras), anchor="w", justify="left",
                    wraplength=largeur or 0, **options)


def vider(cadre):
    for w in cadre.winfo_children():
        w.destroy()


def ligne_etat(parent, niveau, titre, detail="", bouton=None, action=None, fond=CARTE):
    """Une ligne « point de couleur + titre + explication (+ bouton) ». Sert aux bilans et aux listes À faire."""
    ligne = tk.Frame(parent, bg=fond)
    ligne.pack(fill="x", pady=5)
    tk.Label(ligne, text="●", bg=fond, fg=COULEUR_NIVEAU.get(niveau, GRIS), font=police(13)).pack(side="left", anchor="n", padx=(0, 10))
    if bouton and action:
        Bouton(ligne, bouton, action, petit=True).pack(side="right", anchor="n", padx=(10, 0))
    textes = tk.Frame(ligne, bg=fond)
    textes.pack(side="left", fill="x", expand=True)
    libelle(textes, titre, 10, TEXTE, True, fond).pack(fill="x")
    if detail:
        d = libelle(textes, detail, 9, GRIS, fond=fond)
        d.pack(fill="x")
        d.bind("<Configure>", lambda e: d.config(wraplength=max(120, e.width - 4)))
    return ligne


class Navigation:
    """Le menu à gauche. Chaque page est un cadre ; on n'affiche que celle qui est choisie."""

    def __init__(self, menu, zone, titre, sous_titre):
        self.menu, self.zone, self.titre, self.sous_titre = menu, zone, titre, sous_titre
        self.pages = []        # liste de (cadre, nom, ligne, barre, label)
        self.aides = {}        # nom de la page -> phrase d'explication affichée sous le titre
        self.compteurs = {}    # nom -> petit compteur à droite dans le menu
        self.actuelle, self.quand_change = None, None

    def groupe(self, titre):
        tk.Label(self.menu, text=espacer(titre), bg=MENU, fg=ETEINT, font=police(7, True), anchor="w").pack(
            fill="x", padx=22, pady=(12, 2))

    def add(self, cadre, icone, nom, aide, en_bas=False):
        ligne = tk.Frame(self.menu, bg=MENU, cursor="hand2")
        ligne.pack(fill="x", side="bottom" if en_bas else "top")
        barre = tk.Frame(ligne, bg=MENU, width=3)
        barre.pack(side="left", fill="y")
        tk.Label(ligne, text=icone, bg=MENU, fg=GRIS, font=police(10), width=3).pack(side="left", padx=(8, 0))
        lbl = tk.Label(ligne, text=nom, bg=MENU, fg=GRIS, font=police(10), anchor="w", pady=6)
        lbl.pack(side="left", fill="x", expand=True)
        compteur = tk.Label(ligne, text="", bg=MENU, fg=FOND, font=police(8, True))
        index = len(self.pages)
        for w in (ligne, lbl) + tuple(ligne.winfo_children()):
            w.bind("<Button-1>", lambda e, i=index: self.select(i))
        self.pages.append((cadre, nom, ligne, barre, lbl))
        self.aides[nom] = aide
        self.compteurs[nom] = compteur

    def compter(self, nom, nombre, couleur=ORANGE):
        """Affiche (ou retire) un compteur à côté d'une page du menu."""
        c = self.compteurs.get(nom)
        if c is None:
            return
        if nombre:
            c.config(text=f" {nombre} ", bg=couleur)
            c.pack(side="right", padx=10)
        else:
            c.pack_forget()

    def select(self, index):
        for i, (cadre, nom, ligne, barre, lbl) in enumerate(self.pages):
            actif = i == index
            fond = melanger(MENU, ACCENT, 0.10) if actif else MENU
            for w in ligne.winfo_children():
                if w is not barre and w is not self.compteurs[nom]:
                    w.config(bg=fond, fg="white" if actif else GRIS)
            ligne.config(bg=fond)
            barre.config(bg=ACCENT if actif else MENU)
            if actif:
                cadre.pack(fill="both", expand=True)
                self.titre.config(text=nom)
                self.sous_titre.config(text=self.aides.get(nom, ""))
                self.actuelle = nom
            else:
                cadre.pack_forget()
        if self.quand_change:
            self.quand_change(self.actuelle)


# =============================================================
#  LA FENÊTRE
#  Une "classe" regroupe des données et des fonctions qui vont
#  ensemble. Ici : tout ce qui concerne notre fenêtre.
#  Ce chapitre pose le décor (menu, en-tête, notifications, recherche,
#  mini-fenêtre). Les pages sont dans les chapitres suivants.
# =============================================================

NOUVEAUTES = [
    ("3.0.0", "La grande refonte", [
        "Fini les fermetures toutes seules : la lecture du micro a été réécrite",
        "Accueil : une liste « À faire » te dit quoi regarder, avec un bouton pour y aller",
        "Graphique des températures sur 10 minutes, 1 heure ou 24 heures",
        "Santé du PC : un bilan en un coup d'œil, puis Refroidissement, Disques, Mises à jour, Diagnostic",
        "Nouveau : suivi des ventilateurs et de la pompe (avec alerte si l'un d'eux s'arrête)",
        "Nouveau : résumé de chaque partie (durée, températures max) dans Jeux > Sessions",
        "Nouveau : le profil Jeu peut se mettre tout seul quand un jeu démarre",
        "Nouveau : notifications Windows (surchauffe, disque plein, fin de partie)",
        "Nouveau : mini-fenêtre toujours visible avec les températures",
        "Nouveau : recherche rapide avec Ctrl+K (pages, profils, sons, actions)",
        "Nouveau : page Diagnostic pour voir si tout est bien branché (capteurs, micro, Stream Deck)",
        "Menu rangé par thème, et chaque page a une phrase d'explication sous son titre",
    ]),
]

FICHIER_HISTORIQUE = DOSSIER_APPLI / "historique.json"
FICHIER_SESSIONS = DOSSIER_APPLI / "sessions.json"
PERIODES = {"10 min": (600, 2), "1 h": (3600, 12), "24 h": (86400, 288)}   # nom -> (durée, secondes par point)
ORDRE_NIVEAUX = {"alerte": 0, "attention": 1, "info": 2}


class BoiteAOutils:

    def __init__(self, racine, cache=False):
        self.racine = racine
        self.icone = None                 # l'icône près de l'horloge
        self.file_icone = queue.Queue()   # messages venant des autres « fils » (icône, téléphone, Stream Deck)
        self.session = None               # infos de la session gaming en cours
        self.taches = {}                  # la liste « À faire » : clé -> {niveau, texte, detail, bouton, action}
        self.notifs = deque(maxlen=40)    # les dernières notifications
        self.non_lues = 0
        self.dernieres_alertes = {}       # pour ne pas répéter la même notification toutes les 2 secondes
        self.flottants = []               # panneaux posés par-dessus la page (recherche, notifications)
        self.sous_pages = {}              # nom de page -> ses onglets
        self.mini = None
        self.maj_dispo = None
        self.cache_au_depart = cache
        racine.title("Boîte à outils de Crz")
        if (DOSSIER_APPLI / "icone.ico").exists():   # logo de l'appli (fenêtre + barre des tâches)
            try:
                racine.iconbitmap(default=str(DOSSIER_APPLI / "icone.ico"))
            except tk.TclError:
                pass
        racine.geometry("1180x760")
        racine.minsize(1080, 700)
        racine.configure(bg=FOND)
        self.style()

        # ----- Menu à gauche -----
        menu = tk.Frame(racine, bg=MENU, width=214)
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False)   # garde la largeur fixe
        logo = tk.Canvas(menu, bg=MENU, height=70, highlightthickness=0)
        logo.pack(fill="x", padx=(18, 0), pady=(16, 0))
        gros = police(19, True)
        logo.create_text(2, 4, text="⚡", fill=CYAN, anchor="nw", font=gros)
        logo.create_text(34, 4, text="CRZ", fill=CYAN, anchor="nw", font=gros)
        x, mesure, mot = 2, tk.font.Font(font=gros), "TOOLBOX"
        for i, lettre in enumerate(mot):   # chaque lettre un peu plus violette : effet dégradé
            logo.create_text(x, 38, text=lettre, fill=melanger(CYAN, VIOLET, i / (len(mot) - 1)), anchor="nw", font=gros)
            x += mesure.measure(lettre) + 1
        tk.Frame(racine, bg=BORD, width=1).pack(side="left", fill="y")   # trait de séparation

        # ----- Zone principale : en-tête + page -----
        principale = tk.Frame(racine, bg=FOND, padx=24, pady=16)
        principale.pack(side="left", fill="both", expand=True)
        self.principale = principale
        entete = tk.Frame(principale, bg=FOND)
        entete.pack(fill="x", pady=(0, 12))
        haut = tk.Frame(entete, bg=FOND)   # 1re ligne : le titre à gauche, les boutons à droite
        haut.pack(fill="x")
        droite = tk.Frame(haut, bg=FOND)
        droite.pack(side="right", pady=(4, 0))
        titre = tk.Label(haut, text="", bg=FOND, fg=TEXTE, font=police(20, True), anchor="w")
        titre.pack(side="left", fill="x", expand=True)
        sous_titre = tk.Label(entete, text="", bg=FOND, fg=GRIS, font=police(10), anchor="w")   # 2e ligne : l'explication
        sous_titre.pack(fill="x")
        self.horloge = tk.Label(droite, text="", bg=FOND, fg=GRIS, font=police(10))
        self.horloge.pack(side="right", padx=(12, 0))
        self.pastille = tk.Label(droite, text="…", bg=FOND, fg=GRIS, font=police(10, True), padx=12, pady=4, cursor="hand2")
        self.pastille.pack(side="right", padx=(8, 0))
        self.pastille.bind("<Button-1>", lambda e: self.aller_a("Santé du PC", "Bilan"))
        Bulle(self.pastille, "L'état général de ton PC. Clique pour voir le bilan complet.")
        self.cloche = tk.Label(droite, text="🔔", bg=SURFACE, fg=GRIS, font=police(10, True), padx=10, pady=4, cursor="hand2")
        self.cloche.pack(side="right", padx=(8, 0))
        self.cloche.bind("<Button-1>", lambda e: self.basculer_notifs())
        Bulle(self.cloche, "Les dernières notifications")
        recherche = tk.Label(droite, text="🔎  Rechercher   Ctrl+K", bg=SURFACE, fg=GRIS, font=police(9), padx=12, pady=5, cursor="hand2")
        recherche.pack(side="right", padx=(8, 0))
        recherche.bind("<Button-1>", lambda e: self.basculer_palette())
        self.bouton_maj_appli = Bouton(droite, "", self.lancer_maj_appli, "principal", petit=True)
        self.maj_horloge()
        zone = tk.Frame(principale, bg=FOND)
        zone.pack(fill="both", expand=True)
        self.message_toast = tk.Label(racine, text="", bg=SURVOL, fg=TEXTE, font=police(10, True), padx=16, pady=8)

        # ----- Les pages -----
        nav = self.navigation = Navigation(menu, zone, titre, sous_titre)
        self.demarrer_serveur()   # pour le téléphone et le Stream Deck
        self.preparer_stats()     # les statistiques servent à plusieurs pages

        def page(icone, nom, aide, constructeur, carte=True, en_bas=False):
            cadre = Carte(zone, padx=20, pady=16) if carte else tk.Frame(zone, bg=FOND)
            nav.add(cadre, icone, nom, aide, en_bas)
            constructeur(cadre)

        page("⚙", "Réglages", "Tout se règle ici, sans toucher au code.", self.page_reglages, carte=False, en_bas=True)
        nav.groupe("Surveiller")
        page("◉", "Accueil", "Ton PC en un coup d'œil, et ce qu'il y a à faire.", self.page_accueil, carte=False)
        page("🩺", "Santé du PC", "Températures, ventilateurs, disques et mises à jour.", self.page_sante, carte=False)
        page("📊", "Rapport", "Le résumé de ta semaine : temps de jeu, températures, ménage.", self.page_rapport)
        nav.groupe("Jouer")
        page("🎮", "Jeux", "Lance une partie et retrouve ton temps de jeu.", self.page_jeux, carte=False)
        page("🎛", "Profils", "Un clic pour passer le PC en mode Jeu, Travail ou Silence.", self.page_profils, carte=False)
        page("🔊", "Soundboard", "Des sons à envoyer dans Discord, comme si c'était ton micro.", self.page_soundboard)
        nav.groupe("Entretenir")
        page("🧹", "Entretien", "Faire de la place, ranger tes fichiers, voir ce qui se lance au démarrage.", self.page_entretien, carte=False)
        nav.groupe("Outils")
        self.coffre = None
        page("🔐", "Coffre-fort", "Tes mots de passe, chiffrés. Toi seul peux les ouvrir.", self.page_coffre)
        page("🔔", "Alerte prix", "Colle le lien d'un produit : je te préviens quand le prix baisse.", self.page_prix)
        page("📱", "Téléphone", "Pilote ton PC depuis ton téléphone ou ton Stream Deck.", self.page_telephone, carte=False)
        tk.Label(menu, text=f"v{VERSION}", bg=MENU, fg="#44445e", font=police(8)).pack(side="bottom", pady=(0, 6), before=nav.pages[0][2])
        nav.quand_change = self.page_changee
        self.aller_a("Accueil")

        # ----- Clavier, fermeture, démarrage -----
        racine.bind_all("<Control-k>", lambda e: self.basculer_palette())
        racine.bind_all("<Control-K>", lambda e: self.basculer_palette())
        racine.bind_all("<Escape>", lambda e: self.fermer_flottants(), add="+")
        racine.bind_all("<Button-1>", self.clic_ailleurs, add="+")
        racine.protocol("WM_DELETE_WINDOW", self.fermer)   # clic sur la croix
        racine.protocol("WM_SAVE_YOURSELF", self.arret_windows)   # Windows s'éteint ou ferme la session
        self.lire_file_icone()
        self.racine.after(8000, lambda: self.verifier_maj_appli(au_demarrage=True))
        self.racine.after(1500, lambda: self.creer_icone(demander=False))   # l'icône sert aussi aux notifications
        self.racine.after(20000, self.verifier_stabilite)
        if REGLAGES.get("mini_fenetre"):
            self.racine.after(1200, self.ouvrir_mini)
        if cache:   # lancé au démarrage de Windows : direct près de l'horloge
            if self.creer_icone(demander=False):
                racine.withdraw()
            else:
                racine.iconify()
        self.racine.after(1800, self.annoncer_nouveautes)

    # ---------- petits outils ----------

    def style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Treeview", background=CHAMP, fieldbackground=CHAMP, foreground=TEXTE, rowheight=28,
                    font=police(10), borderwidth=0, relief="flat")
        s.configure("Treeview.Heading", background=SURFACE, foreground=GRIS, font=police(9, True), relief="flat", borderwidth=0)
        s.map("Treeview", background=[("selected", melanger(CHAMP, ACCENT, 0.30))], foreground=[("selected", "white")])
        s.map("Treeview.Heading", background=[("active", SURVOL)])
        s.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])   # sans le cadre clair autour
        s.configure("TCombobox", fieldbackground=CHAMP, background=SURFACE, foreground=TEXTE, arrowcolor=ACCENT,
                    bordercolor=BORD, lightcolor=BORD, darkcolor=BORD, padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", CHAMP)], foreground=[("readonly", TEXTE)],
              selectbackground=[("readonly", CHAMP)], selectforeground=[("readonly", TEXTE)])
        s.configure("Vertical.TScrollbar", background=BORD, troughcolor=CARTE, bordercolor=CARTE, arrowcolor=GRIS,
                    lightcolor=BORD, darkcolor=BORD, relief="flat")
        s.map("Vertical.TScrollbar", background=[("active", ETEINT)])
        for cle, valeur in (("background", CARTE), ("foreground", TEXTE), ("selectBackground", ACCENT), ("selectForeground", FOND)):
            self.racine.option_add(f"*TCombobox*Listbox.{cle}", valeur)

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

    def aller_a(self, nom, onglet=None):
        """Ouvre une page du menu par son nom (et, si on veut, un de ses onglets)."""
        noms = [p[1] for p in self.navigation.pages]
        if nom in noms:
            self.navigation.select(noms.index(nom))
            if onglet and nom in self.sous_pages:
                self.sous_pages[nom].choisir(onglet)
        self.fermer_flottants()

    def page_changee(self, nom):
        self.fermer_flottants()

    def toast(self, texte, niveau="ok"):
        """Un petit message qui apparaît en bas de la fenêtre et s'efface tout seul."""
        couleur = COULEUR_NIVEAU.get(niveau, VERT)
        self.message_toast.config(text=texte, fg=couleur, bg=melanger(CARTE, couleur, 0.14),
                                  highlightthickness=1, highlightbackground=melanger(CARTE, couleur, 0.5))
        self.message_toast.place(relx=0.5, rely=1.0, y=-22, anchor="s")
        self.message_toast.lift()
        if getattr(self, "fin_toast", None):
            self.racine.after_cancel(self.fin_toast)
        self.fin_toast = self.racine.after(3500, self.message_toast.place_forget)

    def maj_horloge(self):
        t = time.localtime()
        self.horloge.config(text=f"{JOURS[t.tm_wday]} {t.tm_mday} {MOIS[t.tm_mon - 1]} · {t.tm_hour:02d}:{t.tm_min:02d}")
        self.racine.after(5000, self.maj_horloge)

    def ouvrir_dossier_appli(self):
        try:
            os.startfile(DOSSIER_APPLI)
        except (AttributeError, OSError):
            self.toast(f"Dossier : {DOSSIER_APPLI}", "info")

    # ---------- la liste « À faire » ----------
    #  N'importe quelle page peut signaler un point à regarder avec self.tache(...),
    #  et le retirer avec self.tache_finie(...). L'accueil, le bilan et la pastille
    #  en haut se mettent à jour tout seuls.

    def tache(self, cle, niveau, texte, detail="", bouton="Voir", action=None, prevenir=True):
        nouvelle = cle not in self.taches or self.taches[cle]["niveau"] != niveau
        self.taches[cle] = {"niveau": niveau, "texte": texte, "detail": detail, "bouton": bouton, "action": action}
        if nouvelle:
            if prevenir and niveau in ("alerte", "attention"):
                self.notifier(texte, detail, niveau, action, cle=cle)
            self.afficher_taches()
        return nouvelle

    def tache_finie(self, cle):
        if self.taches.pop(cle, None) is not None:
            self.afficher_taches()

    def taches_triees(self):
        return sorted(self.taches.values(), key=lambda t: ORDRE_NIVEAUX.get(t["niveau"], 9))

    def afficher_taches(self):
        taches = self.taches_triees()
        importantes = [t for t in taches if t["niveau"] in ("alerte", "attention")]
        if not importantes:
            texte, couleur = "✓  Tout va bien", VERT
        else:
            couleur = ROUGE if importantes[0]["niveau"] == "alerte" else ORANGE
            texte = "⚠  " + importantes[0]["texte"] + (f"  (+{len(importantes) - 1})" if len(importantes) > 1 else "")
        self.pastille.config(text=texte[:46], fg=couleur, bg=melanger(FOND, couleur, 0.12))
        # Le même nombre partout : menu, carte « À faire » de l'accueil et bilan
        self.navigation.compter("Santé du PC", len(taches), couleur if importantes else CYAN)
        for redessiner in ("dessiner_a_faire", "dessiner_bilan"):
            if hasattr(self, "cadre_" + redessiner.split("_", 1)[1]):
                getattr(self, redessiner)()

    # ---------- notifications ----------

    def notifier(self, titre, texte="", niveau="info", action=None, cle=None, silence=1800):
        """Ajoute une notification (cloche en haut) et prévient avec une bulle Windows si la fenêtre n'est pas devant."""
        cle = cle or titre
        if time.time() - self.dernieres_alertes.get(cle, 0) < silence:
            return
        self.dernieres_alertes[cle] = time.time()
        self.notifs.appendleft({"heure": time.strftime("%H:%M"), "titre": titre, "texte": texte, "niveau": niveau, "action": action})
        self.non_lues += 1
        self.dessiner_cloche()
        try:
            devant = self.racine.state() == "normal" and self.racine.focus_displayof() is not None
        except tk.TclError:
            devant = False
        if devant:
            self.toast(titre, niveau if niveau != "info" else "info")
        elif REGLAGES.get("notifications", True) and self.icone:
            try:
                self.icone.notify(texte or titre, titre if texte else "Boîte à outils")
            except Exception:
                pass

    def dessiner_cloche(self):
        if self.non_lues:
            self.cloche.config(text=f"🔔 {self.non_lues}", fg=FOND, bg=ORANGE)
        else:
            self.cloche.config(text="🔔", fg=GRIS, bg=SURFACE)

    def basculer_notifs(self):
        if any(nom == "notifs" for nom, _ in self.flottants):
            self.fermer_flottants()
            return
        self.fermer_flottants()
        panneau = tk.Frame(self.racine, bg=CARTE, highlightthickness=1, highlightbackground=BORD, padx=14, pady=12)
        panneau.place(relx=1.0, x=-24, y=62, anchor="ne", width=390)
        panneau.lift()
        self.flottants.append(("notifs", panneau))
        tete = tk.Frame(panneau, bg=CARTE)
        tete.pack(fill="x", pady=(0, 6))
        petit_titre(tete, "Notifications").pack(side="left")
        if self.notifs:
            vider_tout = tk.Label(tete, text="Tout effacer", bg=CARTE, fg=ACCENT, font=police(9), cursor="hand2")
            vider_tout.pack(side="right")
            vider_tout.bind("<Button-1>", lambda e: (self.notifs.clear(), self.fermer_flottants()))
        if not self.notifs:
            libelle(panneau, "Rien pour l'instant. Les alertes (surchauffe, disque plein, fin de partie...) arriveront ici.",
                    9, GRIS, largeur=350).pack(fill="x", pady=8)
        for n in list(self.notifs)[:7]:
            ligne = tk.Frame(panneau, bg=CARTE, cursor="hand2" if n["action"] else "arrow")
            ligne.pack(fill="x", pady=4)
            tk.Label(ligne, text="●", bg=CARTE, fg=COULEUR_NIVEAU.get(n["niveau"], CYAN), font=police(10)).pack(side="left", anchor="n", padx=(0, 8))
            tk.Label(ligne, text=n["heure"], bg=CARTE, fg=ETEINT, font=police(8)).pack(side="right", anchor="n")
            textes = tk.Frame(ligne, bg=CARTE)
            textes.pack(side="left", fill="x", expand=True)
            libelle(textes, n["titre"], 10, TEXTE, True, largeur=280).pack(fill="x")
            if n["texte"]:
                libelle(textes, n["texte"], 9, GRIS, largeur=280).pack(fill="x")
            if n["action"]:
                for w in [ligne, textes] + textes.winfo_children():
                    w.bind("<Button-1>", lambda e, a=n["action"]: (self.fermer_flottants(), a()))
        self.non_lues = 0
        self.dessiner_cloche()

    # ---------- recherche rapide (Ctrl+K) ----------

    def commandes(self):
        """Tout ce qu'on peut lancer depuis la recherche : [(texte affiché, fonction), ...]."""
        liste = []
        for _, nom, *_ in self.navigation.pages[1:] + self.navigation.pages[:1]:   # dans l'ordre du menu
            liste.append((f"Ouvrir : {nom}", lambda n=nom: self.aller_a(n)))
            for onglet in getattr(self.sous_pages.get(nom), "pages", {}):
                liste.append((f"Ouvrir : {nom} › {onglet}", lambda n=nom, o=onglet: self.aller_a(n, o)))
        liste += [
            ("Action : couper ou réactiver le micro", self.basculer_micro),
            ("Action : mode jeu (profil Jeu)", self.mode_jeu),
            ("Action : montrer ou cacher la mini-fenêtre", self.basculer_mini),
            ("Action : vérifier les mises à jour (pilotes et applis)", lambda: (self.aller_a("Santé du PC", "Mises à jour"), self.verifier_maj(), self.verifier_pilotes())),
            ("Action : analyser ce qui peut être nettoyé", lambda: (self.aller_a("Entretien", "Nettoyer"), self.analyser())),
            ("Action : chercher une mise à jour de la boîte à outils", lambda: self.verifier_maj_appli(a_la_main=True)),
            ("Action : ouvrir le dossier des journaux", self.ouvrir_dossier_appli),
            ("Action : voir les nouveautés de cette version", self.quoi_de_neuf),
            ("Action : musique, lecture / pause", lambda: touche_media("playpause")),
            ("Action : musique, morceau suivant", lambda: touche_media("suivant")),
            ("Action : arrêter tous les sons du soundboard", stopper_sons),
        ]
        for nom, p in REGLAGES.get("profils", {}).items():
            liste.append((f"Profil : {p.get('icone', '')} {nom}", lambda n=nom: self.activer_profil(n)))
        for son in REGLAGES.get("sons", []):
            liste.append((f"Son : {son['nom']}", lambda s=son["id"]: threading.Thread(target=jouer_son, args=(s,), daemon=True).start()))
        return liste

    def basculer_palette(self):
        if any(nom == "palette" for nom, _ in self.flottants):
            self.fermer_flottants()
            return
        self.fermer_flottants()
        if self.racine.state() != "normal":
            return
        panneau = tk.Frame(self.racine, bg=CARTE, highlightthickness=1, highlightbackground=ACCENT, padx=12, pady=12)
        panneau.place(relx=0.5, y=64, anchor="n", width=540)
        panneau.lift()
        self.flottants.append(("palette", panneau))
        saisie = champ(panneau, 40)
        saisie.config(font=police(12))
        saisie.pack(fill="x", ipady=6)
        liste = tk.Listbox(panneau, height=10, bg=CARTE, fg=TEXTE, selectbackground=melanger(CARTE, ACCENT, 0.3),
                           selectforeground="white", relief="flat", highlightthickness=0, font=police(11),
                           activestyle="none", exportselection=False)
        liste.pack(fill="x", pady=(8, 0))
        libelle(panneau, "↑ ↓ pour choisir   ·   Entrée pour valider   ·   Échap pour fermer", 8, ETEINT).pack(fill="x", pady=(6, 0))
        toutes, visibles = self.commandes(), []

        def filtrer(_evt=None):
            mots = sans_accents(saisie.get()).split()
            visibles[:] = [c for c in toutes if all(m in sans_accents(c[0]) for m in mots)]
            liste.delete(0, "end")
            for texte, _ in visibles:
                liste.insert("end", "  " + texte)
            if visibles:
                liste.selection_set(0)

        def bouger(pas):
            if visibles:
                i = (liste.curselection() or (0,))[0]
                i = max(0, min(len(visibles) - 1, i + pas))
                liste.selection_clear(0, "end")
                liste.selection_set(i)
                liste.see(i)
            return "break"

        def valider(_evt=None):
            choix = liste.curselection()
            if choix and choix[0] < len(visibles):
                action = visibles[choix[0]][1]
                self.fermer_flottants()
                action()
            return "break"
        saisie.bind("<KeyRelease>", lambda e: e.keysym not in ("Up", "Down", "Return", "Escape") and filtrer())
        saisie.bind("<Down>", lambda e: bouger(1))
        saisie.bind("<Up>", lambda e: bouger(-1))
        saisie.bind("<Return>", valider)
        liste.bind("<ButtonRelease-1>", valider)
        filtrer()
        saisie.focus_set()

    def fermer_flottants(self):
        for _, panneau in self.flottants:
            panneau.destroy()
        self.flottants = []

    def clic_ailleurs(self, evt):
        """Un clic en dehors d'un panneau flottant le referme."""
        if not self.flottants:
            return
        w = evt.widget
        if w in (self.cloche,) or (isinstance(w, tk.Label) and "Rechercher" in str(w.cget("text"))):
            return
        for _, panneau in self.flottants:
            if str(w).startswith(str(panneau)):
                return
        self.fermer_flottants()

    # ---------- mini-fenêtre toujours visible ----------

    def basculer_mini(self):
        if self.mini:
            self.fermer_mini()
        else:
            self.ouvrir_mini()

    def ouvrir_mini(self):
        if self.mini:
            return
        f = self.mini = tk.Toplevel(self.racine)
        f.overrideredirect(True)          # pas de barre de titre
        f.attributes("-topmost", True)    # toujours au-dessus des autres fenêtres
        try:
            f.attributes("-alpha", 0.94)
        except tk.TclError:
            pass
        f.configure(bg=BORD)
        dedans = tk.Frame(f, bg=FOND, padx=12, pady=7)
        dedans.pack(padx=1, pady=1)
        self.mini_valeurs = {}
        for cle, nom, couleur in (("cpu", "CPU", CYAN), ("gpu", "GPU", ROSE), ("ram", "RAM", VIOLET)):
            bloc = tk.Frame(dedans, bg=FOND)
            bloc.pack(side="left", padx=7)
            tk.Label(bloc, text=nom, bg=FOND, fg=GRIS, font=police(7, True)).pack()
            self.mini_valeurs[cle] = tk.Label(bloc, text="--", bg=FOND, fg=couleur, font=police(14, True), width=4)
            self.mini_valeurs[cle].pack()
        position = REGLAGES.get("mini_pos")
        f.update_idletasks()
        if not (isinstance(position, list) and len(position) == 2):
            position = [f.winfo_screenwidth() - f.winfo_reqwidth() - 30, 30]
        x = max(0, min(int(position[0]), f.winfo_screenwidth() - 60))
        y = max(0, min(int(position[1]), f.winfo_screenheight() - 40))
        f.geometry(f"+{x}+{y}")
        prise = {}

        def attraper(evt):
            prise["x"], prise["y"] = evt.x_root - f.winfo_x(), evt.y_root - f.winfo_y()

        def glisser(evt):
            if prise:
                f.geometry(f"+{evt.x_root - prise['x']}+{evt.y_root - prise['y']}")

        def lacher(_evt):
            REGLAGES["mini_pos"] = [f.winfo_x(), f.winfo_y()]
            enregistrer_reglages()

        def menu(evt):
            m = tk.Menu(f, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=ACCENT, activeforeground=FOND)
            m.add_command(label="Ouvrir la boîte à outils", command=self.montrer)
            m.add_command(label="Couper / réactiver le micro", command=self.basculer_micro)
            m.add_separator()
            m.add_command(label="Fermer la mini-fenêtre", command=self.fermer_mini)
            m.tk_popup(evt.x_root, evt.y_root)
        for w in [f, dedans] + [e for b in dedans.winfo_children() for e in [b] + b.winfo_children()]:
            w.bind("<Button-1>", attraper)
            w.bind("<B1-Motion>", glisser)
            w.bind("<ButtonRelease-1>", lacher)
            w.bind("<Double-Button-1>", lambda e: self.montrer())
            w.bind("<Button-3>", menu)
        if not REGLAGES.get("mini_fenetre"):
            REGLAGES["mini_fenetre"] = True
            enregistrer_reglages()
        self.maj_mini()
        self.maj_actions_rapides()

    def fermer_mini(self):
        if self.mini:
            self.mini.destroy()
            self.mini = None
        if REGLAGES.get("mini_fenetre"):
            REGLAGES["mini_fenetre"] = False
            enregistrer_reglages()
        self.maj_actions_rapides()

    def maj_mini(self):
        if not self.mini:
            return
        m = getattr(self, "dernieres_mesures", None) or {}
        cpu, gpu, ram = m.get("cpu_temp"), m.get("gpu"), m.get("ram")
        self.mini_valeurs["cpu"].config(text=f"{cpu:.0f}°" if cpu is not None else "--",
                                        fg=ROUGE if cpu is not None and cpu >= ALERTE_CPU else CYAN)
        self.mini_valeurs["gpu"].config(text=f"{gpu[0]:.0f}°" if gpu else "--",
                                        fg=ROUGE if gpu and gpu[0] >= ALERTE_GPU else ROSE)
        self.mini_valeurs["ram"].config(text=f"{ram[0] / ram[1] * 100:.0f}%" if ram else "--")

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

        try:   # le logo de l'appli s'il existe
            image = Image.open(DOSSIER_APPLI / "logo.png").convert("RGBA").resize((64, 64))
        except Exception:   # sinon on dessine une petite caisse à outils
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            d = ImageDraw.Draw(image)
            d.rounded_rectangle([4, 20, 60, 58], radius=8, fill=CYAN)
            d.rounded_rectangle([22, 8, 42, 24], radius=5, outline=CYAN, width=5)
            d.rectangle([4, 34, 60, 38], fill=FOND)

        envoyer = self.file_icone.put   # l'icône tourne dans un autre fil : elle passe par la file
        menu = pystray.Menu(
            pystray.MenuItem("Ouvrir", lambda: envoyer("ouvrir"), default=True),
            pystray.MenuItem("Couper / réactiver le micro", lambda: envoyer("micro_basculer")),
            pystray.MenuItem("Mini-fenêtre", lambda: envoyer("mini")),
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
        """Toutes les 200 ms, on regarde si un autre fil nous a demandé quelque chose."""
        try:
            while True:
                ordre = self.file_icone.get_nowait()
                if ordre == "ouvrir":
                    self.montrer()
                elif ordre == "quitter":
                    self.quitter()
                    return
                elif ordre == "micro_basculer":
                    self.basculer_micro()
                elif ordre == "mini":
                    self.basculer_mini()
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
        if getattr(self, "nouveautes_en_attente", False):
            self.nouveautes_en_attente = False
            self.racine.after(400, self.quoi_de_neuf)

    def fermer(self):
        if not REGLAGES["fermer_vers_icone"]:
            self.quitter()
        elif self.creer_icone():
            if self.coffre and self.coffre.mdp_maitre:   # sécurité : on verrouille le coffre en cachant la fenêtre
                self.coffre.verrouiller()
            self.racine.withdraw()
        else:
            self.racine.iconify()   # pas d'icône possible : on réduit dans la barre des tâches

    def tout_enregistrer(self):
        if getattr(self, "stats_a_sauver", False):
            ecrire_json(FICHIER_STATS, self.stats)
            self.stats_a_sauver = False
        if hasattr(self, "histo"):
            self.sauver_historique()

    def arret_windows(self):
        """Windows s'éteint : on enregistre ce qui doit l'être, et on note que ce n'est pas un plantage."""
        journal("Windows ferme la session")
        self.tout_enregistrer()
        noter_arret_propre()

    def quitter(self):
        self.tout_enregistrer()
        if self.session:
            self.fin_session()   # remet le plan d'alim et les applis
        if self.icone:
            self.icone.stop()
        if getattr(self, "serveur", None):
            self.serveur.shutdown()
        self.racine.destroy()

    # ---------- mises à jour de la boîte à outils ----------

    def verifier_maj_appli(self, au_demarrage=False, a_la_main=False):
        """Regarde s'il y a une nouvelle version (au démarrage puis toutes les 6 h)."""
        def ensuite(infos):
            if isinstance(infos, dict):
                self.maj_dispo = infos
                self.bouton_maj_appli.changer(f"⬇  Mise à jour v{infos['version']}")
                self.bouton_maj_appli.activer(True)
                self.bouton_maj_appli.pack(side="right", padx=(8, 0))
                if au_demarrage and REGLAGES.get("maj_auto", True) and not self.session:
                    self.lancer_maj_appli(sans_question=True)
                else:
                    self.tache("maj_appli", "info", f"Version {infos['version']} de la boîte à outils disponible",
                               infos.get("notes", ""), "Installer", self.lancer_maj_appli)
            elif a_la_main:
                self.toast(f"Tu as déjà la dernière version (v{VERSION})")
            self.derniere_verif_maj = time.strftime("%H:%M")
            if not a_la_main:
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
        self.bouton_maj_appli.changer("⏳  Installation...")
        self.bouton_maj_appli.activer(False)

        def ensuite(erreur):
            if isinstance(erreur, Exception):
                erreur = str(erreur)
            if erreur:
                self.bouton_maj_appli.changer(f"⬇  Mise à jour v{infos['version']}")
                self.bouton_maj_appli.activer(True)
                messagebox.showerror("Mise à jour", f"Mise à jour impossible : {erreur}\nTa version actuelle continue de marcher.")
                return
            # On relance la nouvelle version, puis on ferme celle-ci
            arguments = [sys.executable, str(Path(__file__).resolve()), "--apres-maj"]
            if self.racine.state() == "withdrawn":
                arguments.append("--cache")
            journal(f"Mise à jour installée (v{infos['version']}), redémarrage : {arguments}")
            drapeaux = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            try:   # « breakaway » : la nouvelle version survit même si l'ancienne était dans un groupe de processus
                subprocess.Popen(arguments, creationflags=drapeaux | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0),
                                 close_fds=True)
            except OSError:
                subprocess.Popen(arguments, creationflags=drapeaux, close_fds=True)
            self.quitter()
        self.en_fond(lambda: installer_maj(infos), ensuite)

    # ---------- « Quoi de neuf » ----------

    def annoncer_nouveautes(self):
        """Au premier lancement d'une nouvelle version, on montre ce qui a changé."""
        if REGLAGES.get("version_vue") in (VERSION, NOUVEAUTES[0][0]):   # pas de fenêtre pour une petite correction
            return
        REGLAGES["version_vue"] = NOUVEAUTES[0][0]
        enregistrer_reglages()
        if self.racine.state() == "normal":
            self.quoi_de_neuf()
        else:   # lancée cachée : on le montrera quand tu ouvriras la fenêtre
            self.nouveautes_en_attente = True
            self.notifier(f"Boîte à outils mise à jour (v{VERSION})", "Ouvre-la pour voir les nouveautés.", "info", self.montrer)

    def quoi_de_neuf(self):
        f = tk.Toplevel(self.racine, bg=CARTE, padx=26, pady=20)
        f.title("Quoi de neuf")
        f.transient(self.racine)
        f.resizable(False, False)
        f.geometry(f"+{self.racine.winfo_rootx() + 240}+{self.racine.winfo_rooty() + 40}")   # la hauteur s'adapte au texte
        version, nom, points = NOUVEAUTES[0]
        libelle(f, f"Quoi de neuf dans la v{version}", 16, TEXTE, True).pack(fill="x")
        libelle(f, nom, 11, ACCENT, True).pack(fill="x", pady=(0, 10))
        for point in points:
            ligne = tk.Frame(f, bg=CARTE)
            ligne.pack(fill="x", pady=3)
            tk.Label(ligne, text="•", bg=CARTE, fg=ACCENT, font=police(11, True)).pack(side="left", anchor="n", padx=(0, 8))
            libelle(ligne, point, 10, largeur=520).pack(side="left", fill="x")
        libelle(f, "Astuce : chaque page a une phrase d'explication sous son titre, et Ctrl+K ouvre la recherche.",
                9, GRIS, largeur=540).pack(fill="x", pady=(12, 0))
        Bouton(f, "C'est parti", f.destroy, "principal").pack(anchor="e", pady=(14, 0))

    def verifier_stabilite(self):
        """Regarde si la boîte s'est arrêtée brutalement ces derniers jours (voir noter_demarrage)."""
        arrets = charger_json(FICHIER_ARRETS, [])
        limite = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 3 * 86400))
        recents = [a for a in arrets if isinstance(a, dict) and str(a.get("vu", "")) >= limite and a.get("version") == VERSION]
        if len(recents) >= 2:
            self.tache("stabilite", "attention", f"La boîte à outils s'est arrêtée {len(recents)} fois sans prévenir",
                       "Ces 3 derniers jours, avec cette version. Regarde le diagnostic.", "Diagnostic",
                       lambda: self.aller_a("Santé du PC", "Diagnostic"), prevenir=False)


def methode(fonction):
    """Range une fonction dans la classe BoiteAOutils.
    Ça permet d'écrire la fenêtre en plusieurs chapitres (un par page) plutôt qu'en un seul bloc énorme."""
    setattr(BoiteAOutils, fonction.__name__, fonction)
    return fonction


# =============================================================
#  ◉ ACCUEIL  -  tout le PC sur un écran
# =============================================================

NOMS_VENTILOS = {"cpu fan": "Ventilateur du processeur", "pump fan": "Pompe du watercooling",
                 "gpu fan": "Ventilateur de la carte graphique"}


def nom_ventilo(nom):
    """« CPU Fan » -> « Ventilateur du processeur », « System Fan #2 » -> « Ventilateur du boîtier 2 »..."""
    n = nom.lower().strip()
    numero = re.search(r"(\d+)\s*$", n)
    suffixe = f" {numero.group(1)}" if numero else ""
    if n.startswith("system fan") or n.startswith("chassis fan") or n.startswith("case fan"):
        return "Ventilateur du boîtier" + suffixe
    for debut, propre in NOMS_VENTILOS.items():
        if n.startswith(debut):
            return propre + suffixe
    return nom


@methode
def page_accueil(self, cadre):
    # ----- Ligne 1 : quatre tuiles de mesures -----
    ligne1 = tk.Frame(cadre, bg=FOND)
    ligne1.pack(fill="x")
    self.tuiles = {}
    for col, (cle, titre, couleur, aide) in enumerate((
            ("cpu", "Processeur", CYAN, "Température du processeur. En jeu, 70 à 85 °C est normal pour ton i5."),
            ("gpu", "Carte graphique", ROSE, "Température de la carte graphique. En jeu, 60 à 75 °C est normal."),
            ("ram", "Mémoire", TEXTE, "La mémoire vive utilisée par tout ce qui est ouvert."),
            ("net", "Connexion", TEXTE, "Ce que ton PC télécharge et envoie en ce moment."))):
        ligne1.columnconfigure(col, weight=1, uniform="tuile")
        carte, self.tuiles[cle] = self.tuile(ligne1, titre, couleur)
        carte.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5))
        Bulle(carte, aide)

    # ----- Ligne 2 : graphique + (À faire, actions rapides) -----
    ligne2 = tk.Frame(cadre, bg=FOND)
    ligne2.pack(fill="both", expand=True, pady=10)
    ligne2.columnconfigure(0, weight=1)
    ligne2.rowconfigure(0, weight=1)
    graph = Carte(ligne2, padx=14, pady=10)
    graph.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    tete = tk.Frame(graph, bg=CARTE)
    tete.pack(fill="x")
    petit_titre(tete, "Températures").pack(side="left")
    self.periode = "10 min"
    self.boutons_periode = {}
    for nom in PERIODES:
        b = tk.Label(tete, text=nom, bg=CARTE, fg=GRIS, font=police(8, True), padx=8, pady=2, cursor="hand2")
        b.pack(side="left", padx=(8 if nom == "10 min" else 2, 0))
        b.bind("<Button-1>", lambda e, n=nom: self.choisir_periode(n))
        self.boutons_periode[nom] = b
    self.legende_alerte = tk.Label(tete, text="", bg=CARTE, fg=ORANGE, font=police(8, True))
    self.legende_alerte.pack(side="right")
    tk.Label(tete, text="● GPU   ", bg=CARTE, fg=ROSE, font=police(8, True)).pack(side="right")
    tk.Label(tete, text="● CPU   ", bg=CARTE, fg=CYAN, font=police(8, True)).pack(side="right")
    self.graphique = tk.Canvas(graph, bg=CARTE, height=150, width=1, highlightthickness=0)
    self.graphique.pack(fill="both", expand=True, pady=(6, 0))
    self.graphique.bind("<Configure>", lambda e: self.dessiner_graphique())
    self.charger_historique()
    self.choisir_periode("10 min")

    droite = tk.Frame(ligne2, bg=FOND, width=326)
    droite.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    droite.pack_propagate(False)
    a_faire = Carte(droite, padx=14, pady=10)
    a_faire.pack(fill="both", expand=True)
    tete = tk.Frame(a_faire, bg=CARTE)
    tete.pack(fill="x")
    petit_titre(tete, "À faire").pack(side="left")
    self.compteur_a_faire = tk.Label(tete, text="", bg=CARTE, fg=VERT, font=police(8, True))
    self.compteur_a_faire.pack(side="right")
    self.cadre_a_faire = tk.Frame(a_faire, bg=CARTE)
    self.cadre_a_faire.pack(fill="both", expand=True, pady=(4, 0))

    actions = Carte(droite, padx=12, pady=10)
    actions.pack(fill="x", pady=(10, 0))
    petit_titre(actions, "Actions rapides").pack(fill="x", pady=(0, 4))
    grille = tk.Frame(actions, bg=CARTE)
    grille.pack(fill="x")
    self.infos_actions = {}
    for i, (cle, icone, titre, couleur, commande, aide) in enumerate((
            ("jeu", "🎮", "Mode jeu", CYAN, self.mode_jeu, "Active le profil Jeu : plan Performances, ferme les applis choisies."),
            ("micro", "🎙", "Micro", ROSE, self.basculer_micro, "Coupe ou réactive ton micro (celui choisi dans les Réglages)."),
            ("profil", "🎛", "Profil", VIOLET, self.menu_profils, "Change de profil en un clic."),
            ("mini", "▣", "Mini-fenêtre", VERT, self.basculer_mini, "Une petite fenêtre toujours visible avec les températures."))):
        grille.columnconfigure(i % 2, weight=1, uniform="a")
        self.infos_actions[cle] = self.action_rapide(grille, icone, titre, couleur, commande, i // 2, i % 2)
        Bulle(self.infos_actions[cle].master, aide)

    # ----- Ligne 3 : disques, jeu, musique -----
    ligne3 = tk.Frame(cadre, bg=FOND)
    ligne3.pack(fill="x")
    for col, poids in enumerate((6, 5, 6)):
        ligne3.columnconfigure(col, weight=poids, uniform="bas")
    disques = Carte(ligne3, padx=14, pady=10)
    disques.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    tete = tk.Frame(disques, bg=CARTE)
    tete.pack(fill="x")
    petit_titre(tete, "Disques").pack(side="left")
    self.dash_disques = tk.Label(tete, text="", bg=CARTE, fg=VERT, font=police(8, True))
    self.dash_disques.pack(side="right")
    self.cadre_dash_disques = tk.Frame(disques, bg=CARTE)
    self.cadre_dash_disques.pack(fill="x", pady=(4, 0))
    self.lignes_disques = {}

    jeu = Carte(ligne3, padx=14, pady=10)
    jeu.grid(row=0, column=1, sticky="nsew", padx=5)
    petit_titre(jeu, "Jeu").pack(fill="x")
    self.dash_jeu = tk.Label(jeu, text="Aucun jeu", bg=CARTE, fg=GRIS, font=police(14, True), anchor="w")
    self.dash_jeu.pack(fill="x", pady=(4, 2))
    self.dash_semaine = tk.Label(jeu, text="", bg=CARTE, fg=GRIS, font=police(9), anchor="w")
    self.dash_semaine.pack(fill="x")
    self.dash_top = tk.Label(jeu, text="", bg=CARTE, fg=GRIS, font=police(9), anchor="w")
    self.dash_top.pack(fill="x")

    musique = Carte(ligne3, padx=14, pady=10)
    musique.grid(row=0, column=2, sticky="nsew", padx=(5, 0))
    petit_titre(musique, "Musique · Spotify").pack(fill="x")
    self.dash_musique = tk.Label(musique, text="Rien en lecture", bg=CARTE, fg=GRIS, font=police(11, True), anchor="w")
    self.dash_musique.pack(fill="x", pady=(4, 0))
    self.dash_artiste = tk.Label(musique, text="", bg=CARTE, fg=GRIS, font=police(9), anchor="w")
    self.dash_artiste.pack(fill="x")
    boutons = tk.Frame(musique, bg=CARTE)
    boutons.pack(fill="x", pady=(6, 0))
    for col, (symbole, action, aide) in enumerate((("⏮", "precedent", "Morceau précédent"), ("⏯", "playpause", "Lecture / pause"),
                                                   ("⏭", "suivant", "Morceau suivant"), ("🔉", "volmoins", "Baisser le volume"),
                                                   ("🔊", "volplus", "Monter le volume"))):
        boutons.columnconfigure(col, weight=1, uniform="m")
        b = tk.Label(boutons, text=symbole, bg=SURFACE, fg=CYAN, font=police(10), cursor="hand2", pady=3)
        b.grid(row=0, column=col, sticky="ew", padx=2)
        b.bind("<Button-1>", lambda e, a=action: touche_media(a))
        b.bind("<Enter>", lambda e, w=b: w.config(bg=SURVOL))
        b.bind("<Leave>", lambda e, w=b: w.config(bg=SURFACE))
        Bulle(b, aide)

    self.titre_musique = None
    self.micro_coupe = None
    self.temps_disques = []
    self.max = {"cpu": 0, "gpu": 0}
    self.compte = {}                 # combien de relevés de suite un souci dure (pour ne pas alerter pour 2 secondes)
    self.ventilos_vus = {}           # vitesse max vue pour chaque ventilateur
    self.dernier_reseau = None
    self.max_down = 0
    self.depart = time.time()
    self.dessiner_a_faire()
    self.racine.after(500, self.maj_mesures)
    self.racine.after(800, self.maj_disques_dash)
    self.racine.after(1500, self.suivre_musique)
    self.racine.after(5 * 60 * 1000, self.sauver_historique_regulierement)


@methode
def tuile(self, parent, titre, couleur):
    """Une tuile de mesure : titre + état, grosse valeur + unité, détail, jauge."""
    c = Carte(parent, padx=14, pady=10)
    petit_titre(c, titre).pack(fill="x")
    ligne = tk.Frame(c, bg=CARTE)
    ligne.pack(fill="x", pady=(2, 0))
    valeur = tk.Label(ligne, text="--", bg=CARTE, fg=couleur, font=police(26, True))
    valeur.pack(side="left")
    unite = tk.Label(ligne, text="", bg=CARTE, fg=GRIS, font=police(11, True))
    unite.pack(side="left", anchor="s", pady=(0, 8), padx=(2, 0))
    etat = tk.Label(ligne, text="", bg=CARTE, fg=VERT, font=police(8, True))   # NORMAL, CHAUD, BRÛLANT...
    etat.pack(side="right", anchor="s", pady=(0, 10))
    detail = tk.Label(c, text="", bg=CARTE, fg=GRIS, font=police(9), anchor="w")
    detail.pack(fill="x")
    jauge = Jauge(c, couleur)
    jauge.pack(fill="x", pady=(6, 0))
    return c, {"etat": etat, "valeur": valeur, "unite": unite, "detail": detail, "jauge": jauge, "couleur": couleur}


@methode
def remplir_tuile(self, t, valeur, unite, detail, fraction, etat, couleur_etat, couleur_valeur=None, couleur_jauge=None):
    t["valeur"].config(text=valeur, fg=couleur_valeur or t["couleur"])
    t["unite"].config(text=unite)
    t["detail"].config(text=detail)
    t["etat"].config(text=espacer(etat), fg=couleur_etat)
    t["jauge"].regler(fraction, couleur_jauge or couleur_valeur or t["couleur"])


@methode
def action_rapide(self, parent, icone, titre, couleur, commande, rangee, colonne):
    """Un bouton carré : icône colorée + titre, et une petite ligne d'état dessous. Renvoie le label de l'état."""
    b = tk.Frame(parent, bg=SURFACE, highlightthickness=1, highlightbackground=BORD, cursor="hand2", padx=9, pady=6)
    b.grid(row=rangee, column=colonne, sticky="nsew", padx=3, pady=3)
    haut = tk.Frame(b, bg=SURFACE)
    haut.pack(fill="x")
    ic = tk.Label(haut, text=icone, bg=melanger(SURFACE, couleur, 0.25), fg=TEXTE, font=police(10), width=2)
    ic.pack(side="left")
    nom = tk.Label(haut, text=titre, bg=SURFACE, fg=TEXTE, font=police(10, True))
    nom.pack(side="left", padx=(8, 0))
    info = tk.Label(b, text="", bg=SURFACE, fg=GRIS, font=police(8), anchor="w")
    info.pack(fill="x", pady=(3, 0))

    def teinte(fond):
        for w in (b, haut, nom, info):
            w.config(bg=fond)
    for w in (b, haut, ic, nom, info):
        w.bind("<Button-1>", lambda e: commande())
        w.bind("<Enter>", lambda e: teinte(SURVOL))
        w.bind("<Leave>", lambda e: teinte(SURFACE))
    return info


@methode
def maj_actions_rapides(self):
    """Met à jour la petite ligne d'état de chaque action rapide."""
    infos = getattr(self, "infos_actions", None)
    if not infos:
        return
    actif = REGLAGES.get("profil_actif")
    infos["jeu"].config(text="activé ✓" if actif == "Jeu" else "activer le profil Jeu", fg=VERT if actif == "Jeu" else GRIS)
    infos["profil"].config(text=f"{actif or 'aucun'}  ▾")
    infos["mini"].config(text="affichée · cacher" if self.mini else "cachée · afficher", fg=VERT if self.mini else GRIS)
    coupe = getattr(self, "micro_coupe", None)
    if coupe is None:
        infos["micro"].config(text="état inconnu", fg=GRIS)
    elif coupe:
        infos["micro"].config(text="COUPÉ · réactiver", fg=ROUGE)
    else:
        infos["micro"].config(text="actif · couper", fg=VERT)


@methode
def mode_jeu(self):
    if "Jeu" in REGLAGES.get("profils", {}):
        self.activer_profil("Jeu")
    else:
        self.aller_a("Profils")


@methode
def menu_profils(self, evt=None):
    menu = tk.Menu(self.racine, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=ACCENT, activeforeground=FOND)
    for nom, p in REGLAGES.get("profils", {}).items():
        coche = "✓ " if nom == REGLAGES.get("profil_actif") else "    "
        menu.add_command(label=f"{coche}{p.get('icone', '')} {nom}", command=lambda n=nom: self.activer_profil(n))
    menu.add_separator()
    menu.add_command(label="Modifier les profils…", command=lambda: self.aller_a("Profils"))
    x, y = self.racine.winfo_pointerxy()
    menu.tk_popup(x, y)


@methode
def dessiner_a_faire(self):
    """La carte « À faire » de l'accueil : les 3 points les plus importants, chacun avec son bouton."""
    vider(self.cadre_a_faire)
    taches = self.taches_triees()
    importantes = [t for t in taches if t["niveau"] in ("alerte", "attention")]
    if not taches:
        self.compteur_a_faire.config(text=espacer("rien"), fg=VERT)
        libelle(self.cadre_a_faire, "✓  Rien à faire", 13, VERT, True).pack(fill="x", pady=(14, 2))
        libelle(self.cadre_a_faire, "Ton PC est en forme. Si quelque chose demande ton attention "
                                    "(mise à jour, disque plein, surchauffe...), ça s'affichera ici.", 9, GRIS,
                largeur=280).pack(fill="x")
        return
    couleur = ROUGE if any(t["niveau"] == "alerte" for t in taches) else (ORANGE if importantes else CYAN)
    self.compteur_a_faire.config(text=espacer(f"{len(taches)} point" + ("s" if len(taches) > 1 else "")), fg=couleur)
    for t in taches[:3]:
        ligne = tk.Frame(self.cadre_a_faire, bg=CARTE)
        ligne.pack(fill="x", pady=4)
        tk.Label(ligne, text="●", bg=CARTE, fg=COULEUR_NIVEAU.get(t["niveau"], CYAN), font=police(11)).pack(side="left", anchor="n", padx=(0, 8))
        if t["action"]:
            Bouton(ligne, t["bouton"], t["action"], petit=True).pack(side="right", anchor="n", padx=(6, 0))
        libelle(ligne, t["texte"], 9, TEXTE, True, largeur=190).pack(side="left", fill="x", expand=True, anchor="n")
    if len(taches) > 3:
        plus = tk.Label(self.cadre_a_faire, text=pluriel(f"+ {len(taches) - 3} autre(s) dans le bilan  ›", len(taches) - 3), bg=CARTE, fg=ACCENT,
                        font=police(9), cursor="hand2", anchor="w")
        plus.pack(fill="x", pady=(2, 0))
        plus.bind("<Button-1>", lambda e: self.aller_a("Santé du PC", "Bilan"))


# ---------- les mesures, toutes les 2 secondes ----------

@methode
def dure(self, cle, vrai, combien):
    """Renvoie True quand `vrai` est vrai depuis `combien` relevés de suite (évite les fausses alertes)."""
    self.compte[cle] = self.compte.get(cle, 0) + 1 if vrai else 0
    return self.compte[cle] >= combien


@staticmethod
def _etat_temperature(temp, alerte):
    """Un mot simple + sa couleur pour une température."""
    if temp >= alerte:
        return "Brûlant", ROUGE
    if temp >= alerte - 10:
        return "Chaud", ORANGE
    return "Normal", VERT


BoiteAOutils.etat_temperature = _etat_temperature


@methode
def maj_mesures(self):
    def ensuite(m):
        if isinstance(m, Exception) or not m:
            m = {"gpu": None, "ram": None, "cpu_temp": None, "cpu_usage": None, "disques": [], "hwinfo": False,
                 "reseau": None, "ventilos": [], "temps": [], "watts": {}}
        t = self.tuiles
        refroidir = lambda: self.aller_a("Santé du PC", "Refroidissement")
        # --- Processeur ---
        if m["cpu_temp"] is not None:
            temp = m["cpu_temp"]
            self.max["cpu"] = max(self.max["cpu"], temp)
            etat, couleur = self.etat_temperature(temp, ALERTE_CPU)
            charge = f"Charge {m['cpu_usage']:.0f} % · " if m["cpu_usage"] is not None else ""
            self.remplir_tuile(t["cpu"], f"{temp:.0f}", "°C", f"{charge}max {self.max['cpu']:.0f} °C",
                               temp / 100, etat, couleur, ROUGE if couleur == ROUGE else None)
            if self.dure("cpu_chaud", temp >= ALERTE_CPU, 5):
                if self.tache("cpu_chaud", "alerte", f"Processeur brûlant ({temp:.0f} °C)",
                              f"Il dépasse ton alerte de {ALERTE_CPU} °C. Vérifie le ventilateur et la pompe.", "Voir", refroidir):
                    self.racine.bell()
            elif self.dure("cpu_frais", temp < ALERTE_CPU - 3, 5):
                self.tache_finie("cpu_chaud")
        else:
            charge = f"Charge {m['cpu_usage']:.0f} % · " if m.get("cpu_usage") is not None else ""
            self.remplir_tuile(t["cpu"], "--", "°C", charge + "capteur absent", 0, "?", GRIS, GRIS)
        # --- Carte graphique ---
        if m["gpu"]:
            temp, util, vram, watts = m["gpu"]
            self.max["gpu"] = max(self.max["gpu"], temp)
            etat, couleur = self.etat_temperature(temp, ALERTE_GPU)
            self.remplir_tuile(t["gpu"], f"{temp:.0f}", "°C", f"Charge {util} % · {watts:.0f} W",
                               temp / 100, etat, couleur, ROUGE if couleur == ROUGE else None)
            self.vram = vram
            if self.dure("gpu_chaud", temp >= ALERTE_GPU, 5):
                if self.tache("gpu_chaud", "alerte", f"Carte graphique brûlante ({temp:.0f} °C)",
                              f"Elle dépasse ton alerte de {ALERTE_GPU} °C.", "Voir", refroidir):
                    self.racine.bell()
            elif self.dure("gpu_frais", temp < ALERTE_GPU - 3, 5):
                self.tache_finie("gpu_chaud")
        else:
            self.remplir_tuile(t["gpu"], "--", "°C", "carte NVIDIA introuvable", 0, "?", GRIS, GRIS)
        # --- Mémoire ---
        if m["ram"]:
            utilise, total = m["ram"]
            pct = utilise / total * 100
            couleur = ROUGE if pct >= 90 else (ORANGE if pct >= 80 else VERT)
            vram = getattr(self, "vram", None)
            self.remplir_tuile(t["ram"], f"{utilise:.1f}".replace(".", ","), f"/ {total:.0f} Go",
                               f"VRAM {vram / 1024:.1f} Go utilisés".replace(".", ",") if vram else "",
                               pct / 100, f"{pct:.0f} %", couleur, couleur_jauge=VIOLET)
            if self.dure("ram_pleine", pct >= 92, 15):
                self.tache("ram", "attention", f"Mémoire presque pleine ({pct:.0f} %)",
                           "Ferme des applis ou des onglets du navigateur pour éviter les ralentissements.", "", None)
            elif pct < 85:
                self.tache_finie("ram")
        # --- Connexion : on compare avec le relevé d'il y a 2 s ---
        vitesse = debit(self.dernier_reseau, m.get("reseau"))
        self.dernier_reseau = m.get("reseau") or self.dernier_reseau
        if vitesse:
            down, up = vitesse
            self.max_down = max(self.max_down, down)
            self.remplir_tuile(t["net"], f"{down:.1f}".replace(".", ",") if down < 10 else f"{down:.0f}",
                               "Mbit/s ↓", f"↑ {up:.1f} Mbit/s envoi".replace(".", ","),
                               down / max(self.max_down, 50), "Active" if down + up > 0.2 else "Calme", VERT, couleur_jauge=VERT)
        elif m.get("reseau") is None:
            self.remplir_tuile(t["net"], "--", "Mbit/s", "mesure impossible", 0, "?", GRIS, GRIS)
        # --- Disques (températures) ---
        if m["disques"]:
            self.temps_disques = m["disques"]
        # --- Capteurs absents ? (on laisse 20 s au démarrage) ---
        if not m["hwinfo"] and time.time() - self.depart > 20:
            self.tache("capteurs", "info", "Température du processeur indisponible",
                       "Lance LibreHardwareMonitor (avec son serveur web) pour l'avoir.", "Diagnostic",
                       lambda: self.aller_a("Santé du PC", "Diagnostic"))
        elif m["hwinfo"]:
            self.tache_finie("capteurs")
        # --- Ventilateurs : l'un d'eux s'est-il arrêté ? ---
        for v in m.get("ventilos", []):
            cle = f"{v['ou']} / {v['nom']}"
            self.ventilos_vus[cle] = max(self.ventilos_vus.get(cle, 0), v["rpm"])
            demande = v.get("pct")
            arrete = (v["ou"] == "Carte mère" and self.ventilos_vus[cle] > 300 and v["rpm"] < 50
                      and (demande is None or demande > 20))
            if self.dure("ventilo " + cle, arrete, 5):
                if self.tache("ventilo " + cle, "alerte", f"{nom_ventilo(v['nom'])} à l'arrêt",
                              "Il tournait tout à l'heure et ne tourne plus. Regarde-le vite : sans lui, ça chauffe.",
                              "Voir", refroidir):
                    self.racine.bell()
            elif not arrete:
                self.tache_finie("ventilo " + cle)
        # --- Le reste de l'appli se sert de ces mesures ---
        self.dernieres_mesures = m
        self.derniere_vitesse = vitesse or getattr(self, "derniere_vitesse", None)
        cpu, gpu = m["cpu_temp"], (m["gpu"][0] if m["gpu"] else None)
        self.noter("cpu_max", cpu)
        self.noter("gpu_max", gpu)
        self.noter_partie(cpu, gpu)
        self.ajouter_historique(cpu, gpu)
        self.dessiner_graphique()
        self.maj_actions_rapides()
        self.maj_mini()
        if self.navigation.actuelle == "Santé du PC":
            self.dessiner_refroidissement()
        self.racine.after(2000, self.maj_mesures)   # et on recommence dans 2 s
    self.en_fond(lire_tout, ensuite)


@methode
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
        seuil = int(REGLAGES.get("alerte_disque", 90)) / 100
        for lettre, total, libre in lecteurs:
            if lettre not in self.lignes_disques:
                l = tk.Frame(self.cadre_dash_disques, bg=CARTE)
                l.pack(fill="x", pady=2)
                tk.Label(l, text=f"{lettre}:", bg=CARTE, fg=TEXTE, font=police(9, True), width=3, anchor="w").pack(side="left")
                texte = tk.Label(l, text="", bg=CARTE, fg=GRIS, font=police(9), width=17, anchor="e")
                texte.pack(side="right")
                barre = Jauge(l, CYAN, epaisseur=5)
                barre.pack(side="left", fill="x", expand=True, padx=(2, 8))
                self.lignes_disques[lettre] = (barre, texte)
            barre, texte = self.lignes_disques[lettre]
            rempli = 1 - libre / total if total else 0
            temp = temps.get(lettre)
            couleur = ROUGE if rempli > 0.97 or (temp or 0) >= 70 else (ORANGE if rempli >= seuil or (temp or 0) >= 60 else CYAN)
            a_surveiller += couleur != CYAN
            texte.config(text=f"{libre / 1e9:,.0f} Go libres".replace(",", " ") + (f" · {temp:.0f}°" if temp else ""))
            barre.regler(rempli, couleur)
            if rempli >= seuil:
                self.tache(f"disque {lettre}", "attention", f"Disque {lettre}: presque plein",
                           f"Il reste {libre / 1e9:.0f} Go sur {total / 1e9:.0f}. Un peu de ménage ?", "Nettoyer",
                           lambda: self.aller_a("Entretien", "Nettoyer"))
            else:
                self.tache_finie(f"disque {lettre}")
            if (temp or 0) >= 70:
                self.tache(f"disque chaud {lettre}", "attention", f"Disque {lettre}: très chaud ({temp:.0f} °C)",
                           "Un SSD qui reste au-dessus de 70 °C s'use plus vite.", "Voir",
                           lambda: self.aller_a("Santé du PC", "Disques"))
            else:
                self.tache_finie(f"disque chaud {lettre}")
        self.lecteurs = lecteurs
        if lecteurs and not getattr(self, "sante_disques_connue", False):
            ok = len(lecteurs) - a_surveiller
            self.dash_disques.config(text=espacer(f"{ok} / {len(lecteurs)} OK"), fg=VERT if not a_surveiller else ORANGE)
        self.racine.after(30000, self.maj_disques_dash)
    self.en_fond(lecteurs_fixes, ensuite)


# ---------- le graphique et son historique ----------

@methode
def charger_historique(self):
    """self.histo[période] = liste de (heure, cpu, gpu). Les périodes longues sont gardées d'un lancement à l'autre."""
    self.histo = {nom: deque(maxlen=int(duree / pas) + 5) for nom, (duree, pas) in PERIODES.items()}
    self.seaux = {}   # pour les périodes longues : on garde le max de chaque tranche de temps
    garde = charger_json(FICHIER_HISTORIQUE, {})
    maintenant = time.time()
    for nom, (duree, _) in PERIODES.items():
        for point in garde.get(nom, []) if isinstance(garde, dict) else []:
            if isinstance(point, list) and len(point) == 3 and maintenant - duree < point[0] <= maintenant:
                self.histo[nom].append(tuple(point))


@methode
def sauver_historique(self):
    ecrire_json(FICHIER_HISTORIQUE, {nom: [list(p) for p in self.histo[nom]] for nom in ("1 h", "24 h")})


@methode
def sauver_historique_regulierement(self):
    self.sauver_historique()
    self.racine.after(5 * 60 * 1000, self.sauver_historique_regulierement)


@methode
def ajouter_historique(self, cpu, gpu):
    maintenant = time.time()
    self.histo["10 min"].append((maintenant, cpu, gpu))
    for nom in ("1 h", "24 h"):
        pas = PERIODES[nom][1]
        seau = self.seaux.setdefault(nom, [maintenant, None, None])
        for i, v in ((1, cpu), (2, gpu)):
            if v is not None:
                seau[i] = v if seau[i] is None else max(seau[i], v)
        if maintenant - seau[0] >= pas:
            self.histo[nom].append((maintenant, seau[1], seau[2]))
            self.seaux[nom] = [maintenant, None, None]


@methode
def choisir_periode(self, nom):
    self.periode = nom
    for n, b in self.boutons_periode.items():
        b.config(bg=melanger(CARTE, ACCENT, 0.18) if n == nom else CARTE, fg=ACCENT if n == nom else GRIS)
    self.dessiner_graphique()


@methode
def dessiner_graphique(self):
    c = self.graphique
    c.delete("all")   # on efface et on redessine tout
    larg, haut = max(c.winfo_width(), 200), max(c.winfo_height(), 120)
    gauche, droite, bas, mini, maxi = 34, larg - 8, haut - 20, 20, 100
    duree, pas = PERIODES[self.periode]
    maintenant = time.time()

    def y(temp):
        temp = min(max(temp, mini), maxi)
        return bas - (temp - mini) / (maxi - mini) * (bas - 8)

    def x(instant):
        return gauche + (instant - (maintenant - duree)) / duree * (droite - gauche)

    for t in (20, 40, 60, 80, 100):   # lignes repères
        c.create_line(gauche, y(t), droite, y(t), fill="#16162a")
        c.create_text(gauche - 6, y(t), text=f"{t}°", fill=GRIS, anchor="e", font=police(8))
    c.create_line(gauche, y(ALERTE_GPU), droite, y(ALERTE_GPU), fill=melanger(CARTE, ORANGE, 0.6), dash=(4, 4))
    self.legende_alerte.config(text=f"┄ alerte {ALERTE_GPU}°")
    debut, milieu = {"10 min": ("-10 min", "-5 min"), "1 h": ("-1 h", "-30 min"), "24 h": ("-24 h", "-12 h")}[self.periode]
    for texte, px, ancre in ((debut, gauche, "w"), (milieu, (gauche + droite) / 2, "center"), ("maintenant", droite, "e")):
        c.create_text(px, haut - 6, text=texte, fill=GRIS, anchor=ancre, font=police(8))
    points = [p for p in self.histo[self.periode] if p[0] >= maintenant - duree]
    for indice, couleur in ((1, CYAN), (2, ROSE)):
        morceaux, trace, avant = [], [], None
        for p in points:
            v = p[indice]
            if v is None or (avant is not None and p[0] - avant > pas * 4):   # trou dans les mesures : on coupe la ligne
                morceaux.append(trace)
                trace = []
            if v is not None:
                trace += [x(p[0]), y(v)]
                avant = p[0]
        morceaux.append(trace)
        for pts in morceaux:
            if len(pts) >= 4:
                for largeur, force in ((12, 0.06), (8, 0.13), (5, 0.25)):
                    c.create_line(pts, fill=melanger(CARTE, couleur, force), width=largeur, smooth=True,
                                  capstyle="round", joinstyle="round", splinesteps=24)
                c.create_line(pts, fill=couleur, width=2.5, smooth=True, capstyle="round", splinesteps=24)
        dernier = next((p for p in reversed(points) if p[indice] is not None), None)
        if dernier and maintenant - dernier[0] < pas * 4:   # un point sur la valeur actuelle
            px, py = x(dernier[0]), y(dernier[indice])
            c.create_oval(px - 4, py - 4, px + 4, py + 4, fill=couleur, outline="")
    if len(points) < 2:
        c.create_text((gauche + droite) / 2, (bas + 8) / 2, fill=ETEINT, font=police(9),
                      text="Les courbes se dessinent au fur et à mesure" if self.periode == "10 min"
                      else f"Pas encore assez de mesures sur {self.periode} : laisse la boîte à outils ouverte")


# ---------- musique + micro (toutes les 3 s) ----------

@methode
def suivre_musique(self):
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


@methode
def afficher_micro(self):
    self.maj_actions_rapides()


@methode
def basculer_micro(self):
    import importlib.util
    try:
        absent = importlib.util.find_spec("pycaw") is None   # on regarde juste si la librairie est là, sans la charger ici
    except (ImportError, ValueError):
        absent = False
    if absent:
        if not messagebox.askyesno("Micro", "Pour couper le micro, il faut la librairie pycaw.\n\nL'installer maintenant ?"):
            return
        if not installer_paquets("pycaw"):
            messagebox.showerror("Oups", "Installation ratée. Dans PowerShell :\npython -m pip install pycaw")
            return

    def ensuite(coupe):
        if isinstance(coupe, Exception) or coupe is None:
            self.toast("Micro introuvable : vérifie qu'il est branché (ou choisis-le dans les Réglages)", "attention")
            return
        self.micro_coupe = coupe
        self.afficher_micro()
        self.toast("Micro coupé" if coupe else "Micro réactivé", "alerte" if coupe else "ok")
    self.en_fond(lambda: micro("basculer"), ensuite)


# =============================================================
#  🩺 SANTÉ DU PC  -  bilan, refroidissement, disques, mises à jour, diagnostic
# =============================================================

NOMS_TEMPERATURES = {   # (où, nom donné par LibreHardwareMonitor) -> nom clair. None = on ne l'affiche pas
    ("Processeur", "core max"): "Cœur le plus chaud du processeur",
    ("Processeur", "core average"): None,
    ("Carte graphique", "gpu core"): None,   # déjà affichée (lecture directe)
    ("Carte graphique", "gpu hot spot"): "Point le plus chaud de la carte graphique",
    ("Carte graphique", "gpu memory junction"): "Mémoire de la carte graphique",
    ("Carte mère", "system"): "Intérieur du boîtier (carte mère)",
    ("Carte mère", "vrm mos"): "Alimentation du processeur (VRM)",
    ("Carte mère", "pch"): "Puce de la carte mère (chipset)",
    ("Carte mère", "cpu"): None,
    ("Carte mère", "cpu socket"): None,
    ("Carte mère", "pcie x1"): None,
}
DOSSIER_PLUGIN = Path(APPDATA) / "Elgato" / "StreamDeck" / "Plugins" / "com.crz.capteurs.sdPlugin"


def diagnostic(appli):
    """Vérifie que chaque morceau de la boîte à outils est bien branché.
    Renvoie [(niveau, titre, explication), ...]. Tourne en arrière-plan : ne touche pas à l'affichage."""
    points = []
    # 1. Capteurs de température
    if lire_lhm() is not None:
        points.append(("ok", "Capteurs de température", "LibreHardwareMonitor répond : températures et ventilateurs disponibles."))
    elif lire_hwinfo() is not None:
        points.append(("ok", "Capteurs de température", "HWiNFO partage ses mesures (attention : la version gratuite coupe le partage au bout de 12 h)."))
    else:
        points.append(("attention", "Capteurs de température",
                       "Aucun logiciel de capteurs ne répond. Lance LibreHardwareMonitor, puis Options > Remote Web Server > Run."))
    # 2. Carte graphique
    if lire_gpu_lhm() is not None:
        points.append(("ok", "Carte graphique", "Lue par LibreHardwareMonitor (rien de plus ne sollicite le pilote NVIDIA)."))
    elif lire_gpu_nvml() is not None:
        points.append(("ok", "Carte graphique", "Lue directement auprès du pilote NVIDIA (rapide, sans ralentir le PC)."))
    elif lire_gpu() is not None:
        points.append(("ok", "Carte graphique", "Lue avec l'outil nvidia-smi (un peu plus lent que la lecture directe)."))
    else:
        points.append(("attention", "Carte graphique", "Impossible de lire la carte NVIDIA. Vérifie que son pilote est installé."))
    # 3. Micro
    import importlib.util
    try:
        pycaw_present = importlib.util.find_spec("pycaw") is not None
    except (ImportError, ValueError):
        pycaw_present = True
    etat = micro("etat") if pycaw_present else None
    if not pycaw_present:
        points.append(("attention", "Micro", "La librairie pycaw n'est pas installée. Clique sur le bouton Micro de l'accueil pour l'installer."))
    elif etat is None:
        points.append(("attention", "Micro", "Aucun micro trouvé. Branche ton casque, ou choisis le bon micro dans Réglages > Micro."))
    else:
        nom = REGLAGES.get("micro_nom") or "micro par défaut de Windows"
        points.append(("ok", "Micro", f"Branché ({nom}), actuellement {'coupé' if etat else 'ouvert'}."))
    # 4. Icône près de l'horloge + notifications
    if appli["icone"]:
        points.append(("ok", "Icône près de l'horloge", "Active : elle sert aussi à afficher les notifications Windows."))
    else:
        points.append(("attention", "Icône près de l'horloge", "Absente (librairies pystray et Pillow) : pas de notifications Windows."))
    # 5. Serveur local
    if appli["serveur"]:
        points.append(("ok", "Liaison téléphone et Stream Deck", f"Le petit serveur écoute sur le port {PORT_SERVEUR}."))
    else:
        points.append(("alerte", "Liaison téléphone et Stream Deck",
                       f"Le port {PORT_SERVEUR} est déjà pris : une autre boîte à outils tourne peut-être déjà."))
    # 6. Plugin Stream Deck
    version = None
    try:
        version = json.loads((DOSSIER_PLUGIN / "manifest.json").read_text(encoding="utf-8")).get("Version")
    except (OSError, ValueError):
        pass
    if version and time.time() - appli["dernier_appel_local"] < 20:
        points.append(("ok", "Plugin Stream Deck", f"Installé (v{version}) et connecté : il vient de demander des mesures."))
    elif version:
        points.append(("info", "Plugin Stream Deck", f"Installé (v{version}) mais silencieux : le logiciel Stream Deck est peut-être fermé."))
    else:
        points.append(("info", "Plugin Stream Deck", "Pas installé. Tu peux l'installer depuis la page Téléphone > Stream Deck."))
    # 7. Démarrage, mises à jour
    points.append(("ok", "Lancement au démarrage de Windows", "Activé." ) if LANCEUR_DEMARRAGE.exists() else
                  ("info", "Lancement au démarrage de Windows", "Désactivé (ça se change dans les Réglages)."))
    points.append(("ok", "Mises à jour de la boîte à outils", f"Automatiques. Version actuelle : v{VERSION}.") if REGLAGES.get("maj_auto", True) else
                  ("info", "Mises à jour de la boîte à outils", f"Manuelles. Version actuelle : v{VERSION}."))
    # 8. Stabilité
    arrets = [a for a in charger_json(FICHIER_ARRETS, []) if isinstance(a, dict)]
    limite = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 7 * 86400))
    recents = [a for a in arrets if str(a.get("vu", "")) >= limite]
    cette_version = [a for a in recents if a.get("version") == VERSION]
    if not recents:
        points.append(("ok", "Stabilité", "Aucun arrêt brutal ces 7 derniers jours."))
    elif not cette_version:
        points.append(("ok", "Stabilité", f"{len(recents)} arrêt{' brutal' if len(recents) == 1 else 's brutaux'} cette semaine, mais aucun depuis cette version."))
    else:
        points.append(("attention", "Stabilité", f"{len(cette_version)} arrêt{' brutal' if len(cette_version) == 1 else 's brutaux'} avec cette version cette semaine. "
                                                 "Les détails sont dans plantage.txt (bouton « Ouvrir le dossier »)."))
    return points


@methode
def page_sante(self, cadre):
    onglets = self.sous_pages["Santé du PC"] = Onglets(cadre)
    onglets.pack(fill="both", expand=True)
    self.etats = {}          # ce qu'on sait de chaque sujet : clé -> (niveau, phrase)
    self.temps_max = {}      # température max vue depuis le lancement, par capteur
    self.lignes_ventilos, self.lignes_temps = {}, {}

    # ----- Bilan -----
    bilan = onglets.ajouter("Bilan")
    tete = tk.Frame(bilan, bg=CARTE)
    tete.pack(fill="x", pady=(0, 8))
    self.titre_bilan = libelle(tete, "Bilan en cours...", 15, TEXTE, True)
    self.titre_bilan.pack(side="left")
    Bouton(tete, "🔄 Tout revérifier", self.tout_reverifier).pack(side="right")
    self.cadre_bilan = tk.Frame(bilan, bg=CARTE)
    self.cadre_bilan.pack(fill="x")
    self.lignes_bilan = {}
    for cle, titre, onglet in (("temperatures", "Températures", "Refroidissement"),
                               ("ventilos", "Ventilateurs et pompe", "Refroidissement"),
                               ("disques", "Disques", "Disques"),
                               ("pilote", "Pilote de la carte graphique", "Mises à jour"),
                               ("applis", "Applications et autres pilotes", "Mises à jour"),
                               ("diagnostic", "La boîte à outils elle-même", "Diagnostic")):
        ligne = tk.Frame(self.cadre_bilan, bg=CARTE)
        ligne.pack(fill="x", pady=6)
        point = tk.Label(ligne, text="●", bg=CARTE, fg=GRIS, font=police(15))
        point.pack(side="left", padx=(0, 12))
        Bouton(ligne, "Voir  ›", lambda o=onglet: onglets.choisir(o), petit=True).pack(side="right")
        textes = tk.Frame(ligne, bg=CARTE)
        textes.pack(side="left", fill="x", expand=True)
        libelle(textes, titre, 11, TEXTE, True).pack(fill="x")
        detail = libelle(textes, "Vérification...", 9, GRIS, largeur=640)
        detail.pack(fill="x")
        self.lignes_bilan[cle] = (point, detail)
    self.cadre_autres = tk.Frame(bilan, bg=CARTE)
    self.cadre_autres.pack(fill="x", pady=(8, 0))

    # ----- Refroidissement -----
    refroid = onglets.ajouter("Refroidissement", carte=False)
    refroid.columnconfigure(0, weight=1, uniform="r")
    refroid.columnconfigure(1, weight=1, uniform="r")
    refroid.rowconfigure(0, weight=1)
    carte_v = Carte(refroid, padx=18, pady=14)
    carte_v.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    petit_titre(carte_v, "Ventilateurs et pompe").pack(fill="x")
    self.cadre_ventilos = tk.Frame(carte_v, bg=CARTE)
    self.cadre_ventilos.pack(fill="x", pady=(6, 0))
    self.info_ventilos = libelle(carte_v, "", 9, GRIS, largeur=380)
    self.info_ventilos.pack(fill="x", pady=(8, 0))
    carte_t = Carte(refroid, padx=18, pady=14)
    carte_t.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    petit_titre(carte_t, "Températures").pack(fill="x")
    self.cadre_temps = tk.Frame(carte_t, bg=CARTE)
    self.cadre_temps.pack(fill="x", pady=(6, 0))
    self.info_watts = libelle(carte_t, "", 9, GRIS, largeur=380)
    self.info_watts.pack(fill="x", pady=(8, 0))
    aide = Carte(refroid, padx=18, pady=10)
    aide.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
    libelle(aide, "Comment lire ces chiffres ?", 10, TEXTE, True).pack(fill="x")
    libelle(aide, "Un ventilateur se mesure en tours par minute (tr/min) : plus ça chauffe, plus il tourne vite. "
                  "La pompe du watercooling, elle, tourne toujours à fond : c'est normal. Les ventilateurs de la carte "
                  "graphique s'arrêtent quand elle est froide : c'est normal aussi. Si un ventilateur de la carte mère "
                  "s'arrête alors qu'il tournait, tu reçois une alerte.", 9, GRIS, largeur=860).pack(fill="x")

    # ----- Disques -----
    disques = onglets.ajouter("Disques")
    tete = tk.Frame(disques, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Santé des disques", 13, TEXTE, True).pack(side="left")
    Bouton(tete, "🔄 Revérifier", self.verifier_disques).pack(side="right")
    libelle(disques, "L'état de santé vient de Windows ; l'usure, la température et les données écrites viennent des capteurs.",
            9, GRIS, largeur=860).pack(fill="x", pady=(2, 6))
    self.cadre_disques = tk.Frame(disques, bg=CARTE)
    self.cadre_disques.pack(fill="x")

    # ----- Mises à jour -----
    maj = onglets.ajouter("Mises à jour")
    tete = tk.Frame(maj, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Pilote de la carte graphique", 12, TEXTE, True).pack(side="left")
    self.lien_pilote = PAGE_PILOTES_NVIDIA
    self.btn_pilote = Bouton(tete, "⬇ Télécharger", lambda: os.startfile(self.lien_pilote), "succes", petit=True)
    self.info_pilote = libelle(maj, "Vérification...", 10, GRIS)
    self.info_pilote.pack(fill="x", pady=(2, 10))

    tete = tk.Frame(maj, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Applications", 12, TEXTE, True).pack(side="left")
    self.btn_maj = Bouton(tete, "⬆ Mettre à jour la sélection", self.lancer_maj, "succes", petit=True)
    self.btn_maj.pack(side="right")
    self.btn_maj.activer(False)
    Bouton(tete, "🔍 Vérifier", lambda: (self.verifier_maj(), self.verifier_pilotes()), petit=True).pack(side="right", padx=8)
    self.info_maj = libelle(maj, "", 9, GRIS, largeur=860)
    self.info_maj.pack(fill="x", pady=(2, 4))
    self.liste_maj = tk.Listbox(maj, height=6, bg=CHAMP, fg=TEXTE, selectbackground=melanger(CHAMP, ACCENT, 0.3),
                                selectforeground="white", relief="flat", highlightthickness=1, highlightbackground=BORD,
                                font=police(10), activestyle="none", selectmode="extended", exportselection=False)
    self.liste_maj.pack(fill="x")

    tete = tk.Frame(maj, bg=CARTE)
    tete.pack(fill="x", pady=(12, 0))
    libelle(tete, "Autres pilotes et carte mère", 12, TEXTE, True).pack(side="left")
    Bouton(tete, "🌐 Page MSI", lambda: os.startfile(PAGE_MSI), petit=True).pack(side="right")
    Bouton(tete, "🪟 Windows Update", lambda: os.startfile("ms-settings:windowsupdate-optionalupdates"), petit=True).pack(side="right", padx=8)
    self.info_pilotes = libelle(maj, "Autres pilotes : vérification via Windows Update...", 10, GRIS, largeur=860)
    self.info_pilotes.pack(fill="x", pady=(2, 0))
    bios = version_bios()
    libelle(maj, (f"Carte mère MSI PRO B760-P : BIOS {bios[0]} du {bios[1]}. " if bios else "Carte mère MSI PRO B760-P. ") +
            "Compare avec la page MSI ; une mise à jour du BIOS n'est utile que si elle corrige un souci que tu as.",
            10, GRIS, largeur=860).pack(fill="x", pady=(4, 0))
    self.applis_maj = []

    # ----- Diagnostic -----
    diag = onglets.ajouter("Diagnostic")
    tete = tk.Frame(diag, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Tout est-il bien branché ?", 13, TEXTE, True).pack(side="left")
    Bouton(tete, "🔄 Revérifier", self.lancer_diagnostic, petit=True).pack(side="right")
    Bouton(tete, "📋 Copier le rapport", self.copier_diagnostic, petit=True).pack(side="right", padx=8)
    Bouton(tete, "📁 Ouvrir le dossier", self.ouvrir_dossier_appli, petit=True).pack(side="right")
    libelle(diag, "La boîte à outils s'appuie sur plusieurs morceaux. Ici tu vois d'un coup d'œil lequel manque, et quoi faire.",
            9, GRIS, largeur=860).pack(fill="x", pady=(2, 6))
    self.cadre_diagnostic = tk.Frame(diag, bg=CARTE)
    self.cadre_diagnostic.pack(fill="x")
    self.points_diagnostic = []
    onglets.quand_change = lambda nom: nom == "Diagnostic" and self.lancer_diagnostic()

    self.racine.after(3000, self.verifier_maj)
    self.racine.after(4000, self.verifier_disques)
    self.racine.after(5000, self.verifier_pilotes)
    self.racine.after(9000, self.lancer_diagnostic)
    self.dessiner_bilan()


@methode
def tout_reverifier(self):
    self.verifier_maj()
    self.verifier_pilotes()
    self.verifier_disques()
    self.lancer_diagnostic()
    self.toast("Vérification relancée : le bilan se met à jour dans quelques secondes", "info")


@methode
def dessiner_bilan(self):
    """Met à jour les 6 lignes du bilan à partir de ce qu'on sait (self.etats + les dernières mesures)."""
    if not hasattr(self, "lignes_bilan"):
        return
    m = getattr(self, "dernieres_mesures", None) or {}
    etats = dict(self.etats)
    # Températures
    cpu, gpu = m.get("cpu_temp"), (m.get("gpu") or [None])[0]
    if cpu is None and gpu is None:
        etats["temperatures"] = ("inconnu", "Pas encore de mesure.")
    else:
        mots, pire = [], "ok"
        for nom, valeur, alerte in (("processeur", cpu, ALERTE_CPU), ("carte graphique", gpu, ALERTE_GPU)):
            if valeur is not None:
                etat, couleur = self.etat_temperature(valeur, alerte)
                mots.append(f"{nom} {valeur:.0f} °C ({etat.lower()})")
                if couleur == ROUGE:
                    pire = "alerte"
        phrase = ", ".join(mots)
        etats["temperatures"] = (pire, phrase[:1].upper() + phrase[1:] + ".")
    # Ventilateurs
    ventilos = [v for v in m.get("ventilos", []) if self.ventilos_vus.get(f"{v['ou']} / {v['nom']}", 0) > 0] if hasattr(self, "ventilos_vus") else []
    arretes = [t for cle, t in self.taches.items() if cle.startswith("ventilo ")]
    if arretes:
        etats["ventilos"] = ("alerte", arretes[0]["texte"] + ". " + arretes[0]["detail"])
    elif ventilos:
        pompe = next((v for v in ventilos if v["nom"].lower().startswith("pump")), None)
        tournent = sum(1 for v in ventilos if v["rpm"] > 0)
        etats["ventilos"] = ("ok", pluriel(f"{tournent} ventilateur(s) en marche sur {len(ventilos)}", tournent) +
                             (", pompe à " + f"{pompe['rpm']:,.0f}".replace(",", " ") + " tr/min" if pompe else "") + ".")
    else:
        etats["ventilos"] = ("inconnu", "Pas de mesure : il faut LibreHardwareMonitor pour voir les ventilateurs.")
    # Applications + autres pilotes : on réunit les deux
    a, p = etats.pop("applis_seules", None), etats.pop("pilotes_wu", None)
    if a or p:
        niveaux = [x[0] for x in (a, p) if x]
        etats["applis"] = (next((n for n in ("attention", "info", "ok") if n in niveaux), "inconnu"),
                           " ".join(x[1] for x in (a, p) if x))
    for cle, (point, detail) in self.lignes_bilan.items():
        niveau, phrase = etats.get(cle, ("inconnu", "Vérification..."))
        point.config(fg=COULEUR_NIVEAU.get(niveau, GRIS))
        detail.config(text=phrase)
    total = len(self.taches)   # le même nombre que dans le menu et sur l'accueil
    niveaux = {t["niveau"] for t in self.taches.values()}
    if total == 0:
        self.titre_bilan.config(text="✓  Ton PC est en forme", fg=VERT)
    elif niveaux <= {"info"}:   # que des petites choses (une appli à mettre à jour...)
        self.titre_bilan.config(text=pluriel(f"✓  Ton PC est en forme · {total} petite(s) chose(s) à faire, rien d'urgent", total), fg=CYAN)
    else:
        self.titre_bilan.config(text=pluriel(f"{total} point(s) à regarder", total), fg=ROUGE if "alerte" in niveaux else ORANGE)
    # Les autres points « À faire » qui ne rentrent dans aucune ligne
    vider(self.cadre_autres)
    autres = [t for cle, t in self.taches.items()
              if not cle.startswith(("ventilo ", "cpu_chaud", "gpu_chaud", "pilote", "applis", "pilotes_wu", "sante_disque"))]
    if autres:
        petit_titre(self.cadre_autres, "Aussi à noter").pack(fill="x", pady=(6, 0))
    for t in sorted(autres, key=lambda t: ORDRE_NIVEAUX.get(t["niveau"], 9)):
        ligne_etat(self.cadre_autres, t["niveau"], t["texte"], t["detail"], t["bouton"] if t["action"] else None, t["action"])


@methode
def dessiner_refroidissement(self):
    """Met à jour les ventilateurs et les températures (appelée toutes les 2 s quand la page Santé est ouverte)."""
    m = getattr(self, "dernieres_mesures", None) or {}
    self.dessiner_bilan()
    # --- Ventilateurs ---
    caches = 0
    for v in m.get("ventilos", []):
        cle = f"{v['ou']} / {v['nom']}"
        if self.ventilos_vus.get(cle, 0) <= 0 and v["ou"] == "Carte mère":
            caches += 1   # prise vide sur la carte mère : rien n'est branché dessus
            continue
        if cle not in self.lignes_ventilos:
            ligne = tk.Frame(self.cadre_ventilos, bg=CARTE)
            ligne.pack(fill="x", pady=5)
            haut = tk.Frame(ligne, bg=CARTE)
            haut.pack(fill="x")
            libelle(haut, nom_ventilo(v["nom"]), 10, TEXTE, True).pack(side="left")
            etat = tk.Label(haut, text="", bg=CARTE, fg=VERT, font=police(8, True))
            etat.pack(side="right")
            vitesse = tk.Label(haut, text="", bg=CARTE, fg=TEXTE, font=police(10))
            vitesse.pack(side="right", padx=(0, 12))
            jauge = Jauge(ligne, CYAN, epaisseur=5)
            jauge.pack(fill="x", pady=(2, 0))
            self.lignes_ventilos[cle] = (vitesse, etat, jauge)
        vitesse, etat, jauge = self.lignes_ventilos[cle]
        maxi = max(self.ventilos_vus.get(cle, 0), 1)
        vitesse.config(text=f"{v['rpm']:,.0f} tr/min".replace(",", " "))
        fraction = (v["pct"] / 100) if v.get("pct") is not None else v["rpm"] / maxi
        if ("ventilo " + cle) in self.taches:
            etat.config(text=espacer("arrêté"), fg=ROUGE)
            jauge.regler(0.02, ROUGE)
        elif v["rpm"] <= 0:
            etat.config(text=espacer("au repos"), fg=GRIS)
            jauge.regler(0, GRIS)
        else:
            etat.config(text=espacer(f"{v['pct']:.0f} %" if v.get("pct") is not None else "tourne"), fg=VERT)
            jauge.regler(fraction, ROSE if v["ou"] == "Carte graphique" else CYAN)
    if not m.get("ventilos"):
        self.info_ventilos.config(text="Aucun ventilateur visible. Pour les voir, lance LibreHardwareMonitor "
                                       "(Options > Remote Web Server > Run). Détails dans l'onglet Diagnostic.")
    elif caches:
        self.info_ventilos.config(text=pluriel(f"{caches} prise(s) de ventilateur", caches) + " de la carte mère sans rien de branché (non affichées). "
                                       "Les ventilateurs reliés à un boîtier de contrôle séparé n'apparaissent pas ici.")
    else:
        self.info_ventilos.config(text="")
    # --- Températures ---
    liste = []
    if m.get("cpu_temp") is not None:
        liste.append(("Processeur", m["cpu_temp"], ALERTE_CPU))
    if m.get("gpu"):
        liste.append(("Carte graphique", m["gpu"][0], ALERTE_GPU))
    barrettes = [v for ou, nom, v in m.get("temps", []) if ou == "Mémoire"]
    for ou, nom, valeur in m.get("temps", []):
        propre = NOMS_TEMPERATURES.get((ou, nom.lower()), "?")
        if propre == "?" and ou == "Carte mère" and nom.lower().startswith("m2"):
            propre = "Emplacement SSD " + nom.replace("M2", "M.2")
        if propre and propre != "?":
            liste.append((propre, valeur, 95 if "Point le plus chaud" in propre else 90))
    if barrettes:
        liste.append(("Mémoire (barrette la plus chaude)", max(barrettes), 70))
    for nom, valeur, alerte in liste:
        if nom not in self.lignes_temps:
            ligne = tk.Frame(self.cadre_temps, bg=CARTE)
            ligne.pack(fill="x", pady=4)
            haut = tk.Frame(ligne, bg=CARTE)
            haut.pack(fill="x")
            libelle(haut, nom, 10, TEXTE, nom in ("Processeur", "Carte graphique")).pack(side="left")
            maxi = tk.Label(haut, text="", bg=CARTE, fg=ETEINT, font=police(8))
            maxi.pack(side="right")
            texte = tk.Label(haut, text="", bg=CARTE, fg=TEXTE, font=police(10, True))
            texte.pack(side="right", padx=(0, 10))
            jauge = Jauge(ligne, VERT, epaisseur=5)
            jauge.pack(fill="x", pady=(2, 0))
            self.lignes_temps[nom] = (texte, maxi, jauge)
        texte, maxi, jauge = self.lignes_temps[nom]
        self.temps_max[nom] = max(self.temps_max.get(nom, 0), valeur)
        couleur = self.etat_temperature(valeur, alerte)[1]
        texte.config(text=f"{valeur:.0f} °C", fg=couleur if couleur != VERT else TEXTE)
        maxi.config(text=f"max {self.temps_max[nom]:.0f}°")
        jauge.regler(valeur / 100, couleur)
    watts = m.get("watts", {})
    morceaux = [f"{nom.lower()} {valeur:.0f} W" for nom, valeur in watts.items()]
    if not watts and m.get("gpu"):
        morceaux = [f"carte graphique {m['gpu'][3]:.0f} W"]
    self.info_watts.config(text=("Consommation en ce moment : " + ", ".join(morceaux) + ".") if morceaux else "")


# ---------- mises à jour (pilote NVIDIA, applis, Windows Update) ----------

@methode
def verifier_maj(self):
    self.info_maj.config(text="Je demande à Windows quelles applis ont une mise à jour (ça peut prendre 30 s)...", fg=GRIS)

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
            self.info_maj.config(text=f"Erreur : {res}", fg=ROUGE)
            return
        installe, dernier, self.lien_pilote, applis = res
        voir = lambda: self.aller_a("Santé du PC", "Mises à jour")
        self.btn_pilote.pack_forget()
        if installe and dernier:
            try:
                a_jour = float(installe) >= float(dernier)
            except ValueError:
                a_jour = installe == dernier
            if a_jour:
                self.info_pilote.config(text=f"✓ À jour (version {installe}).", fg=VERT)
                self.etats["pilote"] = ("ok", f"À jour (version {installe}).")
                self.tache_finie("pilote")
            else:
                self.info_pilote.config(text=f"Nouvelle version {dernier} disponible (tu as la {installe}). Télécharge-la, "
                                             "lance l'installation et choisis « Installation express ».", fg=ORANGE)
                self.btn_pilote.changer("⬇ Télécharger", "succes")
                self.btn_pilote.pack(side="right")
                self.etats["pilote"] = ("attention", f"Nouvelle version {dernier} disponible (tu as la {installe}).")
                self.tache("pilote", "attention", f"Nouveau pilote graphique ({dernier})",
                           "Les nouveaux pilotes améliorent souvent les jeux récents.", "Voir", voir)
        else:
            self.info_pilote.config(text=f"Version installée : {installe or 'inconnue'}. Impossible de comparer en ligne pour l'instant.", fg=GRIS)
            self.btn_pilote.changer("🌐 Page des pilotes", "discret")
            self.btn_pilote.pack(side="right")
            self.etats["pilote"] = ("inconnu", f"Version installée : {installe or 'inconnue'} (comparaison en ligne impossible).")
        self.liste_maj.delete(0, "end")
        if applis is None:
            self.info_maj.config(text="winget introuvable : il s'installe avec « Programme d'installation d'application » "
                                      "dans le Microsoft Store.", fg=GRIS)
            self.etats["applis_seules"] = ("inconnu", "Applications : winget introuvable.")
        else:
            self.applis_maj = applis
            for a in applis:
                self.liste_maj.insert("end", f"  {a['nom']}   {a['version']} → {a['dispo']}")
            if applis:
                self.info_maj.config(text=pluriel(f"{len(applis)} appli(s) à mettre à jour. ", len(applis)) + "Clique pour sélectionner "
                                          "(Ctrl+clic pour plusieurs), puis « Mettre à jour la sélection ».", fg=TEXTE)
                self.btn_maj.activer(True)
                self.etats["applis_seules"] = ("info", pluriel(f"{len(applis)} appli(s) à mettre à jour.", len(applis)))
                self.tache("applis", "info", pluriel(f"{len(applis)} appli(s) à mettre à jour", len(applis)),
                           ", ".join(a["nom"] for a in applis[:4]) + ("..." if len(applis) > 4 else ""), "Voir", voir)
            else:
                self.info_maj.config(text="✓ Toutes tes applis sont à jour.", fg=VERT)
                self.btn_maj.activer(False)
                self.etats["applis_seules"] = ("ok", "Applications à jour.")
                self.tache_finie("applis")
        self.sous_pages["Santé du PC"].pastille("Mises à jour", str(len(applis)) if applis else "")
        self.dessiner_bilan()
    self.en_fond(travail, ensuite)


@methode
def lancer_maj(self):
    choisies = [self.applis_maj[i] for i in self.liste_maj.curselection()]
    if not choisies:
        self.info_maj.config(text="Sélectionne d'abord une ou plusieurs applis dans la liste 👇", fg=ORANGE)
        return
    noms = ", ".join(a["nom"] for a in choisies)
    if not messagebox.askyesno("Mises à jour", f"Mettre à jour : {noms} ?\n\n"
                                               "Certaines applis demanderont l'accès admin, et il vaut mieux "
                                               "les fermer avant."):
        return
    self.btn_maj.activer(False)
    self.info_maj.config(text=f"Mise à jour en cours : {noms}... (laisse tourner)", fg=TEXTE)

    def travail():
        return [(a["nom"], mettre_a_jour(a["id"])) for a in choisies]

    def ensuite(res):
        if isinstance(res, Exception):
            self.info_maj.config(text=f"Erreur : {res}", fg=ROUGE)
            return
        ok = [n for n, r in res if r]
        self.noter("maj", len(ok), "somme")
        rate = [n for n, r in res if not r]
        texte = (f"✓ À jour : {', '.join(ok)}. " if ok else "") + (f"Raté : {', '.join(rate)}." if rate else "")
        self.verifier_maj()
        self.racine.after(200, lambda: self.info_maj.config(text=texte, fg=VERT if not rate else ORANGE))
    self.en_fond(travail, ensuite)


@methode
def verifier_pilotes(self):
    def ensuite(pilotes):
        if isinstance(pilotes, Exception):
            self.info_pilotes.config(text=f"Autres pilotes : impossible de demander à Windows Update ({pilotes}).", fg=GRIS)
            self.etats["pilotes_wu"] = ("inconnu", "Autres pilotes : Windows Update ne répond pas.")
        elif pilotes:
            liste = "\n".join("   • " + p[:90] for p in pilotes[:6])
            self.info_pilotes.config(text=pluriel(f"{len(pilotes)} pilote(s) proposé(s)", len(pilotes)) + " par Windows Update "
                                          f"(dans « Mises à jour facultatives ») :\n{liste}", fg=ORANGE)
            self.etats["pilotes_wu"] = ("info", pluriel(f"{len(pilotes)} pilote(s) proposé(s) par Windows Update.", len(pilotes)))
            self.tache("pilotes_wu", "info", pluriel(f"{len(pilotes)} pilote(s) dans Windows Update", len(pilotes)), "Ils sont dans les mises à jour facultatives.",
                       "Voir", lambda: self.aller_a("Santé du PC", "Mises à jour"))
        else:
            self.info_pilotes.config(text="✓ Autres pilotes : rien de nouveau dans Windows Update.", fg=VERT)
            self.etats["pilotes_wu"] = ("ok", "Autres pilotes à jour.")
            self.tache_finie("pilotes_wu")
        self.dessiner_bilan()
    self.en_fond(pilotes_windows_update, ensuite)


# ---------- disques ----------

@methode
def verifier_disques(self):
    vider(self.cadre_disques)
    libelle(self.cadre_disques, "Analyse...", 10, GRIS).pack(anchor="w")

    def puce(parent, texte, couleur):
        tk.Label(parent, text=texte, bg=melanger(SURFACE, couleur, 0.14), fg=couleur, font=police(9, True),
                 padx=8, pady=2).pack(side="left", padx=(0, 6))

    def ensuite(disques):
        vider(self.cadre_disques)
        if isinstance(disques, Exception) or not disques:
            libelle(self.cadre_disques, "Impossible de lire les disques (Windows n'a pas répondu).", 10, GRIS).pack(anchor="w")
            self.etats["disques"] = ("inconnu", "Impossible de lire l'état des disques.")
            self.dessiner_bilan()
            return
        nb_ok, soucis = 0, []
        for d in disques:
            probleme = d["panne"] or d["sante"] not in ("Healthy", None) or (d["vie"] is not None and d["vie"] < 20)
            fatigue = d["vie"] is not None and d["vie"] < 50
            couleur = ROUGE if probleme else (ORANGE if fatigue else VERT)
            nb_ok += not probleme
            bloc = tk.Frame(self.cadre_disques, bg=SURFACE, highlightthickness=1, highlightbackground=BORD, padx=12, pady=8)
            bloc.pack(fill="x", pady=4)
            haut = tk.Frame(bloc, bg=SURFACE)
            haut.pack(fill="x")
            tk.Label(haut, text="●", bg=SURFACE, fg=couleur, font=police(12)).pack(side="left", padx=(0, 8))
            libelle(haut, d["nom"], 11, TEXTE, True, SURFACE).pack(side="left")
            libelle(haut, f"   {d['type']} · {d['taille'] / 1e9:.0f} Go", 9, GRIS, fond=SURFACE).pack(side="left")
            puces = tk.Frame(bloc, bg=SURFACE)
            puces.pack(fill="x", pady=(6, 0))
            if probleme:
                puce(puces, "PROBLÈME : sauvegarde tes fichiers", ROUGE)
                soucis.append(d["nom"])
                self.tache("sante_disque " + d["nom"], "alerte", f"Disque {d['nom']} en mauvais état",
                           "Sauvegarde ce qui compte dessus dès que possible.", "Voir",
                           lambda: self.aller_a("Santé du PC", "Disques"))
            else:
                puce(puces, "Bon état", VERT)
                self.tache_finie("sante_disque " + d["nom"])
            if d["vie"] is not None:
                puce(puces, f"Vie restante {d['vie']:.0f} %", couleur if fatigue or probleme else CYAN)
            if d["temp"] is not None:
                puce(puces, f"{d['temp']:.0f} °C", ROUGE if d["temp"] >= 70 else (ORANGE if d["temp"] >= 60 else CYAN))
            if d["ecrit"]:
                valeur, unite = d["ecrit"]
                puce(puces, f"{valeur:,.0f} {unite} écrits".replace(",", " "), GRIS)
        self.sante_disques_connue = True
        self.dash_disques.config(text=espacer(f"{nb_ok} / {len(disques)} OK"), fg=VERT if nb_ok == len(disques) else ROUGE)
        if soucis:
            self.etats["disques"] = ("alerte", f"Problème sur : {', '.join(soucis)}. Sauvegarde tes fichiers.")
        else:
            pleins = [cle.split()[-1] for cle in self.taches if cle.startswith("disque ") and not cle.startswith("disque chaud")]
            self.etats["disques"] = (("attention", f"Disques en bon état, mais {', '.join(l + ':' for l in pleins)} presque plein.")
                                     if pleins else ("ok", pluriel(f"{len(disques)} disque(s) en bon état.", len(disques))))
        if not any(d["vie"] is not None for d in disques):
            libelle(self.cadre_disques, "Pour voir l'usure et la température des SSD, lance LibreHardwareMonitor.", 9, GRIS).pack(fill="x", pady=(4, 0))
        # La place sur chaque lecteur
        lecteurs = getattr(self, "lecteurs", [])
        if lecteurs:
            petit_titre(self.cadre_disques, "Place sur chaque lecteur").pack(fill="x", pady=(12, 2))
        for lettre, total, libre in lecteurs:
            ligne = tk.Frame(self.cadre_disques, bg=CARTE)
            ligne.pack(fill="x", pady=2)
            libelle(ligne, f"{lettre}:", 10, TEXTE, True, width=3).pack(side="left")
            libelle(ligne, f"{libre / 1e9:,.0f} Go libres sur {total / 1e9:,.0f}".replace(",", " "), 9, GRIS, width=26).pack(side="right")
            rempli = 1 - libre / total if total else 0
            j = Jauge(ligne, CYAN, epaisseur=6)
            j.pack(side="left", fill="x", expand=True, padx=8)
            j.regler(rempli, ROUGE if rempli > 0.97 else (ORANGE if rempli >= int(REGLAGES.get("alerte_disque", 90)) / 100 else CYAN))
        self.dessiner_bilan()
    self.en_fond(etat_disques, ensuite)


# ---------- diagnostic ----------

@methode
def lancer_diagnostic(self):
    infos = {"icone": self.icone is not None, "serveur": getattr(self, "serveur", None) is not None,
             "dernier_appel_local": getattr(self, "dernier_appel_local", 0)}

    def ensuite(points):
        if isinstance(points, Exception):
            points = [("attention", "Diagnostic impossible", str(points))]
        self.points_diagnostic = points
        vider(self.cadre_diagnostic)
        for niveau, titre, detail in points:
            ligne_etat(self.cadre_diagnostic, niveau, titre, detail)
        soucis = [p for p in points if p[0] in ("alerte", "attention")]
        if soucis:
            noms = ", ".join(p[1].lower() for p in soucis)
            self.etats["diagnostic"] = ("attention", pluriel(f"{len(soucis)} point(s) à voir : {noms}.", len(soucis)))
            self.tache("diagnostic", "attention", "Un élément de la boîte à outils n'est pas branché", noms.capitalize() + ".",
                       "Diagnostic", lambda: self.aller_a("Santé du PC", "Diagnostic"), prevenir=False)
        else:
            self.etats["diagnostic"] = ("ok", "Capteurs, micro, liaison téléphone et Stream Deck : tout est branché.")
            self.tache_finie("diagnostic")
        self.dessiner_bilan()
    self.en_fond(lambda: diagnostic(infos), ensuite)


@methode
def copier_diagnostic(self):
    lignes = [f"Boîte à outils v{VERSION} · Python {sys.version.split()[0]} · {time.strftime('%Y-%m-%d %H:%M')}",
              f"Fichier : {Path(__file__).resolve()}"]
    symboles = {"ok": "[OK]", "attention": "[!]", "alerte": "[!!]", "info": "[i]"}
    lignes += [f"{symboles.get(n, '[?]')} {titre} : {detail}" for n, titre, detail in self.points_diagnostic]
    self.racine.clipboard_clear()
    self.racine.clipboard_append("\n".join(lignes))
    self.toast("Rapport copié : tu peux le coller où tu veux (Ctrl+V)")


# =============================================================
#  🎮 JEUX  -  lancer une partie, temps de jeu, résumé des sessions
# =============================================================

def quand_lisible(instant):
    """« aujourd'hui 21:04 », « hier 18:30 », « 12 nov. 20:15 »."""
    t, maintenant = time.localtime(instant), time.localtime()
    heure = f"{t.tm_hour:02d}:{t.tm_min:02d}"
    if (t.tm_year, t.tm_yday) == (maintenant.tm_year, maintenant.tm_yday):
        return f"aujourd'hui {heure}"
    hier = time.localtime(time.time() - 86400)
    if (t.tm_year, t.tm_yday) == (hier.tm_year, hier.tm_yday):
        return f"hier {heure}"
    return f"{t.tm_mday} {MOIS[t.tm_mon - 1]} {heure}"


@methode
def page_jeux(self, cadre):
    onglets = self.sous_pages["Jeux"] = Onglets(cadre)
    onglets.pack(fill="both", expand=True)
    self.temps = charger_temps()
    self.sessions = charger_json(FICHIER_SESSIONS, [])
    if not isinstance(self.sessions, list):
        self.sessions = []
    self.jeux = {}
    self.partie = None   # la partie en cours : {"jeu", "debut", "cpu_max", "gpu_max"}
    self.jeu_actuel, self.debut_jeu, self.dernier_releve = None, None, time.time()

    # ----- Jouer -----
    jouer = onglets.ajouter("Jouer", carte=False)
    jouer.columnconfigure(0, weight=1)
    jouer.rowconfigure(0, weight=1)
    liste = Carte(jouer, padx=16, pady=14)
    liste.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
    tete = tk.Frame(liste, bg=CARTE)
    tete.pack(fill="x", pady=(0, 6))
    libelle(tete, "Tes jeux", 13, TEXTE, True).pack(side="left")
    Bouton(tete, "🔄 Actualiser", self.charger_jeux, petit=True).pack(side="right")
    self.liste_jeux = ttk.Treeview(liste, columns=("jeu", "temps", "quand"), show="headings", height=12, selectmode="browse")
    for col, titre, larg, ancre in (("jeu", "Jeu", 250, "w"), ("temps", "Temps de jeu", 110, "e"), ("quand", "Dernière partie", 130, "e")):
        self.liste_jeux.heading(col, text=titre, anchor=ancre)
        self.liste_jeux.column(col, width=larg, anchor=ancre)
    self.liste_jeux.pack(fill="both", expand=True)
    self.liste_jeux.bind("<Double-1>", lambda e: self.lancer())
    self.info_liste_jeux = libelle(liste, "", 9, GRIS)
    self.info_liste_jeux.pack(fill="x", pady=(6, 0))

    session = Carte(jouer, padx=16, pady=14)
    session.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
    session.exterieur.config(width=320)
    session.exterieur.grid_propagate(False)
    session.exterieur.pack_propagate(False)
    libelle(session, "Session gaming", 13, TEXTE, True).pack(fill="x")
    libelle(session, "Choisis un jeu à gauche, puis lance la session. Voilà ce qui se passe :", 9, GRIS, largeur=280).pack(fill="x", pady=(2, 8))
    self.cadre_etapes = tk.Frame(session, bg=CARTE)
    self.cadre_etapes.pack(fill="x")
    self.btn_lancer = Bouton(session, "🚀 Lancer la session", self.lancer, "succes")
    self.btn_lancer.pack(fill="x", pady=(12, 4))
    self.btn_fini = Bouton(session, "✅ J'ai fini de jouer", self.fin_session)
    self.btn_fini.pack(fill="x")
    self.btn_fini.activer(False)
    self.info_gaming = libelle(session, "", 9, GRIS, largeur=280)
    self.info_gaming.pack(fill="x", pady=(10, 0))
    self.dessiner_etapes()

    # ----- Temps de jeu -----
    temps = onglets.ajouter("Temps de jeu")
    self.info_jeu_actuel = libelle(temps, "", 12, GRIS, True)
    self.info_jeu_actuel.pack(fill="x")
    self.info_totaux = libelle(temps, "", 10, TEXTE)
    self.info_totaux.pack(fill="x", pady=(2, 8))
    petit_titre(temps, "Par jeu, sur les 7 derniers jours").pack(fill="x")
    self.graph_jeux = tk.Canvas(temps, bg=CARTE, height=170, highlightthickness=0)
    self.graph_jeux.pack(fill="x", pady=(4, 10))
    petit_titre(temps, "Par jour").pack(fill="x")
    self.graph_jours = tk.Canvas(temps, bg=CARTE, height=130, highlightthickness=0)
    self.graph_jours.pack(fill="x", pady=4)
    libelle(temps, "Le temps est compté tant que la boîte à outils tourne (même rangée près de l'horloge).", 9, GRIS).pack(fill="x", pady=(6, 0))
    self.graph_jeux.bind("<Configure>", lambda e: self.afficher_temps())
    self.graph_jours.bind("<Configure>", lambda e: self.afficher_temps())

    # ----- Sessions -----
    sessions = onglets.ajouter("Sessions")
    libelle(sessions, "Tes dernières parties", 13, TEXTE, True).pack(fill="x")
    libelle(sessions, "À la fin de chaque partie, la boîte à outils note sa durée et les températures les plus hautes atteintes. "
                      "Pratique pour repérer un jeu qui fait trop chauffer le PC.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 8))
    self.liste_sessions = ttk.Treeview(sessions, columns=("jeu", "quand", "duree", "cpu", "gpu"), show="headings", height=14, selectmode="none")
    for col, titre, larg, ancre in (("jeu", "Jeu", 260, "w"), ("quand", "Quand", 160, "w"), ("duree", "Durée", 100, "e"),
                                    ("cpu", "Processeur max", 130, "e"), ("gpu", "Carte graphique max", 150, "e")):
        self.liste_sessions.heading(col, text=titre, anchor=ancre)
        self.liste_sessions.column(col, width=larg, anchor=ancre)
    self.liste_sessions.pack(fill="both", expand=True)
    self.info_sessions = libelle(sessions, "", 9, GRIS)
    self.info_sessions.pack(fill="x", pady=(6, 0))
    self.afficher_sessions()
    self.charger_jeux()
    self.racine.after(1500, self.suivre_jeu)


@methode
def dessiner_etapes(self):
    """La liste « voilà ce qui se passe » de la session gaming, d'après tes réglages."""
    vider(self.cadre_etapes)
    etapes = []
    if APPS_A_FERMER:
        etapes.append("Ferme " + ", ".join(a.replace(".exe", "") for a in APPS_A_FERMER))
    if REGLAGES["mode_performances"]:
        etapes.append("Passe Windows en mode Performances")
    etapes += ["Ouvre Discord", "Lance le jeu avec Steam", "À la fin : remet tout comme avant"]
    for texte in etapes:
        ligne = tk.Frame(self.cadre_etapes, bg=CARTE)
        ligne.pack(fill="x", pady=2)
        tk.Label(ligne, text="✓", bg=CARTE, fg=VERT, font=police(10, True)).pack(side="left", padx=(0, 8))
        libelle(ligne, texte, 10, largeur=250).pack(side="left", fill="x")
    lien = tk.Label(self.cadre_etapes, text="Changer ces réglages  ›", bg=CARTE, fg=ACCENT, font=police(9), cursor="hand2", anchor="w")
    lien.pack(fill="x", pady=(6, 0))
    lien.bind("<Button-1>", lambda e: self.aller_a("Réglages", "Jeux"))


@methode
def charger_jeux(self):
    def ensuite(jeux):
        if isinstance(jeux, Exception) or not jeux:
            jeux = JEUX_SECOURS
            self.info_liste_jeux.config(text="Steam introuvable : voici une liste de secours. Double-clic sur un jeu pour le lancer.")
        else:
            self.info_liste_jeux.config(text=f"{len(jeux)} jeux Steam installés. Double-clic sur un jeu pour lancer la session.")
        self.jeux = jeux
        self.remplir_liste_jeux()
    self.en_fond(jeux_steam, ensuite)


@methode
def remplir_liste_jeux(self):
    totaux, derniers = {}, {}
    for jour, parties in self.temps.items():
        for jeu, sec in parties.items():
            totaux[jeu] = totaux.get(jeu, 0) + sec
            derniers[jeu] = max(derniers.get(jeu, ""), jour)
    choix = self.liste_jeux.selection()
    self.liste_jeux.delete(*self.liste_jeux.get_children())
    for nom in self.jeux:
        jour = derniers.get(nom)
        quand = time.strftime("%d/%m/%Y", time.strptime(jour, "%Y-%m-%d")) if jour else "jamais"
        self.liste_jeux.insert("", "end", iid=nom, values=(nom, duree_lisible(totaux[nom]) if nom in totaux else "-", quand))
    garder = choix[0] if choix and choix[0] in self.jeux else next(iter(self.jeux), None)
    if garder:
        self.liste_jeux.selection_set(garder)


@methode
def lancer(self):
    choix = self.liste_jeux.selection()
    if not choix or self.session:
        return
    jeu = choix[0]
    self.btn_lancer.activer(False)
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
            self.btn_lancer.activer(True)
            return
        self.session = session
        fermees = ", ".join(session["applis"]) or "aucune"
        perf = "mode Performances activé" if session["plan"] else "plan d'alimentation inchangé"
        self.info_gaming.config(text=f"🚀 {jeu} se lance. Applis fermées : {fermees}. {perf.capitalize()}. Bon jeu !", fg=TEXTE)
        self.btn_fini.activer(True)
    self.en_fond(travail, ensuite)


@methode
def fin_session(self):
    if not self.session:
        return
    for exe, chemin in self.session["applis"].items():
        if Path(chemin).exists():
            subprocess.Popen([chemin])
    if self.session["plan"]:
        activer_plan(self.session["plan"])   # on remet ton plan d'avant
    self.session = None
    try:
        self.info_gaming.config(text="👍 Tout est remis comme avant (applis et plan d'alimentation).", fg=GRIS)
        self.btn_fini.activer(False)
        self.btn_lancer.activer(True)
    except tk.TclError:
        pass   # la fenêtre est en train de se fermer


# ---------- suivi : quel jeu tourne ? ----------

@methode
def suivre_jeu(self):
    """Toutes les 20 s : quel jeu tourne ? On ajoute le temps écoulé à ce jeu, et on repère le début et la fin des parties."""
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
            ecrire_json(FICHIER_TEMPS, self.temps)
        if jeu != self.jeu_actuel:
            if self.jeu_actuel:
                self.fin_partie()
            self.jeu_actuel, self.debut_jeu = jeu, maintenant
            if jeu:
                self.debut_partie(jeu)
        self.afficher_temps()
        self.racine.after(20 * 1000, self.suivre_jeu)
    self.en_fond(lambda: jeu_en_cours(getattr(self, "jeux", {})), ensuite)


@methode
def debut_partie(self, jeu):
    self.partie = {"jeu": jeu, "debut": time.time(), "cpu_max": 0, "gpu_max": 0}
    profil = REGLAGES.get("profil_en_jeu", "Jeu")
    if REGLAGES.get("auto_profil") and profil in REGLAGES.get("profils", {}) and REGLAGES.get("profil_actif") != profil:
        self.profil_avant_jeu = REGLAGES.get("profil_actif")
        self.activer_profil(profil, ouvrir=False)
        self.notifier(f"{jeu} détecté : profil {profil} activé", "Je remettrai le profil d'avant à la fin de la partie.", "info",
                      cle="auto profil", silence=60)


@methode
def noter_partie(self, cpu, gpu):
    """Appelée à chaque relevé : retient les températures max de la partie en cours."""
    partie = getattr(self, "partie", None)
    if partie:
        partie["cpu_max"] = max(partie["cpu_max"], cpu or 0)
        partie["gpu_max"] = max(partie["gpu_max"], gpu or 0)


@methode
def fin_partie(self):
    partie, self.partie = self.partie, None
    avant = getattr(self, "profil_avant_jeu", None)
    if REGLAGES.get("auto_profil") and avant and avant in REGLAGES.get("profils", {}):
        self.activer_profil(avant, ouvrir=False)
    self.profil_avant_jeu = None
    if not partie:
        return
    duree = time.time() - partie["debut"]
    if duree < 120:   # moins de 2 minutes : ce n'était pas vraiment une partie
        return
    self.sessions.append({"jeu": partie["jeu"], "debut": partie["debut"], "duree": duree,
                          "cpu_max": partie["cpu_max"], "gpu_max": partie["gpu_max"]})
    self.sessions = self.sessions[-200:]
    ecrire_json(FICHIER_SESSIONS, self.sessions)
    self.afficher_sessions()
    self.remplir_liste_jeux()
    temps = " · ".join(f"{nom} max {v:.0f} °C" for nom, v in (("processeur", partie["cpu_max"]), ("carte graphique", partie["gpu_max"])) if v)
    self.notifier(f"Partie terminée : {partie['jeu']}", f"{duree_lisible(duree)} de jeu" + (f" · {temps}" if temps else ""),
                  "info", lambda: self.aller_a("Jeux", "Sessions"), cle=f"partie {partie['debut']}")


@methode
def afficher_sessions(self):
    self.liste_sessions.delete(*self.liste_sessions.get_children())
    for s in reversed(self.sessions[-60:]):
        self.liste_sessions.insert("", "end", values=(
            s.get("jeu", "?"), quand_lisible(s.get("debut", 0)), duree_lisible(s.get("duree", 0)),
            f"{s['cpu_max']:.0f} °C" if s.get("cpu_max") else "-", f"{s['gpu_max']:.0f} °C" if s.get("gpu_max") else "-"))
    if self.sessions:
        total = sum(s.get("duree", 0) for s in self.sessions)
        self.info_sessions.config(text=pluriel(f"{len(self.sessions)} partie(s) enregistrée(s), {duree_lisible(total)} au total.", len(self.sessions)))
    else:
        self.info_sessions.config(text="Aucune partie enregistrée pour l'instant. Lance un jeu : le résumé arrivera ici à la fin.")


@methode
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
    # Et sur l'accueil
    if self.jeu_actuel:
        self.dash_jeu.config(text=f"{self.jeu_actuel} · {duree_lisible(time.time() - self.debut_jeu)}"[:26], fg=CYAN)
    else:
        self.dash_jeu.config(text="Aucun jeu", fg=GRIS)
    self.dash_semaine.config(text=f"7 derniers jours : {duree_lisible(sum(par_jour))}")
    self.dash_top.config(text=f"Le plus joué : {max(par_jeu, key=par_jeu.get)}" if par_jeu else "")

    # Graphique 1 : une barre horizontale par jeu (les 5 plus joués)
    c = self.graph_jeux
    c.delete("all")
    larg = max(c.winfo_width(), 300)
    classement = sorted(par_jeu.items(), key=lambda j: j[1], reverse=True)[:5]
    if not classement:
        c.create_text(larg / 2, 85, text="Pas encore de partie enregistrée cette semaine. Lance un jeu !", fill=GRIS, font=police(10))
    plus_long = max([sec for _, sec in classement], default=1)
    couleurs = [CYAN, ROSE, VIOLET, VERT, ORANGE]
    for i, (jeu, sec) in enumerate(classement):
        y = 12 + i * 31
        c.create_text(4, y + 9, text=jeu[:24], fill=TEXTE, anchor="w", font=police(10))
        fin = 200 + (larg - 300) * sec / plus_long
        c.create_line(200, y + 9, larg - 100, y + 9, fill="#1c1c2c", width=12, capstyle="round")
        c.create_line(200, y + 9, max(fin, 201), y + 9, fill=couleurs[i], width=12, capstyle="round")
        c.create_text(larg - 84, y + 9, text=duree_lisible(sec), fill=GRIS, anchor="w", font=police(9))

    # Graphique 2 : une colonne par jour
    c = self.graph_jours
    c.delete("all")
    larg = max(c.winfo_width(), 300)
    plus_long = max(par_jour + [3600])
    pas = (larg - 20) / 7
    noms_jours = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
    for i, (jour, sec) in enumerate(zip(jours, par_jour)):
        x = 10 + i * pas
        haut = (130 - 46) * sec / plus_long
        c.create_rectangle(x + pas * 0.25, 106 - max(haut, 2), x + pas * 0.75, 106, fill=VIOLET if i < 6 else CYAN, width=0)
        c.create_text(x + pas / 2, 119, text=noms_jours[time.strptime(jour, "%Y-%m-%d").tm_wday], fill=GRIS, font=police(9))
        if sec >= 60:
            c.create_text(x + pas / 2, 97 - haut, text=duree_lisible(sec), fill=TEXTE, font=police(8))


# =============================================================
#  🎛 PROFILS  -  Jeu / Travail / Silence en un clic
# =============================================================

@methode
def page_profils(self, cadre):
    self.cadre_profils = tk.Frame(cadre, bg=FOND)
    self.cadre_profils.pack(fill="x")
    auto = Carte(cadre, padx=18, pady=12)
    auto.pack(fill="x", pady=10)
    ligne = tk.Frame(auto, bg=CARTE)
    ligne.pack(fill="x")
    libelle(ligne, "Changement automatique", 11, TEXTE, True).pack(side="left")
    Bouton(ligne, "Régler  ›", lambda: self.aller_a("Réglages", "Jeux"), petit=True).pack(side="right")
    self.info_auto_profil = libelle(auto, "", 9, GRIS, largeur=820)
    self.info_auto_profil.pack(fill="x", pady=(2, 0))

    edition = Carte(cadre, padx=18, pady=14)
    edition.pack(fill="both", expand=True)
    libelle(edition, "Modifier les profils", 12, TEXTE, True).pack(fill="x")
    libelle(edition, "Sépare les applis par des virgules. « Fermer » : le nom du programme (Steam.exe). « Ouvrir » : un chemin, "
                     "un lien (steam://...) ou simplement Discord. Les profils ne touchent jamais au volume de ton casque.",
            9, GRIS, largeur=820).pack(fill="x", pady=(2, 8))
    grille = tk.Frame(edition, bg=CARTE)
    grille.pack(fill="x")
    self.champs_profils = {}
    grille.columnconfigure(2, weight=2)   # les deux dernières colonnes se partagent la place qui reste
    grille.columnconfigure(3, weight=3)
    for col, titre in enumerate(["", "Alimentation", "Applis à fermer", "Applis à ouvrir"]):
        petit_titre(grille, titre).grid(row=0, column=col, sticky="w", padx=4, pady=(0, 4))
    for rangee, (nom, p) in enumerate(REGLAGES["profils"].items(), start=1):
        libelle(grille, f"{p.get('icone', '')}  {nom}", 10, TEXTE, True).grid(row=rangee, column=0, sticky="w", padx=(4, 12), pady=4)
        plan = ttk.Combobox(grille, values=list(NOMS_PLANS.values()), state="readonly", width=20)
        plan.set(NOMS_PLANS.get(p.get("plan"), "Utilisation normale"))
        plan.grid(row=rangee, column=1, padx=4)
        champs = {"plan": plan}
        for col, cle, larg in ((2, "fermer", 18), (3, "ouvrir", 24)):
            c = champ(grille, larg, valeur=", ".join(p.get(cle) or []))
            c.grid(row=rangee, column=col, padx=4, ipady=4, sticky="ew")
            champs[cle] = c
        self.champs_profils[nom] = champs
    Bouton(edition, "💾 Enregistrer les profils", self.sauver_profils, "principal").pack(anchor="w", pady=(12, 0))
    self.dessiner_profils()


@methode
def dessiner_profils(self):
    vider(self.cadre_profils)
    actif = REGLAGES.get("profil_actif")
    dernier = len(REGLAGES["profils"]) - 1
    for col, (nom, p) in enumerate(REGLAGES["profils"].items()):
        self.cadre_profils.columnconfigure(col, weight=1, uniform="p")
        couleur = [CYAN, VIOLET, ROSE][col % 3]
        c = Carte(self.cadre_profils, padx=18, pady=14, bordure=couleur if nom == actif else BORD)
        c.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 4, 0 if col == dernier else 4))
        haut = tk.Frame(c, bg=CARTE)
        haut.pack(fill="x")
        libelle(haut, f"{p.get('icone', '')}  {nom}", 16, couleur, True).pack(side="left")
        if nom == actif:
            tk.Label(haut, text=espacer("actif"), bg=CARTE, fg=couleur, font=police(8, True)).pack(side="right")
        resume = ["Alimentation : " + NOMS_PLANS.get(p.get("plan"), "inchangée")]
        if p.get("fermer"):
            resume.append("Ferme " + ", ".join(a.replace(".exe", "") for a in p["fermer"]))
        if p.get("ouvrir"):
            resume.append("Ouvre " + ", ".join(a.split("://")[0].capitalize() if "://" in a else Path(a).stem for a in p["ouvrir"]))
        libelle(c, "\n".join(resume), 9, GRIS, largeur=240).pack(fill="x", pady=(6, 10))
        Bouton(c, "✓ Activé" if nom == actif else "Activer", lambda n=nom: self.activer_profil(n),
               "discret" if nom == actif else "principal").pack(anchor="w")
    if REGLAGES.get("auto_profil"):
        self.info_auto_profil.config(text=f"Activé : dès qu'un jeu démarre, le profil {REGLAGES.get('profil_en_jeu', 'Jeu')} se met tout seul "
                                          "(sans ouvrir d'appli), et le profil d'avant revient à la fin de la partie.", fg=VERT)
    else:
        self.info_auto_profil.config(text="Désactivé. Tu peux demander à la boîte à outils de passer toute seule au profil Jeu "
                                          "quand un jeu démarre.", fg=GRIS)
    self.maj_actions_rapides()


@methode
def activer_profil(self, nom, ouvrir=True):
    if nom not in REGLAGES.get("profils", {}):
        return

    def ensuite(fait):
        if isinstance(fait, Exception):
            self.toast(f"Profil {nom} : erreur ({fait})", "alerte")
            return
        self.toast(f"Profil {nom} activé" + (" : " + ", ".join(fait) if fait else ""))
        self.dessiner_profils()
    self.en_fond(lambda: appliquer_profil(nom, ouvrir), ensuite)


@methode
def sauver_profils(self):
    plans = {v: k for k, v in NOMS_PLANS.items()}
    for nom, champs in self.champs_profils.items():
        p = REGLAGES["profils"][nom]
        p["plan"] = plans.get(champs["plan"].get(), "SCHEME_BALANCED")
        p["fermer"] = [a.strip() for a in champs["fermer"].get().split(",") if a.strip()]
        p["ouvrir"] = [a.strip() for a in champs["ouvrir"].get().split(",") if a.strip()]
        p["volume"] = None   # les profils ne règlent plus le volume (demande de Crz)
    enregistrer_reglages()
    self.dessiner_profils()
    self.toast("Profils enregistrés")


# =============================================================
#  🔊 SOUNDBOARD
# =============================================================

@methode
def page_soundboard(self, cadre):
    haut = tk.Frame(cadre, bg=CARTE)
    haut.pack(fill="x")
    libelle(haut, "Tes sons", 13, TEXTE, True).pack(side="left")
    Bouton(haut, "⏹ Tout arrêter", stopper_sons, "danger", petit=True).pack(side="right")
    Bouton(haut, "➕ Ajouter un son", self.ajouter_son, "succes", petit=True).pack(side="right", padx=8)

    sorties = tk.Frame(cadre, bg=CARTE)
    sorties.pack(fill="x", pady=(10, 2))
    libelle(sorties, "Envoyer vers Discord (câble virtuel)", 10, GRIS).grid(row=0, column=0, sticky="w", pady=3)
    libelle(sorties, "Et l'entendre dans", 10, GRIS).grid(row=1, column=0, sticky="w", pady=3)
    self.choix_discord = ttk.Combobox(sorties, state="readonly", width=44)
    self.choix_ecoute = ttk.Combobox(sorties, state="readonly", width=44)
    self.choix_discord.grid(row=0, column=1, padx=10, sticky="w")
    self.choix_ecoute.grid(row=1, column=1, padx=10, sticky="w")
    for c in (self.choix_discord, self.choix_ecoute):
        c.bind("<<ComboboxSelected>>", lambda e: self.sauver_sorties())
    Bouton(sorties, "🔄", self.lister_sorties, petit=True).grid(row=0, column=2)
    self.aide_soundboard = libelle(cadre, "", 9, GRIS, largeur=860)
    self.aide_soundboard.pack(fill="x", pady=(4, 10))
    self.grille_sons = tk.Frame(cadre, bg=CARTE)
    self.grille_sons.pack(fill="both", expand=True)
    libelle(cadre, "Clic : jouer   ·   clic droit : renommer, volume, couleur, supprimer   ·   "
                   "les mêmes sons sont sur le Stream Deck et le téléphone", 9, GRIS).pack(fill="x")
    self.lister_sorties()
    self.dessiner_sons()


@methode
def lister_sorties(self):
    audio = charger_audio()
    if not audio:
        self.aide_soundboard.config(text="Pour commencer, clique sur « Ajouter un son » : je te proposerai d'installer les 2 petites "
                                         "librairies nécessaires.", fg=ORANGE)
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
        self.aide_soundboard.config(text="Pour que Discord entende les sons, il faut un « câble audio virtuel » : installe VB-CABLE "
                                         "(gratuit, vb-audio.com/Cable), puis relance la boîte à outils.", fg=ORANGE)
    else:
        self.aide_soundboard.config(text="✓ Câble virtuel trouvé. Dans Discord : Paramètres > Voix et vidéo > Périphérique d'entrée "
                                         "= « CABLE Output ». Pour ta voix : Windows > Son > ton micro > Propriétés > Écouter > "
                                         "coche « Écouter ce périphérique » et choisis « CABLE Input ».", fg=GRIS)


@methode
def sauver_sorties(self):
    d, e = self.choix_discord.get(), self.choix_ecoute.get()
    REGLAGES["sortie_discord"] = "" if d.startswith("(") else d
    REGLAGES["sortie_ecoute"] = "" if e == "(sortie par défaut)" else (None if e == "(aucune)" else e)
    enregistrer_reglages()


@methode
def dessiner_sons(self):
    vider(self.grille_sons)
    if not REGLAGES["sons"]:
        libelle(self.grille_sons, "Aucun son pour l'instant", 13, GRIS, True).pack(pady=(40, 4))
        libelle(self.grille_sons, "Clique sur « Ajouter un son » et choisis des fichiers .mp3, .wav ou .ogg.", 10, GRIS).pack()
        return
    for i, son in enumerate(REGLAGES["sons"]):
        self.grille_sons.columnconfigure(i % 5, weight=1, uniform="s")
        couleur = son.get("couleur", CYAN)
        pad = tk.Label(self.grille_sons, text=son["nom"], bg=SURFACE, fg=couleur, font=police(12, True), wraplength=140,
                       highlightthickness=2, highlightbackground=couleur, cursor="hand2", height=3)
        pad.grid(row=i // 5, column=i % 5, sticky="nsew", padx=5, pady=5)
        pad.bind("<Button-1>", lambda e, s=son["id"]: threading.Thread(target=jouer_son, args=(s,), daemon=True).start())
        pad.bind("<Enter>", lambda e, w=pad, c=couleur: w.config(bg=melanger(SURFACE, c, 0.2)))
        pad.bind("<Leave>", lambda e, w=pad: w.config(bg=SURFACE))
        pad.bind("<Button-3>", lambda e, s=son: self.menu_son(e, s))


@methode
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


@methode
def menu_son(self, evenement, son):
    from tkinter import simpledialog
    menu = tk.Menu(self.racine, tearoff=0, bg=CARTE, fg=TEXTE, activebackground=ACCENT, activeforeground=FOND)

    def renommer():
        nom = simpledialog.askstring("Renommer", "Nouveau nom :", initialvalue=son["nom"], parent=self.racine)
        if nom:
            son["nom"] = nom[:24]
            enregistrer_reglages()
            self.dessiner_sons()

    def volume():
        v = simpledialog.askinteger("Volume du son", "Volume de ce son (0 à 150 %) :", initialvalue=son.get("volume", 80),
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
    menu.add_command(label="🔉 Volume de ce son", command=volume)
    menu.add_command(label="🎨 Changer la couleur", command=couleur)
    menu.add_separator()
    menu.add_command(label="🗑 Supprimer", command=supprimer_son)
    menu.tk_popup(evenement.x_root, evenement.y_root)


# =============================================================
#  🧹 ENTRETIEN  -  nettoyer, ranger, démarrage de Windows
# =============================================================

def programmes_demarrage():
    """Ce que Windows lance à l'ouverture de ta session : [(nom, commande, activé ?, où)].
    On LIT seulement le registre et le dossier Démarrage : rien n'est modifié."""
    try:
        import winreg
    except ImportError:
        return []
    base = r"Software\Microsoft\Windows\CurrentVersion"

    def valeurs(racine, chemin):
        trouve = {}
        try:
            with winreg.OpenKey(racine, chemin) as cle:
                i = 0
                while True:
                    try:
                        nom, valeur, _ = winreg.EnumValue(cle, i)
                    except OSError:
                        break
                    trouve[nom] = valeur
                    i += 1
        except OSError:
            pass
        return trouve

    def actif(approuves, nom):   # Windows note ici ce que tu as désactivé (1er octet impair = désactivé)
        v = approuves.get(nom)
        return not (isinstance(v, bytes) and v and v[0] % 2 == 1)

    resultat = []
    for racine, run, approuve, ou in (
            (winreg.HKEY_CURRENT_USER, base + r"\Run", base + r"\Explorer\StartupApproved\Run", "ton compte"),
            (winreg.HKEY_LOCAL_MACHINE, base + r"\Run", base + r"\Explorer\StartupApproved\Run", "tout le PC"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
             base + r"\Explorer\StartupApproved\Run32", "tout le PC")):
        approuves = valeurs(racine, approuve)
        for nom, commande in valeurs(racine, run).items():
            resultat.append((nom, str(commande), actif(approuves, nom), ou))
    approuves = valeurs(winreg.HKEY_CURRENT_USER, base + r"\Explorer\StartupApproved\StartupFolder")
    try:
        for f in LANCEUR_DEMARRAGE.parent.iterdir():
            if f.suffix.lower() in (".lnk", ".vbs", ".bat", ".cmd", ".exe", ".url"):
                nom = "Boîte à outils (cette appli)" if f.name == LANCEUR_DEMARRAGE.name else f.stem
                resultat.append((nom, str(f), actif(approuves, f.name), "dossier Démarrage"))
    except OSError:
        pass
    return sorted(resultat, key=lambda r: (not r[2], r[0].lower()))


@methode
def page_entretien(self, cadre):
    onglets = self.sous_pages["Entretien"] = Onglets(cadre)
    onglets.pack(fill="both", expand=True)

    # ----- Nettoyer -----
    nettoyer = onglets.ajouter("Nettoyer")
    libelle(nettoyer, "Faire de la place", 13, TEXTE, True).pack(fill="x")
    libelle(nettoyer, "1. Coche ce que tu veux nettoyer.   2. « Analyser » montre la place que ça libère.   "
                      "3. « Nettoyer » demande confirmation, puis supprime.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 8))
    self.cadre_zones = tk.Frame(nettoyer, bg=CARTE)
    self.cadre_zones.pack(fill="x", pady=4)
    self.construire_zones()
    boutons = tk.Frame(nettoyer, bg=CARTE)
    boutons.pack(fill="x", pady=(8, 0))
    Bouton(boutons, "🔍 Analyser", self.analyser, "principal").pack(side="left", padx=(0, 8))
    self.btn_nettoyer = Bouton(boutons, "🧹 Nettoyer", self.nettoyer, "succes")
    self.btn_nettoyer.pack(side="left")
    self.btn_nettoyer.activer(False)
    self.resultat_nettoyage = libelle(nettoyer, "", 11, VERT, True)
    self.resultat_nettoyage.pack(fill="x", pady=(10, 0))
    self.info_dernier_nettoyage = libelle(nettoyer, "", 9, GRIS)
    self.info_dernier_nettoyage.pack(fill="x")
    self.afficher_dernier_nettoyage()

    # ----- Ranger -----
    ranger_ = onglets.ajouter("Ranger")
    libelle(ranger_, "Ranger un dossier", 13, TEXTE, True).pack(fill="x")
    libelle(ranger_, "Range les fichiers en vrac d'un dossier dans des sous-dossiers par type (Images, Vidéos, Documents...). "
                     "Rien n'est supprimé, et les sous-dossiers existants ne sont pas touchés.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 8))
    self.info_dossier_rangeur = libelle(ranger_, f"Dossier à ranger : {DOSSIER_A_RANGER}", 10, TEXTE)
    self.info_dossier_rangeur.pack(fill="x")
    lien = tk.Label(ranger_, text="Changer de dossier  ›", bg=CARTE, fg=ACCENT, font=police(9), cursor="hand2", anchor="w")
    lien.pack(fill="x")
    lien.bind("<Button-1>", lambda e: self.aller_a("Réglages", "Général"))
    boutons = tk.Frame(ranger_, bg=CARTE)
    boutons.pack(fill="x", pady=10)
    Bouton(boutons, "🔍 Aperçu", self.voir_apercu, "principal").pack(side="left", padx=(0, 8))
    self.btn_ranger = Bouton(boutons, "📂 Ranger", self.lancer_rangement, "succes")
    self.btn_ranger.pack(side="left")
    self.btn_ranger.activer(False)
    self.apercu = libelle(ranger_, "Clique sur Aperçu pour voir ce qui serait rangé (ça ne déplace rien).", 10, GRIS)
    self.apercu.pack(fill="x")
    self.plan = {}

    # ----- Démarrage -----
    demarrage = onglets.ajouter("Démarrage")
    tete = tk.Frame(demarrage, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Ce qui se lance avec Windows", 13, TEXTE, True).pack(side="left")
    Bouton(tete, "🪟 Régler dans Windows", lambda: os.startfile("ms-settings:startupapps"), petit=True).pack(side="right")
    Bouton(tete, "🔄 Actualiser", self.charger_demarrage, petit=True).pack(side="right", padx=8)
    libelle(demarrage, "Plus il y a de programmes au démarrage, plus le PC met de temps à être prêt. Cette liste est en lecture seule : "
                       "pour en désactiver un, utilise le bouton « Régler dans Windows ».", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 8))
    self.liste_demarrage = ttk.Treeview(demarrage, columns=("nom", "etat", "ou"), show="headings", height=13, selectmode="none")
    for col, titre, larg in (("nom", "Programme", 420), ("etat", "État", 130), ("ou", "Pour", 170)):
        self.liste_demarrage.heading(col, text=titre, anchor="w")
        self.liste_demarrage.column(col, width=larg, anchor="w")
    self.liste_demarrage.tag_configure("off", foreground=ETEINT)
    self.liste_demarrage.pack(fill="both", expand=True)
    self.info_demarrage = libelle(demarrage, "", 9, GRIS)
    self.info_demarrage.pack(fill="x", pady=(6, 0))
    onglets.quand_change = lambda nom: nom == "Démarrage" and self.charger_demarrage()


@methode
def afficher_dernier_nettoyage(self):
    dernier = REGLAGES.get("dernier_nettoyage")
    if not dernier:
        self.info_dernier_nettoyage.config(text="Aucun nettoyage fait avec la boîte à outils pour l'instant.")
        return
    try:
        jours = int((time.time() - time.mktime(time.strptime(dernier, "%Y-%m-%d"))) // 86400)
    except ValueError:
        return
    self.info_dernier_nettoyage.config(text="Dernier nettoyage : " + ("aujourd'hui." if jours <= 0 else pluriel(f"il y a {jours} jour(s).", jours)))


@methode
def construire_zones(self):
    """(Re)crée une case à cocher par zone de nettoyage."""
    vider(self.cadre_zones)
    self.zones = zones_nettoyage()
    self.clips = []
    for zone in self.zones:
        ligne = tk.Frame(self.cadre_zones, bg=CARTE)
        ligne.pack(fill="x", pady=2)
        zone["var"] = tk.BooleanVar(value=zone["coche"])
        tk.Checkbutton(ligne, text=zone["nom"], variable=zone["var"], bg=CARTE, fg=TEXTE, selectcolor=CHAMP,
                       activebackground=CARTE, activeforeground=TEXTE, font=police(10), anchor="w",
                       highlightthickness=0, bd=0).pack(side="left")
        zone["taille_lbl"] = tk.Label(ligne, text="", bg=CARTE, fg=ACCENT, font=police(10, True))
        zone["taille_lbl"].pack(side="right")
        zone["taille"] = 0


@methode
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
            texte = taille_lisible(zone["taille"])
            if zone["cle"] == "medal":
                self.clips = clips
                texte = f"{len(clips)} clips · {texte}" if DOSSIER_MEDAL.exists() else "dossier introuvable"
            zone["taille_lbl"].config(text=texte)
        total = sum(z["taille"] for z in self.zones if z["var"].get())
        self.resultat_nettoyage.config(text=f"Les cases cochées libéreraient environ {taille_lisible(total)}.", fg=TEXTE)
        self.btn_nettoyer.activer(True)
    self.en_fond(travail, ensuite)


@methode
def nettoyer(self):
    choisies = [z for z in self.zones if z["var"].get()]
    if not choisies:
        self.resultat_nettoyage.config(text="Coche au moins une case 👆", fg=ORANGE)
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
        self.noter("nettoye", libere, "somme")
        REGLAGES["dernier_nettoyage"] = time.strftime("%Y-%m-%d")
        enregistrer_reglages()
        self.afficher_dernier_nettoyage()
        self.analyser()
        self.racine.after(1500, lambda: self.resultat_nettoyage.config(text=f"✓ {taille_lisible(libere)} libérés !", fg=VERT))
        self.toast(f"{taille_lisible(libere)} libérés")
    self.en_fond(travail, ensuite)


@methode
def voir_apercu(self):
    self.plan = plan_rangement()
    if not DOSSIER_A_RANGER.exists():
        self.apercu.config(text=f"Le dossier {DOSSIER_A_RANGER} n'existe pas. Change-le dans les Réglages.", fg=ORANGE)
        self.btn_ranger.activer(False)
    elif not self.plan:
        self.apercu.config(text="Rien à ranger, c'est déjà propre ✨", fg=VERT)
        self.btn_ranger.activer(False)
    else:
        lignes = [pluriel(f"{cat} : {len(liste)} fichier(s)", len(liste)) for cat, liste in sorted(self.plan.items())]
        self.apercu.config(text="Voilà ce qui serait rangé :\n\n" + "\n".join(lignes), fg=TEXTE)
        self.btn_ranger.activer(True)


@methode
def lancer_rangement(self):
    total = sum(len(l) for l in self.plan.values())
    if total and messagebox.askyesno("Ranger", f"Ranger ces {total} fichiers dans des sous-dossiers de\n{DOSSIER_A_RANGER} ?"):
        n = ranger(self.plan)
        self.apercu.config(text=pluriel(f"✓ {n} fichier(s) rangé(s) !", n), fg=VERT)
        self.btn_ranger.activer(False)


@methode
def charger_demarrage(self):
    def ensuite(programmes):
        if isinstance(programmes, Exception):
            programmes = []
        self.liste_demarrage.delete(*self.liste_demarrage.get_children())
        for nom, commande, actif, ou in programmes:
            self.liste_demarrage.insert("", "end", values=(nom, "Activé" if actif else "Désactivé", ou), tags=() if actif else ("off",))
        actifs = sum(1 for p in programmes if p[2])
        if programmes:
            self.info_demarrage.config(text=pluriel(f"{actifs} programme(s) activé(s)", actifs) + f" au démarrage sur {len(programmes)}. "
                                            "Certaines applis (Discord, Steam...) ont aussi leur propre réglage « lancer au démarrage ».")
        else:
            self.info_demarrage.config(text="Aucun programme trouvé (ou lecture impossible).")
    self.en_fond(programmes_demarrage, ensuite)


# =============================================================
#  📊 RAPPORT DE LA SEMAINE
# =============================================================

@methode
def preparer_stats(self):
    self.stats = charger_json(FICHIER_STATS, {})
    self.stats_a_sauver = False
    self.racine.after(60 * 1000, self.sauver_stats)


@methode
def noter(self, cle, valeur, mode="max"):
    """Ajoute une statistique du jour (mode "max" = on garde la plus grande, "somme" = on additionne)."""
    if valeur is None:
        return
    jour = self.stats.setdefault(time.strftime("%Y-%m-%d"), {})
    jour[cle] = max(jour.get(cle, 0), valeur) if mode == "max" else jour.get(cle, 0) + valeur
    self.stats_a_sauver = True


@methode
def sauver_stats(self):
    if self.stats_a_sauver:
        ecrire_json(FICHIER_STATS, self.stats)
        self.stats_a_sauver = False
    try:   # garde-fou : si plantage.txt enfle (plus de 2 Mo), on arrête d'y écrire
        if _FICHIER_PLANTAGE and (DOSSIER_APPLI / "plantage.txt").stat().st_size > 2_000_000:
            import faulthandler
            faulthandler.disable()
    except OSError:
        pass
    self.racine.after(60 * 1000, self.sauver_stats)


@methode
def page_rapport(self, cadre):
    haut = tk.Frame(cadre, bg=CARTE)
    haut.pack(fill="x")
    self.titre_rapport = libelle(haut, "", 13, TEXTE, True)
    self.titre_rapport.pack(side="left")
    self.choix_semaine = -1
    self.boutons_semaine = {}
    for valeur, nom in ((0, "Cette semaine"), (-1, "Semaine dernière")):
        b = tk.Label(haut, text=nom, bg=CARTE, fg=GRIS, font=police(9, True), padx=10, pady=4, cursor="hand2")
        b.pack(side="right", padx=(6, 0))
        b.bind("<Button-1>", lambda e, v=valeur: self.choisir_semaine(v))
        self.boutons_semaine[valeur] = b
    self.cadre_rapport = tk.Frame(cadre, bg=CARTE)
    self.cadre_rapport.pack(fill="both", expand=True, pady=(10, 0))
    self.choisir_semaine(-1 if any(bilan_semaine(self.stats, charger_temps(), -1).values()) else 0)
    # Le lundi (ou au 1er lancement de la semaine), on te le signale
    semaine = time.strftime("%G-%V")
    if REGLAGES.get("dernier_rapport") != semaine:
        REGLAGES["dernier_rapport"] = semaine
        enregistrer_reglages()
        b = bilan_semaine(self.stats, charger_temps(), -1)
        if b["jeu_total"] or b["cpu_max"] or b["gpu_max"]:
            self.racine.after(6000, lambda: self.notifier("Ton rapport de la semaine est prêt",
                                                          f"{duree_lisible(b['jeu_total'])} de jeu la semaine dernière.", "info",
                                                          lambda: self.aller_a("Rapport"), cle="rapport " + semaine))


@methode
def choisir_semaine(self, decalage):
    self.choix_semaine = decalage
    for v, b in self.boutons_semaine.items():
        b.config(bg=melanger(CARTE, ACCENT, 0.18) if v == decalage else CARTE, fg=ACCENT if v == decalage else GRIS)
    self.afficher_rapport()


@methode
def afficher_rapport(self):
    vider(self.cadre_rapport)
    decalage = self.choix_semaine
    temps = charger_temps()
    b = bilan_semaine(self.stats, temps, decalage)
    avant = bilan_semaine(self.stats, temps, decalage - 1)
    debut = time.strftime("%d/%m", time.strptime(b["jours"][0], "%Y-%m-%d"))
    fin = time.strftime("%d/%m", time.strptime(b["jours"][-1], "%Y-%m-%d"))
    self.titre_rapport.config(text=f"Semaine du {debut} au {fin}")

    grille = tk.Frame(self.cadre_rapport, bg=CARTE)
    grille.pack(fill="x")
    ecart = b["jeu_total"] - avant["jeu_total"]
    tendance = (f"{'+' if ecart >= 0 else '−'}{duree_lisible(abs(ecart))} vs semaine d'avant" if avant["jeu_total"] else "")
    cases = [
        ("Temps de jeu", duree_lisible(b["jeu_total"]), tendance, CYAN),
        ("Processeur au plus chaud", f"{b['cpu_max']:.0f}°" if b["cpu_max"] else "--",
         "a dépassé ton alerte" if b["cpu_max"] >= ALERTE_CPU else "rien à signaler", ROUGE if b["cpu_max"] >= ALERTE_CPU else CYAN),
        ("Carte graphique au plus chaud", f"{b['gpu_max']:.0f}°" if b["gpu_max"] else "--",
         "a dépassé ton alerte" if b["gpu_max"] >= ALERTE_GPU else "rien à signaler", ROUGE if b["gpu_max"] >= ALERTE_GPU else ROSE),
        ("Place libérée", taille_lisible(b["nettoye"]), "avec le nettoyeur", VERT),
        ("Mises à jour", str(int(b["maj"])), "applis mises à jour", VIOLET),
    ]
    for col, (titre, valeur, detail, couleur) in enumerate(cases):
        grille.columnconfigure(col, weight=1, uniform="r")
        c = tk.Frame(grille, bg=SURFACE, highlightthickness=1, highlightbackground=BORD, padx=12, pady=10)
        c.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 4, 4))
        libelle(c, titre.upper(), 7, GRIS, True, SURFACE, largeur=140).pack(fill="x")
        libelle(c, valeur, 20, couleur, True, SURFACE).pack(fill="x")
        libelle(c, detail, 9, GRIS, fond=SURFACE, largeur=150).pack(fill="x")

    bas = tk.Frame(self.cadre_rapport, bg=CARTE)
    bas.pack(fill="both", expand=True, pady=(14, 0))
    bas.columnconfigure(0, weight=1, uniform="b")
    bas.columnconfigure(1, weight=1, uniform="b")
    gauche = tk.Frame(bas, bg=CARTE)
    gauche.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    petit_titre(gauche, "Tes jeux les plus joués").pack(fill="x", pady=(0, 6))
    if not b["top"]:
        libelle(gauche, "Pas de partie cette semaine-là.", 10, GRIS).pack(fill="x")
    for rang, (jeu, sec) in enumerate(b["top"], start=1):
        ligne = tk.Frame(gauche, bg=CARTE)
        ligne.pack(fill="x", pady=3)
        tk.Label(ligne, text=str(rang), bg=melanger(CARTE, [CYAN, ROSE, VIOLET][rang - 1], 0.25), fg=TEXTE, font=police(10, True), width=3).pack(side="left")
        libelle(ligne, jeu, 11, TEXTE, True).pack(side="left", padx=10)
        libelle(ligne, duree_lisible(sec), 10, GRIS).pack(side="right")
    semaine = set(b["jours"])
    parties = [s for s in getattr(self, "sessions", []) if time.strftime("%Y-%m-%d", time.localtime(s.get("debut", 0))) in semaine]
    if parties:
        plus_longue = max(parties, key=lambda s: s.get("duree", 0))
        libelle(gauche, f"{len(parties)} partie{'s' if len(parties) > 1 else ''} · la plus longue : {plus_longue['jeu']} ({duree_lisible(plus_longue['duree'])})",
                9, GRIS, largeur=380).pack(fill="x", pady=(8, 0))
    droite = tk.Frame(bas, bg=CARTE)
    droite.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
    petit_titre(droite, "Temps de jeu par jour").pack(fill="x", pady=(0, 6))
    toile = tk.Canvas(droite, bg=CARTE, height=150, highlightthickness=0)
    toile.pack(fill="x")
    par_jour = [sum(temps.get(j, {}).values()) for j in b["jours"]]

    def dessiner(_evt=None):
        toile.delete("all")
        larg, plus_long = max(toile.winfo_width(), 280), max(par_jour + [3600])
        pas = (larg - 10) / 7
        for i, sec in enumerate(par_jour):
            x, haut = 5 + i * pas, 96 * sec / plus_long
            toile.create_rectangle(x + pas * 0.22, 122 - max(haut, 2), x + pas * 0.78, 122, fill=VIOLET if sec else "#1c1c2c", width=0)
            toile.create_text(x + pas / 2, 136, text=["lun", "mar", "mer", "jeu", "ven", "sam", "dim"][i], fill=GRIS, font=police(9))
            if sec >= 60:
                toile.create_text(x + pas / 2, 113 - haut, text=duree_lisible(sec), fill=TEXTE, font=police(8))
    toile.bind("<Configure>", dessiner)


# =============================================================
#  🔐 COFFRE-FORT et 🔔 ALERTE PRIX
# =============================================================

@methode
def page_coffre(self, cadre):
    self.coffre = Coffre(cadre, self.racine)


@methode
def page_prix(self, cadre):
    libelle(cadre, "Surveiller un prix", 13, TEXTE, True).pack(fill="x")
    libelle(cadre, "1. Colle le lien de la page du produit.   2. Écris le prix que tu vises.   3. Laisse la boîte à outils ouverte "
                   "(ou près de l'horloge) : elle vérifie régulièrement et te prévient.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 12))
    petit_titre(cadre, "Lien de la page du produit").pack(fill="x")
    self.champ_url = champ(cadre, 60, valeur=REGLAGES.get("prix_url", ""))
    self.champ_url.pack(fill="x", ipady=6, pady=(2, 10))
    petit_titre(cadre, "Me prévenir quand le prix passe sous (en euros)").pack(fill="x")
    self.champ_cible = champ(cadre, 12, valeur=REGLAGES.get("prix_cible", ""))
    self.champ_cible.pack(anchor="w", ipady=6, pady=(2, 12))
    self.btn_surveiller = Bouton(cadre, "🔔 Surveiller ce prix", self.basculer_surveillance, "principal")
    self.btn_surveiller.pack(anchor="w")
    self.info_prix = libelle(cadre, "", 11, TEXTE, largeur=860)
    self.info_prix.pack(fill="x", pady=(14, 0))
    libelle(cadre, "Certains sites (Amazon surtout) bloquent ce genre de lecture automatique : si aucun prix n'est trouvé, "
                   "essaie le lien d'une autre boutique.", 9, GRIS, largeur=860).pack(fill="x", pady=(6, 0))
    self.surveillance = False
    self.prochaine_verif = None


@methode
def basculer_surveillance(self):
    if self.surveillance:
        self.surveillance = False
        if self.prochaine_verif:
            self.racine.after_cancel(self.prochaine_verif)   # annule la vérif prévue
            self.prochaine_verif = None
        self.btn_surveiller.changer("🔔 Surveiller ce prix", "principal")
        self.info_prix.config(text="Surveillance arrêtée.", fg=GRIS)
        return
    try:
        self.cible = float(self.champ_cible.get().replace(",", ".").replace("€", "").strip())
    except ValueError:
        self.info_prix.config(text="Le prix visé doit être un nombre (par exemple 799).", fg=ORANGE)
        return
    self.url = self.champ_url.get().strip()
    if not self.url.startswith("http"):
        self.info_prix.config(text="Colle un lien complet, qui commence par http.", fg=ORANGE)
        return
    REGLAGES["prix_url"], REGLAGES["prix_cible"] = self.url, self.champ_cible.get().strip()
    enregistrer_reglages()
    self.surveillance = True
    self.btn_surveiller.changer("⏹ Arrêter la surveillance", "danger")
    self.verifier_prix()


@methode
def verifier_prix(self):
    if not self.surveillance:
        return
    self.info_prix.config(text="Vérification du prix...", fg=GRIS)

    def ensuite(prix):
        if not self.surveillance:
            return
        heure = time.strftime("%H:%M")
        if isinstance(prix, Exception):
            self.info_prix.config(text=f"[{heure}] Page illisible : {prix}", fg=ORANGE)
        elif prix is None:
            self.info_prix.config(text=f"[{heure}] Pas de prix trouvé (le site bloque peut-être les lectures automatiques).", fg=ORANGE)
        elif prix <= self.cible:
            self.info_prix.config(text=f"[{heure}] 🎉 {prix:.2f} € : prix atteint !", fg=VERT)
            self.basculer_surveillance()
            self.info_prix.config(text=f"[{heure}] 🎉 {prix:.2f} € : prix atteint !", fg=VERT)
            self.racine.bell()
            self.notifier("Prix atteint 🎉", f"{prix:.2f} € (tu visais {self.cible:.2f} €)", "ok", lambda: self.aller_a("Alerte prix"),
                          cle=f"prix {time.time()}")
            return
        else:
            self.info_prix.config(text=f"[{heure}] {prix:.2f} € pour l'instant (tu vises {self.cible:.2f} €). "
                                       f"Prochaine vérification dans {MINUTES_ENTRE_PRIX} min.", fg=TEXTE)
        self.prochaine_verif = self.racine.after(MINUTES_ENTRE_PRIX * 60 * 1000, self.verifier_prix)
    self.en_fond(lambda: trouver_prix(self.url), ensuite)


# =============================================================
#  📱 TÉLÉPHONE ET STREAM DECK
# =============================================================

@methode
def page_telephone(self, cadre):
    enregistrer_reglages()   # pour garder le même code PIN
    onglets = self.sous_pages["Téléphone"] = Onglets(cadre)
    onglets.pack(fill="both", expand=True)

    # ----- Téléphone -----
    tel = onglets.ajouter("Téléphone")
    if self.serveur is None:
        libelle(tel, f"⚠ Le port {PORT_SERVEUR} est déjà utilisé : la boîte à outils est peut-être déjà ouverte ailleurs.",
                10, ROUGE).pack(fill="x", pady=(0, 8))
    libelle(tel, "Ton PC dans ta poche", 13, TEXTE, True).pack(fill="x")
    libelle(tel, "Depuis le navigateur de ton téléphone : températures en direct, soundboard, profils, musique, micro, "
                 "veille, verrouillage, extinction.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 10))
    for numero, titre, valeur, couleur in (
            ("1", "Connecte ton téléphone au Wi-Fi de la maison, puis ouvre cette adresse", f"http://{ip_locale()}:{PORT_SERVEUR}", CYAN),
            ("2", "Entre ton code PIN", " ".join(REGLAGES["pin_telephone"]), ROSE)):
        bloc = tk.Frame(tel, bg=SURFACE, highlightthickness=1, highlightbackground=BORD, padx=14, pady=10)
        bloc.pack(fill="x", pady=4)
        tk.Label(bloc, text=numero, bg=melanger(SURFACE, couleur, 0.25), fg=TEXTE, font=police(12, True), width=3).pack(side="left", padx=(0, 14))
        textes = tk.Frame(bloc, bg=SURFACE)
        textes.pack(side="left", fill="x", expand=True)
        libelle(textes, titre, 9, GRIS, fond=SURFACE).pack(fill="x")
        libelle(textes, valeur, 20, couleur, True, SURFACE).pack(fill="x")
    bloc = tk.Frame(tel, bg=SURFACE, highlightthickness=1, highlightbackground=BORD, padx=14, pady=10)
    bloc.pack(fill="x", pady=4)
    tk.Label(bloc, text="3", bg=melanger(SURFACE, VIOLET, 0.25), fg=TEXTE, font=police(12, True), width=3).pack(side="left", padx=(0, 14))
    libelle(bloc, "Dans le menu du navigateur (⋮ ou Partager), choisis « Ajouter à l'écran d'accueil » : tu auras une vraie icône.",
            10, TEXTE, fond=SURFACE, largeur=760).pack(side="left", fill="x")
    libelle(tel, "Si Windows demande l'autorisation du pare-feu au premier lancement, coche « Réseaux privés ». "
                 "Le code PIN empêche les autres appareils du Wi-Fi de piloter ton PC.", 9, GRIS, largeur=860).pack(fill="x", pady=(8, 0))

    # ----- Stream Deck -----
    sd = onglets.ajouter("Stream Deck")
    tete = tk.Frame(sd, bg=CARTE)
    tete.pack(fill="x")
    libelle(tete, "Plugin Stream Deck", 13, TEXTE, True).pack(side="left")
    Bouton(tete, "⬇ Installer ou réinstaller le plugin", self.installer_plugin, "principal", petit=True).pack(side="right")
    self.info_plugin = libelle(sd, "", 10, GRIS, largeur=860)
    self.info_plugin.pack(fill="x", pady=(2, 10))
    petit_titre(sd, "Les 5 touches disponibles").pack(fill="x", pady=(0, 4))
    for nom, detail, couleur in (("Capteur", "Affiche une mesure en direct : température ou charge du processeur, de la carte graphique, mémoire, connexion.", CYAN),
                                 ("Micro", "Coupe ou réactive ton micro. La touche devient rouge quand il est coupé.", ROSE),
                                 ("Profil", "Active un profil (Jeu, Travail, Silence).", VIOLET),
                                 ("Son", "Joue un son de ton soundboard, dans Discord aussi.", VERT),
                                 ("Musique", "Lecture / pause, morceau suivant ou précédent, volume de la musique.", ORANGE)):
        ligne = tk.Frame(sd, bg=CARTE)
        ligne.pack(fill="x", pady=3)
        tk.Label(ligne, text=nom, bg=melanger(CARTE, couleur, 0.18), fg=couleur, font=police(10, True), width=10, pady=3).pack(side="left", padx=(0, 12))
        libelle(ligne, detail, 10, TEXTE, largeur=720).pack(side="left", fill="x")
    libelle(sd, "Dans le logiciel Stream Deck, ces touches sont dans la catégorie « Capteurs de Crz » (colonne de droite) : "
                "glisse-les sur ton Stream Deck. Le profil « Perfs » est livré avec le plugin.", 9, GRIS, largeur=860).pack(fill="x", pady=(10, 0))

    # ----- Allumer à distance -----
    wol = onglets.ajouter("Allumer à distance")
    libelle(wol, "Allumer le PC depuis ton téléphone (Wake-on-LAN)", 13, TEXTE, True).pack(fill="x")
    libelle(wol, "Un PC éteint ne peut pas répondre lui-même : c'est une appli « Wake On LAN » sur ton téléphone qui lui envoie "
                 "un signal de réveil par le câble réseau. Il faut l'adresse de ta carte réseau (adresse MAC) :", 9, GRIS,
            largeur=860).pack(fill="x", pady=(2, 8))
    self.info_mac = libelle(wol, "Recherche de ta carte réseau...", 12, TEXTE, True)
    self.info_mac.pack(fill="x", pady=(0, 10))
    petit_titre(wol, "À régler une seule fois").pack(fill="x", pady=(0, 4))
    for etape in ("BIOS de la carte mère MSI (touche Suppr au démarrage) : Settings > Advanced > Wake Up Event Setup > "
                  "« Resume By PCI-E Device » sur Enabled, et « ErP Ready » sur Disabled.",
                  "Windows : Gestionnaire de périphériques > Cartes réseau > ta carte > Gestion de l'alimentation : coche "
                  "« Autoriser ce périphérique à sortir l'ordinateur du mode veille » et « paquet magique ».",
                  "Windows : désactive le « démarrage rapide » (Options d'alimentation > Choisir l'action des boutons d'alimentation).",
                  "Téléphone : installe une appli « Wake On LAN », ajoute ton PC avec l'adresse MAC ci-dessus. "
                  "Le PC doit être branché en câble Ethernet (pas en Wi-Fi)."):
        ligne = tk.Frame(wol, bg=CARTE)
        ligne.pack(fill="x", pady=3)
        tk.Label(ligne, text="•", bg=CARTE, fg=ACCENT, font=police(11, True)).pack(side="left", anchor="n", padx=(0, 8))
        libelle(ligne, etape, 10, TEXTE, largeur=820).pack(side="left", fill="x")

    def ensuite(cartes):
        if isinstance(cartes, Exception) or not cartes:
            self.info_mac.config(text="Adresse MAC introuvable (tape « getmac » dans PowerShell pour la voir).", fg=GRIS)
        else:
            self.info_mac.config(text="   ·   ".join(f"{nom[:44]} : {mac}" for nom, mac in cartes), fg=VERT)
    self.en_fond(adresses_mac, ensuite)
    onglets.quand_change = lambda nom: nom == "Stream Deck" and self.afficher_plugin()
    self.racine.after(12000, self.afficher_plugin)


@methode
def afficher_plugin(self):
    version = None
    try:
        version = json.loads((DOSSIER_PLUGIN / "manifest.json").read_text(encoding="utf-8")).get("Version")
    except (OSError, ValueError):
        pass
    if version and time.time() - getattr(self, "dernier_appel_local", 0) < 20:
        self.info_plugin.config(text=f"✓ Installé (version {version}) et connecté à la boîte à outils.", fg=VERT)
    elif version:
        self.info_plugin.config(text=f"Installé (version {version}), mais il ne demande rien en ce moment : le logiciel Stream Deck est peut-être fermé.", fg=ORANGE)
    else:
        self.info_plugin.config(text="Pas encore installé sur ce PC. Clique sur le bouton, puis accepte l'installation dans le logiciel Stream Deck.", fg=GRIS)


@methode
def installer_plugin(self):
    self.info_plugin.config(text="Téléchargement du plugin...", fg=GRIS)

    def travail():
        fichier = DOSSIER_APPLI / "com.crz.capteurs.streamDeckPlugin"
        DOSSIER_APPLI.mkdir(parents=True, exist_ok=True)
        fichier.write_bytes(telecharger("com.crz.capteurs.streamDeckPlugin"))
        os.startfile(fichier)   # le logiciel Stream Deck propose de l'installer
        return True

    def ensuite(res):
        if isinstance(res, Exception):
            self.info_plugin.config(text=f"Téléchargement impossible ({res}). Vérifie ta connexion et réessaie.", fg=ORANGE)
        else:
            self.info_plugin.config(text="Téléchargé : le logiciel Stream Deck s'ouvre pour te proposer l'installation.", fg=VERT)
    self.en_fond(travail, ensuite)


# =============================================================
#  ⚙ RÉGLAGES
# =============================================================

@methode
def page_reglages(self, cadre):
    onglets = self.sous_pages["Réglages"] = Onglets(cadre)
    onglets.pack(fill="both", expand=True)
    self.champs_reglages = {}   # clé du réglage -> (sorte, widget)

    def ligne(parent, cle, sorte, titre, aide="", choix=None):
        """Une ligne de réglage : le titre et son explication à gauche, la commande à droite."""
        l = tk.Frame(parent, bg=CARTE)
        l.pack(fill="x", pady=6)
        valeur = REGLAGES.get(cle, REGLAGES_DEFAUT.get(cle))
        if sorte == "oui_non":
            w = Interrupteur(l, valeur)
            w.pack(side="right", padx=(12, 0))
        elif sorte == "choix":
            w = ttk.Combobox(l, values=choix, state="readonly", width=34)
            w.set(valeur if valeur in choix else choix[0])
            w.pack(side="right", padx=(12, 0))
        else:
            if sorte == "dossier":
                def choisir():
                    choisi = filedialog.askdirectory(initialdir=w.get() or str(Path.home()))
                    if choisi:
                        w.delete(0, "end")
                        w.insert(0, str(Path(choisi)))
                Bouton(l, "📁", choisir, petit=True).pack(side="right", padx=(6, 0))
            w = champ(l, {"nombre": 8, "dossier": 34, "liste": 34}[sorte],
                      valeur=", ".join(valeur) if isinstance(valeur, list) else valeur)
            w.pack(side="right", padx=(12, 0), ipady=4)
        textes = tk.Frame(l, bg=CARTE)
        textes.pack(side="left", fill="x", expand=True)
        libelle(textes, titre, 10, TEXTE, True).pack(fill="x")
        if aide:
            libelle(textes, aide, 9, GRIS, largeur=470).pack(fill="x")
        self.champs_reglages[cle] = (sorte, w)

    def barre_enregistrer(parent):
        bas = tk.Frame(parent, bg=CARTE)
        bas.pack(fill="x", side="bottom", pady=(10, 0))
        Bouton(bas, "💾 Enregistrer", self.sauver_reglages, "principal").pack(side="left")
        libelle(bas, "Les changements ne sont pris en compte qu'après « Enregistrer ».", 9, GRIS).pack(side="left", padx=12)

    general = onglets.ajouter("Général")
    barre_enregistrer(general)
    ligne(general, "fermer_vers_icone", "oui_non", "La croix range la fenêtre près de l'horloge",
          "La boîte à outils continue de tourner (temps de jeu, alertes, Stream Deck). Pour vraiment quitter : clic droit sur l'icône.")
    ligne(general, "demarrage_windows", "oui_non", "Lancer au démarrage de Windows", "Elle démarre discrètement, rangée près de l'horloge.")
    ligne(general, "maj_auto", "oui_non", "Installer les mises à jour toute seule", "Vérifié au lancement. Sinon, un bouton apparaît en haut quand une version sort.")
    ligne(general, "accent", "choix", "Couleur des boutons", "Appliquée au prochain lancement.", list(COULEURS_ACCENT))
    ligne(general, "dossier_a_ranger", "dossier", "Dossier à ranger", "Utilisé par Entretien > Ranger.")
    ligne(general, "dossier_medal", "dossier", "Dossier des clips Medal", "Utilisé par Entretien > Nettoyer.")
    ligne(general, "jours_clips", "nombre", "Garder les clips Medal pendant (jours)", "Les clips plus vieux sont proposés au nettoyage.")
    ligne(general, "verrou_minutes", "nombre", "Verrouiller le coffre-fort après (minutes)", "Sans rien toucher, le coffre se referme tout seul.")
    ligne(general, "minutes_entre_prix", "nombre", "Alerte prix : vérifier toutes les (minutes)")

    alertes = onglets.ajouter("Alertes")
    barre_enregistrer(alertes)
    ligne(alertes, "notifications", "oui_non", "Notifications Windows",
          "Une bulle près de l'horloge quand la fenêtre n'est pas devant toi : surchauffe, ventilateur arrêté, disque plein, fin de partie.")
    ligne(alertes, "alerte_cpu", "nombre", "Alerte température du processeur (°C)", "Ton i5-13600KF supporte jusqu'à 100 °C. Conseillé : 90.")
    ligne(alertes, "alerte_gpu", "nombre", "Alerte température de la carte graphique (°C)", "Conseillé pour ta RTX 4070 Ti : 83.")
    ligne(alertes, "alerte_disque", "nombre", "Signaler un disque rempli à plus de (%)", "Un SSD trop plein ralentit. Conseillé : 90.")
    libelle(alertes, "Une alerte ne part que si le souci dure une dizaine de secondes, et jamais deux fois de suite pour la même chose.",
            9, GRIS, largeur=860).pack(fill="x", pady=(10, 0))

    jeux = onglets.ajouter("Jeux")
    barre_enregistrer(jeux)
    petit_titre(jeux, "Session gaming (bouton « Lancer la session »)").pack(fill="x", pady=(0, 2))
    ligne(jeux, "mode_performances", "oui_non", "Passer en mode Performances pendant la session", "Le plan d'alimentation d'avant revient à la fin.")
    ligne(jeux, "apps_a_fermer", "liste", "Applis à fermer pour jouer", "Séparées par des virgules. Elles sont relancées à la fin.")
    petit_titre(jeux, "Profil automatique").pack(fill="x", pady=(14, 2))
    ligne(jeux, "auto_profil", "oui_non", "Changer de profil tout seul quand un jeu démarre",
          "Le profil choisi s'active (sans ouvrir d'appli), et le profil d'avant revient quand tu quittes le jeu.")
    ligne(jeux, "profil_en_jeu", "choix", "Profil à activer en jeu", "", list(REGLAGES.get("profils", {})) or ["Jeu"])

    micro_ = onglets.ajouter("Micro")
    barre_enregistrer(micro_)
    libelle(micro_, "Quel micro le bouton Micro doit-il couper ?", 12, TEXTE, True).pack(fill="x")
    libelle(micro_, "Par défaut, c'est le micro principal de Windows. Si tu passes par Voicemeeter, choisis le même micro que le "
                    "« Périphérique d'entrée » de Discord.", 9, GRIS, largeur=860).pack(fill="x", pady=(2, 10))
    self.choix_micro = ttk.Combobox(micro_, state="readonly", width=56, values=["Micro par défaut de Windows"])
    self.choix_micro.set(REGLAGES.get("micro_nom") or "Micro par défaut de Windows")
    self.choix_micro.pack(anchor="w")
    libelle(micro_, "Bon à savoir : ton casque HyperX ignore le « muet » de Windows, donc la boîte à outils coupe le micro en mettant "
                    "son volume à zéro, puis remet le volume d'avant. Elle ne touche jamais au son que tu entends dans le casque.",
            9, GRIS, largeur=860).pack(fill="x", pady=(12, 0))

    def remplir_micros(micros):
        if not isinstance(micros, Exception) and micros:
            self.choix_micro.config(values=["Micro par défaut de Windows"] + [nom for nom, _ in micros])
    self.en_fond(lister_micros, remplir_micros)

    apropos = onglets.ajouter("À propos")
    libelle(apropos, f"Boîte à outils de Crz · version {VERSION}", 14, TEXTE, True).pack(fill="x")
    libelle(apropos, "Faite en Python avec tkinter, la librairie de fenêtres livrée avec Python. Tout le code est dans un seul "
                     "fichier, commenté en français : ouvre-le pour voir comment c'est fait.", 10, GRIS, largeur=860).pack(fill="x", pady=(4, 12))
    boutons = tk.Frame(apropos, bg=CARTE)
    boutons.pack(fill="x")
    Bouton(boutons, "✨ Quoi de neuf", self.quoi_de_neuf).pack(side="left", padx=(0, 8))
    Bouton(boutons, "⬇ Chercher une mise à jour", lambda: self.verifier_maj_appli(a_la_main=True)).pack(side="left", padx=(0, 8))
    Bouton(boutons, "🩺 Diagnostic", lambda: self.aller_a("Santé du PC", "Diagnostic")).pack(side="left", padx=(0, 8))
    Bouton(boutons, "📁 Ouvrir le dossier des données", self.ouvrir_dossier_appli).pack(side="left")
    petit_titre(apropos, "Où sont rangées tes données").pack(fill="x", pady=(18, 4))
    for nom, chemin in (("Réglages, statistiques, journal", DOSSIER_APPLI), ("Coffre-fort (chiffré)", FICHIER_COFFRE.parent),
                        ("Ce programme", Path(__file__).resolve())):
        l = tk.Frame(apropos, bg=CARTE)
        l.pack(fill="x", pady=2)
        libelle(l, nom, 10, TEXTE, width=30).pack(side="left")
        libelle(l, str(chemin), 10, GRIS).pack(side="left")
    petit_titre(apropos, "Raccourcis").pack(fill="x", pady=(18, 4))
    libelle(apropos, "Ctrl+K : recherche rapide   ·   Échap : fermer un panneau   ·   double-clic sur la mini-fenêtre : rouvrir la boîte à outils",
            10, GRIS).pack(fill="x")


@methode
def sauver_reglages(self):
    nouveaux = {}
    limites = {"alerte_cpu": (50, 105), "alerte_gpu": (50, 100), "alerte_disque": (50, 99)}
    for cle, (sorte, w) in self.champs_reglages.items():
        if sorte == "oui_non":
            nouveaux[cle] = w.get()
        elif sorte == "choix":
            nouveaux[cle] = w.get()
        elif sorte == "liste":
            nouveaux[cle] = [a.strip() for a in w.get().split(",") if a.strip()]
        elif sorte == "dossier":
            nouveaux[cle] = w.get().strip()
        else:
            valeur = w.get().strip()
            mini, maxi = limites.get(cle, (1, 100000))
            if not valeur.isdigit() or not mini <= int(valeur) <= maxi:
                self.toast(f"« {valeur} » n'est pas valable ici (attendu : un nombre entre {mini} et {maxi})", "alerte")
                w.focus_set()
                return
            nouveaux[cle] = int(valeur)
    micro_choisi = self.choix_micro.get()
    nouveaux["micro_nom"] = "" if micro_choisi.startswith("Micro par défaut") else micro_choisi
    try:
        if nouveaux["demarrage_windows"] != REGLAGES["demarrage_windows"] or nouveaux["demarrage_windows"]:
            regler_demarrage(nouveaux["demarrage_windows"])
    except OSError as e:
        self.toast(f"Lancement au démarrage impossible à régler : {e}", "alerte")
        return
    if nouveaux["fermer_vers_icone"] and not REGLAGES["fermer_vers_icone"]:
        self.creer_icone()
    changement_micro = nouveaux["micro_nom"] != REGLAGES.get("micro_nom", "")
    changement_accent = nouveaux["accent"] != REGLAGES.get("accent", "Cyan")
    REGLAGES.update(nouveaux)
    enregistrer_reglages()
    if changement_micro:
        SON["verifie"] = 0   # le fil du son reprendra le nouveau micro au prochain relevé
    # On met à jour ce qui est affiché dans les autres pages
    self.construire_zones()
    self.btn_nettoyer.activer(False)
    self.info_dossier_rangeur.config(text=f"Dossier à ranger : {DOSSIER_A_RANGER}")
    self.dessiner_etapes()
    self.dessiner_profils()
    self.dessiner_graphique()
    self.toast("Réglages enregistrés" + (" · la nouvelle couleur sera là au prochain lancement" if changement_accent else ""))


# =============================================================
#  🔐 COFFRE-FORT  -  l'affichage
#  (le chiffrement lui-même est plus haut : chiffrer, dechiffrer...)
# =============================================================

class Coffre:
    """La page du coffre-fort. Deux écrans : verrouillé (on tape le mot de passe maître) ou ouvert (la liste)."""

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

    def dire(self, texte, couleur=GRIS):
        """Écrit un message dans la ligne d'information en bas du coffre."""
        if getattr(self, "info", None) is not None and self.info.winfo_exists():
            self.info.config(text=texte, fg=couleur)

    # ---------- ÉCRAN VERROUILLÉ ----------

    def ecran_verrouille(self):
        vider(self.cadre)
        self.mdp_maitre = None
        self.entrees = []
        self.info = None
        premiere_fois = not FICHIER_COFFRE.exists()

        boite = tk.Frame(self.cadre, bg=CARTE)
        boite.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(boite, text="🔐", bg=CARTE, fg=TEXTE, font=police(30)).pack()
        libelle(boite, "Crée ton mot de passe maître" if premiere_fois else "Coffre verrouillé", 14, TEXTE, True).pack(pady=(0, 2))
        libelle(boite, "C'est le seul mot de passe à retenir : il ouvre tous les autres." if premiere_fois
                else "Tape ton mot de passe maître pour voir tes mots de passe.", 9, GRIS).pack(pady=(0, 10))

        self.champ_maitre = champ(boite, 30, cache=True)
        self.champ_maitre.pack(ipady=6, pady=3)
        self.champ_maitre.bind("<Return>", lambda e: self.deverrouiller())
        self.champ_confirm = None
        if premiere_fois:
            libelle(boite, "Écris-le une deuxième fois :", 9, GRIS).pack(pady=(6, 0))
            self.champ_confirm = champ(boite, 30, cache=True)
            self.champ_confirm.pack(ipady=6, pady=3)
            self.champ_confirm.bind("<Return>", lambda e: self.deverrouiller())
            tk.Label(boite, text="Si tu l'oublies, personne ne pourra ouvrir le coffre.\n"
                                 "Choisis une phrase longue que tu retiens facilement (10 caractères minimum).",
                     bg=CARTE, fg=ORANGE, font=police(9), justify="center").pack(pady=6)

        self.info_verrou = tk.Label(boite, text="", bg=CARTE, fg=ROUGE, font=police(10))
        self.info_verrou.pack(pady=3)
        Bouton(boite, "Créer le coffre" if premiere_fois else "Déverrouiller", self.deverrouiller, "principal").pack(pady=(2, 0))
        libelle(boite, f"Le coffre se referme tout seul après {VERROU_MINUTES} min sans rien toucher, "
                       "et dès que la fenêtre est cachée.", 8, ETEINT).pack(pady=(14, 0))

    def deverrouiller(self):
        if AESGCM is None and not charger_crypto():
            if messagebox.askyesno("Coffre-fort", "Il manque la librairie « cryptography » pour chiffrer.\n\n"
                                                  "L'installer maintenant ? (environ 30 secondes)"):
                self.info_verrou.config(text="Installation...", fg=GRIS)
                self.racine.update()
                if installer_crypto() and charger_crypto():
                    self.info_verrou.config(text="Installé", fg=VERT)
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
        fenetre = getattr(self, "fenetre", None)   # ferme la fenêtre d'édition restée ouverte
        if fenetre is not None and fenetre.winfo_exists():
            fenetre.destroy()
        self.ecran_verrouille()

    # ---------- COFFRE OUVERT ----------

    def ecran_principal(self):
        vider(self.cadre)
        haut = tk.Frame(self.cadre, bg=CARTE)
        haut.pack(fill="x", pady=(0, 10))
        libelle(haut, "Chercher", 9, GRIS).pack(side="left")
        self.recherche = tk.StringVar()
        self.recherche.trace_add("write", lambda *a: self.rafraichir())
        zone = champ(haut, 26)
        zone.config(textvariable=self.recherche)
        zone.pack(side="left", ipady=5, padx=8)
        self.compte = libelle(haut, "", 9, GRIS)
        self.compte.pack(side="left", padx=6)
        Bouton(haut, "Verrouiller", self.verrouiller, "danger", petit=True).pack(side="right")

        self.liste = ttk.Treeview(self.cadre, columns=("site", "identifiant", "note"), show="headings", height=8)
        for col, titre, larg in [("site", "Site ou appli", 220), ("identifiant", "Identifiant", 260), ("note", "Note", 260)]:
            self.liste.heading(col, text=titre, anchor="w")
            self.liste.column(col, width=larg, anchor="w")
        self.liste.pack(fill="both", expand=True)
        self.liste.bind("<Double-1>", lambda e: self.copier("mdp"))

        bas = tk.Frame(self.cadre, bg=CARTE)
        bas.pack(fill="x", pady=(10, 0))
        Bouton(bas, "+ Ajouter", lambda: self.fenetre_edition(None), "succes").pack(side="left", padx=(0, 6))
        Bouton(bas, "Copier le mot de passe", lambda: self.copier("mdp"), "principal").pack(side="left", padx=(0, 6))
        Bouton(bas, "Copier l'identifiant", lambda: self.copier("identifiant")).pack(side="left", padx=(0, 6))
        Bouton(bas, "Modifier", self.modifier).pack(side="left", padx=(0, 6))
        Bouton(bas, "Supprimer", self.supprimer).pack(side="right")
        self.info = libelle(self.cadre, "", 9, GRIS)
        self.info.pack(fill="x", pady=(8, 0))
        self.rafraichir()
        self.dire("Astuce : double-clic sur une ligne pour copier son mot de passe." if self.entrees
                  else "Ton coffre est vide. Clique sur « + Ajouter » pour ranger ton premier mot de passe.")

    def rafraichir(self):
        """Réaffiche la liste en tenant compte de la recherche."""
        self.liste.delete(*self.liste.get_children())
        filtre = sans_accents(self.recherche.get())
        montres = 0
        for i, e in sorted(enumerate(self.entrees), key=lambda x: x[1]["site"].lower()):
            if filtre in sans_accents(e["site"]) or filtre in sans_accents(e["identifiant"]) or filtre in sans_accents(e.get("note", "")):
                self.liste.insert("", "end", iid=str(i), values=(e["site"], e["identifiant"], e.get("note", "")))
                montres += 1
        total = len(self.entrees)
        if filtre:
            self.compte.config(text=f"{montres} sur {total}")
        else:
            self.compte.config(text=f"{total} mot{'s' if total > 1 else ''} de passe")

    def selection(self):
        choix = self.liste.selection()
        if not choix:
            self.dire("Sélectionne d'abord une ligne dans la liste.", ORANGE)
            return None
        return int(choix[0])

    def enregistrer(self):
        sauvegarder_coffre(self.entrees, self.mdp_maitre)
        self.rafraichir()

    def copier(self, quoi):
        i = self.selection()
        if i is None:
            return
        self.racine.clipboard_clear()
        self.racine.clipboard_append(self.entrees[i][quoi])
        if quoi == "mdp":
            self.dire(f"Mot de passe de « {self.entrees[i]['site']} » copié. Il sera effacé du presse-papier dans "
                      f"{EFFACER_PRESSE_PAPIER} s.", VERT)
            if self.minuteur_presse_papier:
                self.racine.after_cancel(self.minuteur_presse_papier)
            self.minuteur_presse_papier = self.racine.after(EFFACER_PRESSE_PAPIER * 1000, self.effacer_presse_papier)
        else:
            self.dire("Identifiant copié.", VERT)

    def effacer_presse_papier(self):
        self.minuteur_presse_papier = None
        self.racine.clipboard_clear()
        self.racine.clipboard_append("")
        if self.mdp_maitre:
            self.dire("Presse-papier effacé.")

    def supprimer(self):
        i = self.selection()
        if i is None:
            return
        if messagebox.askyesno("Supprimer", f"Supprimer « {self.entrees[i]['site']} » du coffre ?\n\nC'est définitif."):
            del self.entrees[i]
            self.enregistrer()
            self.dire("Supprimé.")

    def modifier(self):
        i = self.selection()
        if i is not None:
            self.fenetre_edition(i)

    def fenetre_edition(self, index):
        """Petite fenêtre pour ajouter (index=None) ou modifier une entrée."""
        e = self.entrees[index] if index is not None else {"site": "", "identifiant": "", "mdp": "", "note": ""}
        self.fenetre = f = tk.Toplevel(self.racine, bg=CARTE, padx=22, pady=18)
        f.title("Modifier" if index is not None else "Ajouter un mot de passe")
        f.transient(self.racine)
        f.resizable(False, False)
        f.grab_set()   # on ne peut pas cliquer ailleurs tant qu'elle est ouverte

        champs = {}
        for ligne, (cle, titre) in enumerate([("site", "Site ou appli"), ("identifiant", "Identifiant ou e-mail"),
                                              ("mdp", "Mot de passe"), ("note", "Note (facultatif)")]):
            libelle(f, titre, 10, GRIS).grid(row=ligne, column=0, sticky="w", pady=6)
            c = champ(f, 30, cache=(cle == "mdp"), valeur=e.get(cle, ""))
            c.grid(row=ligne, column=1, ipady=5, padx=10)
            champs[cle] = c

        def basculer_affichage():
            cache = not champs["mdp"].cget("show")
            champs["mdp"].config(show="•" if cache else "")
            oeil.changer("Afficher" if cache else "Cacher")

        def generer():
            champs["mdp"].delete(0, "end")
            champs["mdp"].insert(0, generer_mdp())
            champs["mdp"].config(show="")
            oeil.changer("Cacher")

        outils = tk.Frame(f, bg=CARTE)
        outils.grid(row=2, column=2, sticky="w")
        oeil = Bouton(outils, "Afficher", basculer_affichage, petit=True)
        oeil.pack(side="left", padx=(0, 6))
        Bouton(outils, "Générer", generer, petit=True).pack(side="left")
        libelle(f, "« Générer » invente un mot de passe solide de 20 caractères.", 9, GRIS).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))
        erreur = libelle(f, "", 9, ROUGE)
        erreur.grid(row=5, column=0, columnspan=3, sticky="w")

        def valider(_evt=None):
            nouveau = {cle: c.get().strip() for cle, c in champs.items()}
            nouveau["mdp"] = champs["mdp"].get()   # on ne retire pas les espaces d'un mdp
            if not nouveau["site"] or not nouveau["mdp"]:
                erreur.config(text="Il faut au moins un site et un mot de passe.")
                return
            if index is None:
                self.entrees.append(nouveau)
            else:
                self.entrees[index] = nouveau
            self.enregistrer()
            self.dire(f"« {nouveau['site']} » enregistré (chiffré).", VERT)
            f.destroy()

        bas = tk.Frame(f, bg=CARTE)
        bas.grid(row=6, column=0, columnspan=3, sticky="e", pady=(12, 0))
        Bouton(bas, "Annuler", f.destroy).pack(side="left", padx=(0, 8))
        Bouton(bas, "Enregistrer", valider, "succes").pack(side="left")
        f.bind("<Return>", valider)
        f.bind("<Escape>", lambda e: f.destroy())
        champs["site"].focus_set()


# =============================================================
#  📡 LE PETIT SERVEUR
#  Il répond au téléphone (avec le PIN) et au Stream Deck (sans PIN,
#  parce qu'il est sur le PC lui-même). Il tourne dans son propre fil :
#  il ne touche jamais à l'affichage, il dépose ses demandes dans la file.
# =============================================================

class ServeurLocal(http.server.BaseHTTPRequestHandler):
    app = None   # la boîte à outils, remplie au démarrage

    def log_message(self, *args):   # pas de messages dans la console
        pass

    def local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def autorise(self):
        """Le PC lui-même (Stream Deck) n'a pas besoin du PIN, le téléphone oui."""
        return self.local() or self.headers.get("X-Pin") == REGLAGES["pin_telephone"]

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
            if self.local():
                self.app.dernier_appel_local = time.time()   # le Stream Deck vient de passer : il est bien relié
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
        elif quoi == "fenetre" and valeur in ("montrer", "rien") and self.local():
            if valeur == "montrer":
                self.app.file_icone.put("ouvrir")   # une 2e boîte à outils a été lancée : on montre la 1re
            self.repondre(200, {"ok": True})
        elif quoi == "pc" and valeur in ("veille", "verrouiller", "eteindre", "redemarrer"):
            self.repondre(200, {"ok": True})
            action_pc(valeur)
        else:
            self.repondre(400, {"erreur": "action inconnue"})


@methode
def demarrer_serveur(self):
    ServeurLocal.app = self
    self.dernier_appel_local = 0
    try:
        self.serveur = http.server.ThreadingHTTPServer(("0.0.0.0", PORT_SERVEUR), ServeurLocal)
    except OSError:
        self.serveur = None   # port déjà pris (boîte à outils déjà ouverte ?)
        return
    self.serveur.daemon_threads = True
    threading.Thread(target=self.serveur.serve_forever, daemon=True, name="serveur").start()


@methode
def etat_pour_api(self):
    """Ce que le téléphone et le Stream Deck reçoivent quand ils demandent « comment va le PC ? »."""
    m = getattr(self, "dernieres_mesures", {}) or {}
    return {
        "version": VERSION,
        "cpu_temp": m.get("cpu_temp"), "cpu_usage": m.get("cpu_usage"),
        "gpu": m.get("gpu"), "ram": m.get("ram"), "reseau": getattr(self, "derniere_vitesse", None),
        "jeu": getattr(self, "jeu_actuel", None), "profil": REGLAGES.get("profil_actif"),
        "musique": getattr(self, "titre_musique", None), "micro_coupe": getattr(self, "micro_coupe", None),
        "sons": [{"id": s["id"], "nom": s["nom"], "couleur": s.get("couleur", CYAN)} for s in REGLAGES["sons"]],
        "profils": list(REGLAGES["profils"]),
    }


# =============================================================
#  ▶️ LE DÉMARRAGE
#  Tout ce qui est au-dessus ne fait que DÉFINIR des outils.
#  C'est ici que le programme commence vraiment.
# =============================================================

def deja_ouverte():
    """True si une boîte à outils tourne déjà (dans ce cas on lui demande de montrer sa fenêtre)."""
    try:
        action = "rien" if "--cache" in sys.argv else "montrer"
        requete = urllib.request.Request(f"http://127.0.0.1:{PORT_SERVEUR}/api/fenetre/{action}", method="POST")
        urllib.request.urlopen(requete, timeout=2)
        return True
    except urllib.error.HTTPError:
        return True    # elle répond (version plus ancienne) : elle tourne déjà
    except (OSError, ValueError):
        return False   # personne ne répond : on démarre normalement


def preparer_reglages():
    """Charge les réglages et remet d'aplomb ce qui vient des anciennes versions."""
    global ACCENT
    charger_reglages()
    for profil in REGLAGES["profils"].values():   # les profils ne touchent plus au son du casque
        profil["volume"] = None
    if REGLAGES.get("profil_en_jeu") not in REGLAGES["profils"]:
        REGLAGES["profil_en_jeu"] = next(iter(REGLAGES["profils"]), "")
    ACCENT = COULEURS_ACCENT.get(REGLAGES.get("accent"), CYAN)   # la couleur des boutons choisie dans Réglages
    if REGLAGES.get("demarrage_windows"):   # garde le lancement au démarrage à jour si le fichier a bougé
        try:
            regler_demarrage(True)
        except OSError:
            pass


def revenir_en_arriere(erreur):
    """FILET DE SÉCURITÉ. Si cette version n'arrive pas à démarrer, on remet la précédente
    (la mise à jour en garde toujours une copie) et on la relance. Renvoie True si c'est fait."""
    ici = Path(__file__).resolve()
    secours = DOSSIER_APPLI / (ici.name + ".ancienne")
    try:
        ancienne = re.search(r'^VERSION = "([^"]+)"', secours.read_text(encoding="utf-8"), re.M)
        if not ancienne or ancienne.group(1) == VERSION:
            return False   # pas de copie de secours différente : rien à remettre
        shutil.copy2(ici, DOSSIER_APPLI / (ici.name + ".ratee"))   # on garde la version fautive pour comprendre
        shutil.copy2(secours, ici)
        # On coupe les mises à jour automatiques, sinon l'ancienne version réinstallerait aussitôt la fautive
        reglages = charger_json(FICHIER_REGLAGES, {})
        reglages["maj_auto"] = False
        reglages["retour_arriere"] = {"de": VERSION, "vers": ancienne.group(1), "quand": time.strftime("%Y-%m-%d %H:%M:%S")}
        ecrire_json(FICHIER_REGLAGES, reglages)
        journal(f"RETOUR EN ARRIÈRE : la v{VERSION} n'a pas démarré, v{ancienne.group(1)} remise en place.\n{erreur}")
        try:
            messagebox.showwarning("Boîte à outils", f"La nouvelle version ({VERSION}) n'a pas réussi à démarrer.\n\n"
                                   f"J'ai remis la version d'avant ({ancienne.group(1)}) et coupé les mises à jour automatiques. "
                                   "Rien n'est perdu. Préviens Claude : le détail est dans le journal.")
        except Exception:
            pass
        arguments = [sys.executable, str(ici), "--apres-maj"] + (["--cache"] if "--cache" in sys.argv else [])
        drapeaux = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        subprocess.Popen(arguments, creationflags=drapeaux, close_fds=True)
        return True
    except Exception:
        journal("Retour en arrière impossible :\n" + __import__("traceback").format_exc())
        return False


if __name__ == "__main__":
    if "--apres-maj" in sys.argv:
        time.sleep(3)   # le temps que l'ancienne version se ferme
    elif deja_ouverte():
        sys.exit(0)
    journal(f"Démarrage v{VERSION} {sys.argv[1:]} depuis {Path(__file__).resolve()}")
    surveiller_plantages()
    noter_demarrage()
    threading.Thread(target=reparer_raccourci, daemon=True).start()
    try:   # range la copie de secours laissée sur le Bureau par les anciennes versions
        vieille = Path(__file__).resolve().with_name(Path(__file__).name + ".ancienne")
        if vieille.exists():
            DOSSIER_APPLI.mkdir(exist_ok=True)
            os.replace(vieille, DOSSIER_APPLI / vieille.name)
    except OSError:
        pass
    try:
        preparer_reglages()
        try:   # pour que Windows montre le logo de l'appli (et pas la plume Python) dans la barre des tâches
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Crz.BoiteAOutils")
        except (AttributeError, OSError):
            pass
        racine = tk.Tk()
        racine.report_callback_exception = lambda *e: journal("Erreur : " + "".join(__import__("traceback").format_exception(*e)))
        BoiteAOutils(racine, cache="--cache" in sys.argv)
        racine.mainloop()   # la fenêtre reste ouverte et attend tes clics
    except Exception:
        erreur = __import__("traceback").format_exc()
        journal("Plantage au démarrage :\n" + erreur)
        if revenir_en_arriere(erreur):
            noter_arret_propre()
            os._exit(1)   # on s'arrête net : l'ancienne version prend le relais
        raise
    noter_arret_propre()
    journal("Fermeture")
