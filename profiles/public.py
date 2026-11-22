def public_profile(profile) -> dict:
    """The ONLY shape in which another student's profile may leave the server.
    No email, no date of birth, no user id."""
    return {
        "display_name": profile.display_name,
        "age": profile.age,
        "gender": profile.gender,
        "looking_for": profile.looking_for,
        "bio": profile.bio,
        "department": profile.department,
        "batch": profile.batch,
    }
