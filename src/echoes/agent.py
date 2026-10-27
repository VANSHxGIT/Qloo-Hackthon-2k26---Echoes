"""Agentic Reminiscence Session Synthesizer for Echoes.

Coordinates Qloo cultural taste retrieval, golden-era temporal anchoring,
zero-hallucination session structuring, sensory cue generation, and
adaptive emotional feedback loops.
"""
from __future__ import annotations

import logging
from typing import Any

from .db import EchoesDB
from .presets import get_preset
from .qloo import (
    ARTIST,
    BRAND,
    MOVIE,
    PLACE,
    TV_SHOW,
    Entity,
    QlooClient,
    QlooError,
)

logger = logging.getLogger(__name__)

DOMAIN_MAP = {
    "artist": ARTIST,
    "movie": MOVIE,
    "tv_show": TV_SHOW,
    "brand": BRAND,
    "place": PLACE,
}

DOMAIN_TITLES = {
    "artist": "Auditory Spark & Musical Anchor",
    "movie": "Silver Screen & Storytelling",
    "tv_show": "Family Evening Broadcast",
    "brand": "Childhood Flavors & Everyday Nostalgia",
    "place": "Hometown Walkdown & Landmark Memories",
}


def compute_reminiscence_bump(birth_year: int) -> tuple[int, int]:
    """Calculates the golden reminiscence bump window (ages 12 to 28)."""
    return (birth_year + 12, birth_year + 28)


def get_conversation_starter(domain: str, name: str, culture: str, era_str: str) -> str:
    """Generates a non-confrontational, open-ended reminiscence prompt.

    Avoids memory quizzes (e.g. 'Do you remember X?') which cause anxiety.
    Uses sensory and emotional invitations instead.
    """
    if domain == "artist":
        return f"Listen to this gentle rhythm by {name}... How does this melody feel to your heart today? Does it remind you of singing along with friends?"
    elif domain == "movie":
        return f"Thinking back to cinema days and {name}... Picture the glowing screen and the theater crowd. Who would you love to sit beside watching this?"
    elif domain == "tv_show":
        return f"When {name} came on in the evening, the whole neighborhood would settle in. Was your home lively or quiet around dinnertime?"
    elif domain == "brand":
        return f"Think of the taste and package of {name} from back then... What sweets or treats did you celebrate with on special festival days?"
    elif domain == "place":
        return f"Imagine strolling past {name} in {era_str}... Feel the evening air and hear the bustling sounds. What is the prettiest spot in town you loved to visit?"
    return f"What feeling or picture comes to mind when you hear the name '{name}'?"


def get_sensory_cue(domain: str, name: str, culture: str, hometown: str) -> str:
    """Provides practical sensory grounding ideas for the caregiver."""
    c = culture.lower()
    if domain == "artist":
        if "india" in c or "delhi" in hometown.lower():
            return "Brew a fresh cup of warm cardamom masala chai and play this melody softly in the background."
        if "nigeria" in c or "yoruba" in c:
            return "Play the percussion at low volume and tap a gentle rhythm on the table together."
        if "brazil" in c:
            return "Pour a small warm cup of café passado and let the acoustic guitar strings fill the room."
        if "japan" in c:
            return "Offer a warm cup of roasted hojicha green tea as the gentle vocals begin."
        return "Put on soft ambient lighting and let the opening chords play quietly before talking."

    if domain == "brand":
        if "india" in c:
            return "Share a small piece of jaggery or a crisp glucose biscuit to trigger familiar taste memories."
        if "mexic" in c:
            return "Offer a warm sip of cinnamon hot chocolate with a sweet bread (pan dulce)."
        if "brazil" in c:
            return "A small bite of warm pão de queijo or guava sweet (goiabada)."
        return "Present a familiar childhood snack or aroma before introducing this topic."

    if domain == "place":
        return f"Close your eyes together and imagine the breeze, the sunset, and the laughter at {name} in {hometown}."

    return "Keep hands relaxed, maintain eye contact with a warm smile, and let memories surface without rush."


class ReminiscenceAgent:
    def __init__(self, client: QlooClient, db: EchoesDB):
        self.client = client
        self.db = db

    def resolve_seeds(self, seeds: list[dict[str, Any]]) -> list[Entity]:
        """Resolves raw seed strings to verified Qloo entities."""
        resolved: list[Entity] = []
        for s in seeds:
            name = s.get("name", "").strip()
            etype = s.get("type") or ARTIST
            if not name:
                continue
            try:
                hits = self.client.search(query=name, types=etype, take=3)
                if hits:
                    resolved.append(hits[0])
                else:
                    # Fabricate a safe fallback entity with the seed name
                    resolved.append(Entity(id=f"seed-{name.lower().replace(' ', '-')}", name=name, type=etype))
            except Exception as e:
                logger.warning(f"Error resolving seed {name}: {e}")
                resolved.append(Entity(id=f"seed-{name.lower().replace(' ', '-')}", name=name, type=etype))
        return resolved

    def retrieve_domain_insights(
        self,
        domain_key: str,
        entity_signals: list[str],
        hometown: str,
        exclude_entities: list[str],
        take: int = 4,
    ) -> list[Entity]:
        """Queries Qloo for taste neighbours in a specific domain."""
        etype = DOMAIN_MAP.get(domain_key, ARTIST)
        try:
            # For places, use filter_location; for others use location signal
            is_place = domain_key == "place"
            entities = self.client.insights(
                entity_type=etype,
                entities=entity_signals if entity_signals else None,
                location=None if is_place else (hometown or None),
                filter_location=hometown if is_place else None,
                exclude_entities=exclude_entities if exclude_entities else None,
                take=take,
            )
            # Filter out any explicitly excluded
            return [e for e in entities if e.id not in exclude_entities]
        except Exception as e:
            logger.warning(f"Qloo insights error for domain {domain_key}: {e}")
            return []

    def compose_session(
        self,
        patient_id: str | None,
        name: str,
        birth_year: int,
        hometown: str,
        culture: str = "",
        seed_inputs: list[dict[str, Any]] | None = None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        """Generates a complete, structured 15-20 min Reminiscence Therapy session."""
        bump_start, bump_end = compute_reminiscence_bump(birth_year)
        era_str = f"{bump_start} - {bump_end}"

        # 1. Load patient and adaptive history if available
        exclude_entities: list[str] = []
        positive_entities: list[str] = []
        if patient_id:
            signals = self.db.get_adaptive_signals(patient_id)
            exclude_entities = signals.get("exclude_entities", [])
            positive_entities = signals.get("positive_entities", [])

        # 2. Check for preset context
        preset = get_preset(preset_id) if preset_id else None
        if preset and not seed_inputs:
            seed_inputs = preset.get("seeds", [])
            if not culture:
                culture = preset.get("culture", "")

        raw_seeds = seed_inputs or []

        # 3. Resolve seeds to Qloo entities
        resolved_seeds = self.resolve_seeds(raw_seeds)
        seed_ids = [s.id for s in resolved_seeds if s.id and not s.id.startswith("seed-")]
        all_signals = list(dict.fromkeys(seed_ids + positive_entities))

        # 4. Multi-domain retrieval
        domain_results: dict[str, list[Entity]] = {}
        for domain_key in ["artist", "movie", "tv_show", "brand", "place"]:
            res = self.retrieve_domain_insights(
                domain_key=domain_key,
                entity_signals=all_signals,
                hometown=hometown,
                exclude_entities=exclude_entities,
                take=4,
            )
            # If domain results are thin, inject resolved seed if matching type
            if not res:
                matching_seeds = [s for s in resolved_seeds if s.type == DOMAIN_MAP.get(domain_key)]
                if matching_seeds:
                    res = matching_seeds

            domain_results[domain_key] = res

        # 5. Build Structured Chapters
        chapters: list[dict[str, Any]] = []
        qloo_verified_count = 0
        total_items_count = 0

        for i, (domain_key, entities) in enumerate(domain_results.items(), start=1):
            if not entities:
                continue

            primary = entities[0]
            alternatives = entities[1:4]
            total_items_count += 1
            is_verified = bool(primary.id and not primary.id.startswith("seed-"))
            if is_verified:
                qloo_verified_count += 1

            prompt = get_conversation_starter(domain_key, primary.name, culture, era_str)
            sensory = get_sensory_cue(domain_key, primary.name, culture, hometown)

            chapter = {
                "step": i,
                "domain": domain_key,
                "domain_title": DOMAIN_TITLES.get(domain_key, domain_key.title()),
                "primary_entity": {
                    "id": primary.id,
                    "name": primary.name,
                    "type": primary.type,
                    "popularity": primary.popularity,
                    "affinity": primary.affinity,
                    "tags": primary.tags[:4],
                    "qloo_verified": is_verified,
                },
                "alternative_entities": [
                    {
                        "id": alt.id,
                        "name": alt.name,
                        "type": alt.type,
                        "popularity": alt.popularity,
                        "qloo_verified": bool(alt.id and not alt.id.startswith("seed-")),
                    }
                    for alt in alternatives
                ],
                "conversation_prompt": prompt,
                "sensory_cue": sensory,
                "target_minutes": 3 if domain_key in ("brand", "place") else 4,
            }
            chapters.append(chapter)

        # 6. Generate Generic LLM Baseline for Side-by-Side Comparison
        generic_baseline = self._generate_generic_llm_baseline(
            birth_year=birth_year,
            hometown=hometown,
            culture=culture,
            preset=preset,
        )

        session_payload = {
            "title": f"Reminiscence Journey for {name} ({era_str})",
            "patient_name": name,
            "birth_year": birth_year,
            "golden_era": era_str,
            "hometown": hometown,
            "culture": culture,
            "total_duration_minutes": sum(c["target_minutes"] for c in chapters),
            "chapters": chapters,
            "seeds_used": [{"id": s.id, "name": s.name, "type": s.type} for s in resolved_seeds],
            "excluded_entities_count": len(exclude_entities),
            "stats": {
                "qloo_verified_entities": qloo_verified_count,
                "total_anchors": total_items_count,
                "grounding_score": f"{int((qloo_verified_count / max(1, total_items_count)) * 100)}%",
            },
        }

        # 7. Persist session if patient_id is present
        saved_session = None
        if patient_id:
            saved_session = self.db.save_session(
                patient_id=patient_id,
                title=session_payload["title"],
                session_data=session_payload,
                comparison_data=generic_baseline,
            )

        return {
            "session_id": saved_session["id"] if saved_session else "temp_session",
            "session": session_payload,
            "generic_baseline": generic_baseline,
        }

    def _generate_generic_llm_baseline(
        self,
        birth_year: int,
        hometown: str,
        culture: str,
        preset: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Simulates what a standard generic LLM generates without Qloo grounding.

        Highlights Western pop culture bias, cultural displacement, and lack of verified IDs.
        """
        if preset and "generic_llm_comparison" in preset:
            comp = preset["generic_llm_comparison"]
            return {
                "model_name": "Generic LLM (No Taste Graph)",
                "hallucination_risk": comp["hallucination_risk"],
                "qloo_grounding_score": "0%",
                "cultural_accuracy": "Low (Western Default)",
                "simulated_output": {
                    "music": "Elvis Presley - 'Can't Help Falling in Love' (1961)",
                    "movie": "Casablanca or Singin' in the Rain (Generic Hollywood)",
                    "tv_show": "I Love Lucy or The Twilight Zone",
                    "brand": "Campbell's Tomato Soup / Coca-Cola Diner Glass",
                    "place": "1950s Downtown Main Street / American Diner",
                },
                "critical_flaws": comp["flaws"],
                "verdict": "Fails clinical safety: triggers confusion and agitation due to complete cultural dissonance.",
            }

        return {
            "model_name": "Generic LLM (No Taste Graph)",
            "hallucination_risk": "High (Generic Western Bias)",
            "qloo_grounding_score": "0%",
            "cultural_accuracy": "Displaced",
            "simulated_output": {
                "music": "The Beatles / Frank Sinatra (Default 1950s/60s Western Canon)",
                "movie": "The Wizard of Oz or Roman Holiday",
                "tv_show": "The Ed Sullivan Show",
                "brand": "Vintage Coca-Cola or Kellogg's Corn Flakes",
                "place": f"Generic central square in {hometown} (Hallucinated modern spots)",
            },
            "critical_flaws": [
                f"Ignored the regional cultural nuances of {culture or hometown}",
                f"Defaulted to Anglo-American canon for someone born in {birth_year}",
                "No entity verification or emotional safety blacklist filtering",
            ],
            "verdict": "Unverified LLM generation carries high risk of distressing the care recipient.",
        }
