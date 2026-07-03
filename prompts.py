"""
Prompts de Voice Design pour Nestor.

4 variantes dosant differemment les 3 couches de la DA :
  - MAJORDOME : diction formelle, phrase pesee, retenue (Stevens / Nestor / TARS)
  - GLADOS    : mordant froid, sarcasme poli, calme menacant
  - LAPIN     : timbre clair/chaud/leger, rondeur presque enfantine (Nabaztag)
  - SYNTHESE  : grain robotique, coloration electronique

Lancer une variante :  python3 design.py --variant 0
Les descriptions sont en anglais (ElevenLabs Voice Design comprend mieux
l'anglais pour la *description*, le rendu se fait ensuite en francais).
"""

PROMPTS = [
    {
        "label": "majordome-glacial",
        # Equilibre : majordome dominant, GLaDOS en sous-texte, une pointe de synthetique.
        "prompt": (
            "A composed, softly-spoken domestic butler with a light, warm, "
            "slightly androgynous timbre. Impeccably formal and courteous diction, "
            "very measured and slow pacing with deliberate pauses. Beneath the "
            "politeness, a dry, cold, passive-aggressive undertone. Faintly "
            "synthetic, like a refined household AI. Calm, never raising its voice."
        ),
    },
    {
        "label": "glados-pousse",
        # Curseur sarcasme au maximum : le contraste douceur/cruaute facon GLaDOS.
        "prompt": (
            "A calm, polite feminine-leaning artificial intelligence voice with a "
            "gentle, almost sweet tone that delivers cutting sarcasm without ever "
            "changing pitch. Clinical, deadpan, subtly condescending. A soft "
            "robotic vocoded texture. Unsettlingly serene, like a smiling machine "
            "that finds humans mildly disappointing."
        ),
    },
    {
        "label": "lapin-nabaztag",
        # Curseur douceur/lapin au maximum : chaleur, legerete, attachant.
        "prompt": (
            "A light, bright, warm and friendly voice with a soft, slightly childlike "
            "roundness, like a gentle electronic companion toy. Clear and airy timbre, "
            "polite and attentive, with a faint charming synthetic shimmer. Cute but "
            "well-mannered, with just a hint of cheeky dryness underneath."
        ),
    },
    {
        "label": "synthetique-vintage",
        # Curseur robot/vintage au maximum : coloration electronique marquee.
        "prompt": (
            "A vintage synthetic voice, like an early home-computer assistant, with a "
            "gentle vocoder coloration and a smooth electronic grain. Formal, "
            "articulate and calm, courteous like a butler but clearly artificial. "
            "Understated dry wit. Neutral, precise, mechanical yet oddly warm."
        ),
    },
]
