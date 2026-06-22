"""Recommendation preference helpers for AI-generated collections."""

from dataclasses import dataclass, field


OBSCURITY_GUIDANCE = {
    1: "festival, micro-budget, indie, regional, or formally adventurous hidden gems; avoid obvious canon picks unless essential",
    2: "cult, international, older, or under-seen discoveries with enough reputation to trust",
    3: "a balanced mix of acclaimed discoveries and recognizable anchors",
    4: "accessible, critic-approved, familiar-enough picks with only a few deep cuts",
    5: "blockbuster, four-quadrant, Avengers-scale mainstream comfort picks",
}

ERA_LABELS = {
    "pre_1980": "primarily before 1980",
    "1980s": "primarily from the 1980s",
    "1990s": "primarily from the 1990s",
    "2000s": "primarily from the 2000s",
    "2010s": "primarily from the 2010s",
    "2020s": "primarily from the 2020s",
    "modern": "mostly from the last 15 years",
    "any": "",
}

RUNTIME_LABELS = {
    "under_100": "under 100 minutes",
    "standard": "around 100-130 minutes",
    "long": "longer, immersive watches are acceptable",
    "any": "",
}

PACE_LABELS = {
    "slow_burn": "slow burn",
    "balanced": "balanced",
    "propulsive": "propulsive",
    "any": "",
}

ENDING_LABELS = {
    "uplifting": "uplifting or cathartic",
    "bittersweet": "bittersweet",
    "bleak": "bleak or devastating",
    "ambiguous": "ambiguous or conversation-starting",
    "twisty": "twisty",
    "any": "",
}

LANGUAGE_LABELS = {
    "english": "prefer English-language picks",
    "non_english": "prefer non-English-language picks",
    "global": "mix English-language and international picks",
    "any": "",
}

WATCH_CONTEXT_LABELS = {
    "solo": "solo watch",
    "date_night": "date night",
    "group": "group watch",
    "family": "family-safe watch",
    "late_night": "late-night watch",
    "any": "",
}


def normalize_obscurity_level(value: int | str | None) -> int:
    try:
        level = int(value) if value is not None else 3
    except (TypeError, ValueError):
        level = 3
    return min(5, max(1, level))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _clean_choice(value: str | None, labels: dict[str, str]) -> str | None:
    cleaned = _clean_text(value)
    if not cleaned or cleaned == "any":
        return None
    return cleaned if cleaned in labels else None


@dataclass
class RecommendationPreferences:
    obscurity_level: int = 3
    seed_title: str | None = None
    seed_year: int | None = None
    genres: list[str] = field(default_factory=list)
    tone: str | None = None
    era: str | None = None
    runtime: str | None = None
    pace: str | None = None
    ending_vibe: str | None = None
    language_scope: str | None = None
    watch_context: str | None = None
    exclude_seen: bool = True

    def __post_init__(self):
        self.obscurity_level = normalize_obscurity_level(self.obscurity_level)
        self.seed_title = _clean_text(self.seed_title)
        self.tone = _clean_text(self.tone)
        self.era = _clean_choice(self.era, ERA_LABELS)
        self.runtime = _clean_choice(self.runtime, RUNTIME_LABELS)
        self.pace = _clean_choice(self.pace, PACE_LABELS)
        self.ending_vibe = _clean_choice(self.ending_vibe, ENDING_LABELS)
        self.language_scope = _clean_choice(self.language_scope, LANGUAGE_LABELS)
        self.watch_context = _clean_choice(self.watch_context, WATCH_CONTEXT_LABELS)
        self.genres = [g.strip() for g in self.genres if isinstance(g, str) and g.strip()][:6]

    @property
    def obscurity_guidance(self) -> str:
        return OBSCURITY_GUIDANCE[self.obscurity_level]


def item_labels(media_type: str) -> tuple[str, str]:
    if media_type == "show":
        return "TV show", "TV shows"
    return "movie", "movies"


def build_generation_user_message(
    prompt: str,
    movie_count: int,
    media_type: str,
    preferences: RecommendationPreferences | None = None,
) -> str:
    preferences = preferences or RecommendationPreferences()
    singular, plural = item_labels(media_type)
    cleaned_prompt = prompt.strip()
    lines: list[str] = []

    if preferences.seed_title:
        year = f" ({preferences.seed_year})" if preferences.seed_year else ""
        lines.append(
            f'Start from the {singular} "{preferences.seed_title}"{year} and recommend adjacent {plural} with related themes, tone, craft, or viewing feel.'
        )
        lines.append("Do not choose direct sequels, remakes, or franchise neighbors unless the user explicitly asks for them.")
        if cleaned_prompt:
            lines.append(f"Additional direction: {cleaned_prompt}")
    elif cleaned_prompt:
        lines.append(cleaned_prompt)
    else:
        lines.append(f"Find {plural} worth watching next.")

    lines.append(f"Return exactly {movie_count} {plural}.")
    lines.append("")
    lines.append("Discovery controls:")
    lines.append(f"- Obscurity level {preferences.obscurity_level}: {preferences.obscurity_guidance}")

    if preferences.genres:
        lines.append(f"- Genres: {', '.join(preferences.genres)}")
    if preferences.tone:
        lines.append(f"- Tone: {preferences.tone}")
    if preferences.era:
        lines.append(f"- Era: {ERA_LABELS[preferences.era]}")
    if preferences.runtime:
        lines.append(f"- Runtime: {RUNTIME_LABELS[preferences.runtime]}")
    if preferences.pace:
        lines.append(f"- Pace: {PACE_LABELS[preferences.pace]}")
    if preferences.ending_vibe:
        lines.append(f"- Ending vibe: {ENDING_LABELS[preferences.ending_vibe]}")
    if preferences.language_scope:
        lines.append(f"- Language: {LANGUAGE_LABELS[preferences.language_scope]}")
    if preferences.watch_context:
        lines.append(f"- Watch context: {WATCH_CONTEXT_LABELS[preferences.watch_context]}")
    if preferences.exclude_seen:
        lines.append("- Avoid every title already saved in the user's vault when an exclusion list is provided.")

    return "\n".join(lines)
