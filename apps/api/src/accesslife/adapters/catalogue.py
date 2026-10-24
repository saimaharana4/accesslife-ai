"""Original factual summaries of public venue information, not copied source pages.

Coordinates are approximate venue locations, not accessible entrance coordinates.
Venue statements do not establish door-to-door routing or current lift operation.
"""

from datetime import datetime, timezone
from accesslife.domain.models import City, Evidence, Fact, Place

CITIES = [
    City(
        id="london",
        name="London",
        time_zone="Europe/London",
        latitude=51.514,
        longitude=-0.122,
        district="Central London",
    ),
    City(
        id="new-york",
        name="New York",
        time_zone="America/New_York",
        latitude=40.775,
        longitude=-73.97,
        district="Manhattan",
    ),
    City(
        id="paris",
        name="Paris",
        time_zone="Europe/Paris",
        latitude=48.861,
        longitude=2.33,
        district="Central Paris",
    ),
    City(
        id="berlin",
        name="Berlin",
        time_zone="Europe/Berlin",
        latitude=52.516,
        longitude=13.4,
        district="Central Berlin",
    ),
    City(
        id="chicago",
        name="Chicago",
        time_zone="America/Chicago",
        latitude=41.887,
        longitude=-87.622,
        district="Loop and museum district",
    ),
]
CITY_BY_ID = {c.id: c for c in CITIES}

# Known feature summaries are intentionally narrow. An empty tuple means unknown.
ROWS = [
    (
        "british-museum",
        "london",
        "British Museum",
        51.5194,
        -0.1270,
        ["history", "world cultures", "art"],
        "Explore world histories around the Great Court.",
        "https://www.britishmuseum.org/visit/accessibility-museum",
        {
            "step_free_entrance": "Main entrance lifts provide step-free entry.",
            "accessible_toilet": "The museum lists accessible toilets.",
            "lift": "Wheelchair-accessible lifts serve many galleries; some spaces have no level access.",
        },
    ),
    (
        "national-gallery",
        "london",
        "National Gallery",
        51.5089,
        -0.1283,
        ["art", "painting", "history"],
        "European paintings beside Trafalgar Square.",
        "https://www.nationalgallery.org.uk/visiting/access",
        {"accessible_toilet": "Accessible toilets are listed on several floors and near entrances."},
    ),
    (
        "tate-modern",
        "london",
        "Tate Modern",
        51.5076,
        -0.0994,
        ["modern art", "art", "architecture"],
        "Modern and contemporary art in a converted power station.",
        "https://www.tate.org.uk/visit/tate-modern",
        {},
    ),
    (
        "met-museum",
        "new-york",
        "The Metropolitan Museum of Art",
        40.7794,
        -73.9632,
        ["art", "history", "world cultures"],
        "Collections spanning cultures and centuries.",
        "https://www.metmuseum.org/visit-guides/accessibility",
        {
            "lift": "The museum describes elevators and step-free routes; ask staff for specific gallery access."
        },
    ),
    (
        "moma",
        "new-york",
        "Museum of Modern Art",
        40.7614,
        -73.9776,
        ["modern art", "design", "film", "art"],
        "Modern art, moving images and design in Midtown.",
        "https://www.moma.org/visit/accessibility/social-access-guide",
        {"accessible_toilet": "Wheelchair-accessible restrooms are listed on all floors near the escalator."},
    ),
    (
        "whitney",
        "new-york",
        "Whitney Museum of American Art",
        40.7396,
        -74.0089,
        ["modern art", "art", "architecture"],
        "American art beside the Hudson River.",
        "https://whitney.org/visit/access",
        {},
    ),
    (
        "louvre",
        "paris",
        "Musée du Louvre",
        48.8606,
        2.3376,
        ["art", "history", "painting"],
        "Historic collections in a former royal palace.",
        "https://www.louvre.fr/en/visit/accessibility",
        {},
    ),
    (
        "orsay",
        "paris",
        "Musée d’Orsay",
        48.86,
        2.3266,
        ["painting", "art", "architecture"],
        "Art and architecture in a former railway station.",
        "https://www.musee-orsay.fr/en/articles/accessibility-services-296252",
        {"lift": "Exhibition and service areas are described as reachable via elevators or ramps."},
    ),
    (
        "orangerie",
        "paris",
        "Musée de l’Orangerie",
        48.8638,
        2.3227,
        ["painting", "art", "quiet"],
        "A focused painting visit beside the Tuileries.",
        "https://www.musee-orangerie.fr/en/vous-etes/groupes-orangerie/accessibility-and-health-care-sector",
        {},
    ),
    (
        "jewish-museum",
        "berlin",
        "Jewish Museum Berlin",
        52.502,
        13.3954,
        ["history", "architecture", "world cultures"],
        "Jewish history and an expressive architectural setting.",
        "https://www.jmberlin.de/en/accessibility",
        {
            "accessible_toilet": "The museum lists two accessible bathrooms.",
            "lift": "Exhibition and event rooms are accessible through ramps or elevators.",
        },
    ),
    (
        "humboldt-bistro",
        "berlin",
        "Lebenswelten Bistro",
        52.5175,
        13.4019,
        ["food", "coffee", "world cultures"],
        "A food and coffee break inside the Humboldt Forum.",
        "https://www.humboldtforum.org/en/programm/dauerangebot/food-and-drink/lebenswelten-bistro-23376/",
        {},
    ),
    (
        "humboldt-forum",
        "berlin",
        "Humboldt Forum",
        52.517,
        13.401,
        ["world cultures", "art", "history"],
        "Cultural collections and exhibitions in central Berlin.",
        "https://www.humboldtforum.org/en/visit/",
        {},
    ),
    (
        "field-museum",
        "chicago",
        "Field Museum",
        41.8663,
        -87.617,
        ["history", "nature", "science"],
        "Natural history and science on the Museum Campus.",
        "https://www.fieldmuseum.org/page/visi/accessibility",
        {
            "step_free_entrance": "The East entrance is described as wheelchair-accessible.",
            "lift": "Two elevators are listed as serving the three public levels.",
        },
    ),
    (
        "mca",
        "chicago",
        "Museum of Contemporary Art Chicago",
        41.8972,
        -87.6213,
        ["modern art", "art", "design"],
        "Contemporary ideas, exhibitions and a sculpture garden.",
        "https://mcachicago.org/visit/faq/",
        {"accessible_toilet": "Accessible restrooms are listed on the first floor."},
    ),
    (
        "art-institute",
        "chicago",
        "Art Institute of Chicago",
        41.8796,
        -87.6237,
        ["painting", "art", "design"],
        "Painting, design and collections beside Millennium Park.",
        "https://www.artic.edu/visit/accessibility",
        {},
    ),
]

PLACES: list[Place] = []
EVIDENCE: dict[str, Evidence] = {}
for pid, city, name, lat, lon, interests, description, url, supported in ROWS:
    facts = []
    for feature in ("step_free_entrance", "accessible_toilet", "lift"):
        eid = f"{pid}-{feature}"
        if feature in supported:
            EVIDENCE[eid] = Evidence(
                id=eid,
                source_url=url,
                title=name,
                claim=supported[feature],
                retrieved_at="2026-10-24T00:00:00+05:30",
            )
        facts.append(
            Fact(
                feature=feature,
                status=(
                    "limited"
                    if (pid, feature) in {("british-museum", "lift"), ("met-museum", "lift")}
                    else "confirmed"
                )
                if feature in supported
                else "unknown",
                conditions=supported.get(feature)
                if (pid, feature) in {("british-museum", "lift"), ("met-museum", "lift")}
                else None,
                evidence_ids=[eid] if feature in supported else [],
                stale=(datetime.now(timezone.utc).date().isoformat() > "2026-11-23"),
            )
        )
    PLACES.append(
        Place(
            id=pid,
            city_id=city,
            name=name,
            category="dining" if "bistro" in pid else "museum",
            latitude=lat,
            longitude=lon,
            interests=interests,
            description=description,
            facts=facts,
            source_url=url,
        )
    )
