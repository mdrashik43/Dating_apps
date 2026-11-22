from matching.models import Match

S = "/api/game/sessions/"


def mutual_match(case, a, b):
    """Play the real game flow so both like each other; returns the Match."""
    for user in (a, b):
        c = case.client_for(user)
        sid = c.post(S).json()["id"]
        c.post(f"{S}{sid}/reveal/")
        c.post(f"{S}{sid}/decision/", {"action": "like"}, format="json")
    return Match.objects.get()
