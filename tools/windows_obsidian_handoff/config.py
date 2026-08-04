"""
config.py - Central configuration for the Second Brain automation scripts.

EVERY script imports from here so paths, folders, and canonical-name rules
live in ONE place. Edit this file, not the individual scripts, when things move.
"""

from pathlib import Path

# ---------- CORE PATHS ----------
VAULT = Path("C:/Users/p005105K/OneDrive - Parsons Corp/Second Brain/Second Brain")
SCRIPTS_DIR = VAULT / "_scripts"
DAILY_DIR = VAULT / "Daily"
RAW_DIR = DAILY_DIR / "_raw"
PEOPLE_DIR = VAULT / "People"
PROJECTS_DIR = VAULT / "Projects"
TOPICS_DIR = VAULT / "Topics"
EVENTS_DIR = VAULT / "Events"
MEETINGS_DIR = VAULT / "Meetings"

# Folders that hold canonical entity notes (source of truth for names + aliases)
ENTITY_DIRS = ["People", "Projects", "Events", "Topics"]

# Folders to scan for [[wikilinks]] when creating stubs
SCAN_DIRS = ["Daily", "Meetings"]

# ---------- OUTLOOK (pull_yesterday) ----------
MAX_BODY_CHARS = 2000

# ---------- CANONICAL PROJECT NAMES ----------
# 1:1 variant (lowercased) -> single canonical link text
CANONICAL_PROJECTS = {
    "cas": "Sound Transit CAS",
    "sound transit cas": "Sound Transit CAS",
    "sound transit cbtc/cas": "Sound Transit CAS",
    "sound transit cbtc-cas": "Sound Transit CAS",
    "cbtc/cas": "Sound Transit CAS",
    "mnr gec": "MTA MNR GEC",
    "mta mnr gec": "MTA MNR GEC",
    "mta lirr gec": "MTA LIRR GEC",
    "lirr gec": "MTA LIRR GEC",
    "la metro p3030": "LA Metro P3030",
    "la metro p3030 lrv acquisition": "LA Metro P3030",
    "p3030": "LA Metro P3030",
    "hitachi r262": "Hitachi R262",
    "r262": "Hitachi R262",
}

# Combined variant (lowercased) -> list of canonical links (expands to multiple)
COMBINED_PROJECTS = {
    "mta lirr/mnr gec": ["MTA LIRR GEC", "MTA MNR GEC"],
    "lirr/mnr gec": ["MTA LIRR GEC", "MTA MNR GEC"],
    "mta lirr / mnr gec": ["MTA LIRR GEC", "MTA MNR GEC"],
    "lirr/mnr": ["MTA LIRR GEC", "MTA MNR GEC"],
}

# Map project canonical -> /Projects/ subfolder for stub creation
PROJECT_SUBFOLDER = {
    "Sound Transit CAS": "Sound Transit CAS",
    "MTA LIRR GEC": "MTA LIRR GEC",
    "MTA MNR GEC": "MTA MNR GEC",
    "LA Metro P3030": "LA Metro P3030",
    "Hitachi R262": "Hitachi R262",
    "APTA 2026": "APTA 2026",
}

# ---------- PEOPLE ROSTER (nicknames / short-forms -> canonical People note) ----------
# Add a row any time someone shows up under a new short name.
ROSTER = {
    "Matt": "Matthew Lorenz",
    "Matthew Lorenz": "Matthew Lorenz",
    "Gina": "Gina DeBenedictis",
    "Gina DeBenedictis": "Gina DeBenedictis",
    "Thomas": "Thomas Mudayankavil",
    "Thomas Mudayankavil": "Thomas Mudayankavil",
    "Ernesto": "Ernesto Garcia",
    "Ernesto Garcia": "Ernesto Garcia",
    "Gorov": "Gaurav Kaushik",
    "Gaurav": "Gaurav Kaushik",
    "Gaurav Kaushik": "Gaurav Kaushik",
    "Benjamin": "Benjamin Smoker",
    "Ben Smoker": "Benjamin Smoker",
    "Benjamin Smoker": "Benjamin Smoker",
    "Muamer Dedovic": "Muamer Dedovic",
    "Muamer": "Muamer Dedovic",
    "Dedovic": "Muamer Dedovic",
    "Deda": "Muamer Dedovic",
    "Neville Bugwadia": "Neville Bugwadia",
    "Neville": "Neville Bugwadia",
    "Mark Gander": "Mark Gander",
    "Kenneth Burkhardt": "Kenneth Burkhardt",
    "Joseph Bellars": "Joseph Bellars",
    "Wilson Gago": "Wilson Gago",
    "Kenneth Mangam": "Kenneth Mangam",
    "Ky Fu": "Ky Fu",
    "Mark De Vito": "Mark De Vito",
    "Annie Yang": "Annie Yang",
    "Jim Martin": "Jim Martin",
    "Amy Lively": "Amy Lively",
    "Amy": "Amy Lively",
    "Brian Painley": "Brian Painley",
    "Jason Grohs": "Jason Grohs",
    "Jason": "Jason Grohs",
}

# ---------- STOPWORDS (never auto-link these as person/topic nodes) ----------
# Generic words, firms, and agencies. Agencies that are projects link via CANONICAL_PROJECTS.
STOPWORDS = {
    "team", "parsons", "arup", "stv", "hatch", "crrc", "colliers", "t&m",
    "sound transit", "la metro", "mbta", "wmata", "mdot", "amtrak",
    "seth", "cody", "kai", "elephant", "tom", "siemens", "wabtec",
}
