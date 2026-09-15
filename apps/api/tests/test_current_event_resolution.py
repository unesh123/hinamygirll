from hinaa_api.media.current_event_resolver import CurrentEventResolver, ResolvedCurrentEvent
from hinaa_api.media.search_intelligence import (
    build_media_intent,
    compile_image_search_query,
)


def test_nepal_incident_resolution():
    res = CurrentEventResolver.resolve_event("Nepal current incident", location="Nepal")
    assert res is not None
    assert "Monsoon" in res.event_name or "Flood" in res.event_name
    assert "nepal" in res.specific_search_query.lower()
    assert "kathmandu" in res.specific_search_query.lower()
    assert "flood" in res.specific_search_query.lower()
    assert "anime" in res.negative_terms


def test_japan_earthquake_resolution():
    res = CurrentEventResolver.resolve_event("Japan earthquake pictures", location="Japan")
    assert res is not None
    assert "Earthquake" in res.event_name or "Seismic" in res.event_name
    assert "tokyo" in res.specific_search_query.lower()
    assert "seismic" in res.specific_search_query.lower() or "earthquake" in res.specific_search_query.lower()


def test_dynamic_location_resolution():
    res = CurrentEventResolver.resolve_event("sydney flood damage", location="Sydney")
    assert res is not None
    assert "Sydney" in res.location
    assert "flood" in res.specific_search_query.lower()


def test_nepal_incident_e2e_query_compilation():
    intent = build_media_intent("fetch Nepal current incident images", active_subject="Mikasa")
    assert intent is not None
    assert intent.subject_type in ("current_event", "topic")
    assert "nepal" in intent.canonical_subject.lower()

    spec = compile_image_search_query(intent)
    assert "nepal" in spec.primary_query.lower()
    assert "kathmandu" in spec.primary_query.lower()
    assert "flood" in spec.primary_query.lower()
    # Ensure anime/Mikasa is strongly filtered
    assert any("mikasa" in term.lower() for term in spec.negative_terms)
    assert any("anime" in term.lower() for term in spec.negative_terms)
    # Ensure provider profile is news
    assert spec.provider_profile == "news_image_search"


def test_event_resolution_from_live_evidence_headlines():
    live_headlines = [
        "Kathmandu Valley inundated as incessant monsoon rain triggers massive flash floods and landslides",
        "Nepal disaster management agency deploys emergency rescue teams across Bagmati corridor",
        "Heavy landslides block major highways into Kathmandu valley",
    ]
    res = CurrentEventResolver.resolve_event_from_evidence(
        "tell me about what is happening in nepal",
        live_headlines,
        location="Nepal",
    )
    assert res is not None
    assert "Nepal" in res.location
    assert "flood" in res.event_name.lower() or "landslide" in res.event_name.lower()
    assert len(res.evidence) >= 2
    assert "Kathmandu Valley" in res.evidence[0]
    assert "flood" in res.specific_search_query.lower()
    assert "landslide" in res.specific_search_query.lower()
    assert "2026" in res.specific_search_query

