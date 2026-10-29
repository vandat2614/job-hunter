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
    if event.get("url"):
        lines += ["", event["url"]]
    return "\n".join(lines)
