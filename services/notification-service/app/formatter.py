BASIS_LABELS = {"skills_only": "skills only", "experience_only": "experience only"}


def format_salary(smin: int | None, smax: int | None, currency: str | None) -> str | None:
    if smin is None and smax is None:
        return None
    suffix = f" {currency}" if currency else ""
    if smin is not None and smax is not None:
        if smin == smax:
            return f"{smin:,}{suffix}"
        return f"{smin:,} - {smax:,}{suffix}"
    if smin is not None:
        return f"from {smin:,}{suffix}"
    return f"up to {smax:,}{suffix}"


def format_message(event: dict) -> str:
    """Plain text on purpose: no parse_mode, so no escaping issues with job titles."""
    lines = ["New job match", "", event["title"]]
    where = " | ".join(x for x in (event["company"], event.get("location")) if x)
    lines.append(where)
    salary = format_salary(event.get("salary_min"), event.get("salary_max"), event.get("salary_currency"))
    if salary:
        lines.append(f"Salary: {salary}")

    score = event.get("score")
    if score is not None:
        label = BASIS_LABELS.get(event.get("basis"))
        lines.append(f"Fit score: {score}/100" + (f" ({label})" if label else ""))
        if event.get("matched_skills"):
            lines.append("You have: " + ", ".join(event["matched_skills"][:8]))
        if event.get("missing_skills"):
            lines.append("Missing: " + ", ".join(event["missing_skills"][:8]))
        if event.get("note"):
            lines.append(event["note"])

    if event.get("url"):
        lines += ["", event["url"]]
    return "\n".join(lines)
