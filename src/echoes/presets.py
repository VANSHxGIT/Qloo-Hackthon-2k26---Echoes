"""Rich cultural presets for Echoes.

Demonstrates high-affinity reminiscence across diverse global regions and eras.
Used for 1-click hackathon evaluation and caregiver testing.
"""
from __future__ import annotations

from typing import Any

from .qloo import ARTIST, BRAND, MOVIE, PLACE, TV_SHOW

PRESETS: list[dict[str, Any]] = [
    {
        "id": "delhi_1942",
        "name": "Dadi Savitri",
        "title": "Delhi Heritage & Golden Era Cinema",
        "birth_year": 1942,
        "hometown": "Delhi",
        "culture": "Hindi / North India",
        "golden_era": "1954 - 1970",
        "flag": "🇮🇳",
        "badge_color": "var(--amber-warm)",
        "bio": "Grew up near Chandni Chowk, loved listening to All India Radio on the transistor with family.",
        "seeds": [
            {"name": "Kishore Kumar", "type": ARTIST, "era": "1960s-70s"},
            {"name": "Sholay", "type": MOVIE, "era": "1975"},
            {"name": "Lata Mangeshkar", "type": ARTIST, "era": "1950s-70s"},
        ],
        "sensory_cues": [
            "Aroma of freshly bruised cardamom pods and simmering masala chai",
            "Faint morning temple bells and street hawker call 'Chai garam chai'",
            "Crunch of warm roasted groundnuts wrapped in old newspaper",
        ],
        "generic_llm_comparison": {
            "model_guess": "1950s Pop & American Standards",
            "flaws": [
                "Suggested Elvis Presley and Frank Sinatra for a Delhi grandmother",
                "Recommended diner apple pie and drive-in movie theatres",
                "Completely erased post-partition Delhi radio and Hindi cinema heritage",
            ],
            "hallucination_risk": "Critical (Cultural Irrelevance)",
        },
    },
    {
        "id": "lagos_1952",
        "name": "Baba Tunde",
        "title": "Lagos Island Highlife & Early Nollywood",
        "birth_year": 1952,
        "hometown": "Lagos",
        "culture": "Nigerian / Yoruba",
        "golden_era": "1964 - 1980",
        "flag": "🇳🇬",
        "badge_color": "var(--emerald-vibrant)",
        "bio": "Danced to live highlife bands in Surulere and loved weekend street carnivals and vinyl records.",
        "seeds": [
            {"name": "Fela Kuti", "type": ARTIST, "era": "1970s"},
            {"name": "Living in Bondage", "type": MOVIE, "era": "1992"},
            {"name": "King Sunny Ade", "type": ARTIST, "era": "1970s-80s"},
        ],
        "sensory_cues": [
            "Aroma of hot peppery suya with sliced red onions",
            "Polyrhythmic talking drum beats floating through a warm humid evening",
            "Sweet scent of fried plantains (dodo) on Sunday afternoon",
        ],
        "generic_llm_comparison": {
            "model_guess": "1960s Classic Rock & Motown",
            "flaws": [
                "Offered The Beatles and Bob Dylan to a Lagos resident",
                "Confused Nigerian Jùjú music with generic African safari tracks",
                "Missed landmark Lagos gathering places like the Shrine and Tafawa Balewa Square",
            ],
            "hallucination_risk": "High (Generic Western Canon Fallback)",
        },
    },
    {
        "id": "saopaulo_1947",
        "name": "Dona Maria Helena",
        "title": "São Paulo Bossa Nova & Vintage Telenovelas",
        "birth_year": 1947,
        "hometown": "São Paulo",
        "culture": "Brazilian / Paulista",
        "golden_era": "1959 - 1975",
        "flag": "🇧🇷",
        "badge_color": "var(--cyan-accent)",
        "bio": "Treasures memories of listening to MPB on Sunday afternoons in Vila Madalena.",
        "seeds": [
            {"name": "Elis Regina", "type": ARTIST, "era": "1960s-70s"},
            {"name": "Roque Santeiro", "type": TV_SHOW, "era": "1985"},
            {"name": "Tom Jobim", "type": ARTIST, "era": "1960s"},
        ],
        "sensory_cues": [
            "Fragrance of freshly filtered café passado and warm pão de queijo",
            "Gentle acoustic guitar nylon strings playing 'Águas de Março'",
            "Brisk autumn breeze blowing across the Praça da Sé",
        ],
        "generic_llm_comparison": {
            "model_guess": "1960s American Easy Listening",
            "flaws": [
                "Replaced Elis Regina and MPB with generic instrumental elevator jazz",
                "Hallucinated American sit-coms instead of historic Rede Globo telenovelas",
                "Suggested Miami beaches instead of São Paulo coffee culture",
            ],
            "hallucination_risk": "High (Stereotypical Misattribution)",
        },
    },
    {
        "id": "tokyo_1938",
        "name": "Keiko-san",
        "title": "Tokyo Showa Retro & Classic Cinema",
        "birth_year": 1938,
        "hometown": "Tokyo",
        "culture": "Japanese / Showa",
        "golden_era": "1950 - 1966",
        "flag": "🇯🇵",
        "badge_color": "var(--rose-soft)",
        "bio": "Remembers the bustling reconstruction of downtown Asakusa and the golden age of Showa radio.",
        "seeds": [
            {"name": "Hibari Misora", "type": ARTIST, "era": "1950s-60s"},
            {"name": "Tokyo Story", "type": MOVIE, "era": "1953"},
            {"name": "Kyu Sakamoto", "type": ARTIST, "era": "1961"},
        ],
        "sensory_cues": [
            "Steaming roasted green tea (Hojicha) in a ceramic cup",
            "Faint nostalgic clatter of Showa streetcars (Toden Arakawa line)",
            "Sweet scent of warm dorayaki pancake red-bean filling",
        ],
        "generic_llm_comparison": {
            "model_guess": "Post-war American Big Band",
            "flaws": [
                "Suggested Glenn Miller and Doris Day for a Tokyo senior",
                "Ignored Enka and Showa Kayōkyoku musical tradition entirely",
                "Hallucinated modern anime rather than authentic post-war Yasujiro Ozu cinema",
            ],
            "hallucination_risk": "Extreme (Anachronism & Western Displacement)",
        },
    },
    {
        "id": "mexicocity_1945",
        "name": "Don Mateo",
        "title": "Mexico City Época de Oro & Mariachi",
        "birth_year": 1945,
        "hometown": "Mexico City",
        "culture": "Mexican / Chilango",
        "golden_era": "1957 - 1973",
        "flag": "🇲🇽",
        "badge_color": "var(--gold-warm)",
        "bio": "Loved singing along to Pedro Infante movies on Sunday evenings in Coyoacán.",
        "seeds": [
            {"name": "Pedro Infante", "type": ARTIST, "era": "1940s-50s"},
            {"name": "Nosotros los pobres", "type": MOVIE, "era": "1948"},
            {"name": "Jorge Negrete", "type": ARTIST, "era": "1940s-50s"},
        ],
        "sensory_cues": [
            "Rich Mexican hot chocolate with canela (cinnamon) and pan dulce",
            "Bright trumpet fanfare of Mariachi Vargas echoing in Plaza Garibaldi",
            "Warm eucalyptus-scented morning breeze in Chapultepec park",
        ],
        "generic_llm_comparison": {
            "model_guess": "1950s Tex-Mex & American Country",
            "flaws": [
                "Conflated authentic Golden Age Mexican cinema with Western Hollywood cowboy films",
                "Missed iconic Mexico City landmarks like Alameda Central and Palacio de Bellas Artes",
                "Invented modern pop tracks not existent in his youth",
            ],
            "hallucination_risk": "High (Cultural Conflation)",
        },
    },
]


def get_preset(preset_id: str) -> dict[str, Any] | None:
    for p in PRESETS:
        if p["id"] == preset_id:
            return p
    return None
