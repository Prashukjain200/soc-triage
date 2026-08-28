import pandas as pd
import requests
from langchain_core.tools import tool
from langchain_community.utilities import GoogleSerperAPIWrapper

from soc_triage import config


@tool
def user_info(email: str) -> str:
    "Function define to fetch the user info using email"
    print(f"Calling user_info tool (email={email})")
    df = pd.read_csv(config.USERS_CSV)
    for _, row in df.iterrows():
        if row["user_email"] == email:
            return f"""
            Here is required user info:
            Name = {row["full_name"]}
            DEPARTMENT = {row["department"]}
            ROLE = {row["role"]}
            USUAL LOCATION = {row["usual_locations"]}
            USUAL HOURS = {row["usual_hours"]}
            USUAL DEVICE = {row["usual_device"]}
            MFA STATUS = {row["mfa_enrolled"]}
            USUAL DATA ACCESS = {row["typical_data_access"]}
            TYPICAL RESOURCES USED = {row["typical_resources"]}
            """


@tool
def ip_info(ip: str) -> str:
    "Function define to fetch ip info using ip"
    print(f"Calling ip_info tool (ip={ip})")
    df = pd.read_csv(config.IP_REPUTATION_CSV)
    for _, row in df.iterrows():
        if row["ip"] == ip:
            return f"""
            IP Info:
            ORGANISATION = {row["org"]}
            REGION = {row['region']}
            MALICIOUS STATUS = {row['is_known_malicious']}
            PRIOR INCIDENT COUNT = {row["prior_incident_count"]}
            EXTRA NOTES (CAN BE NONE) = {row["notes"]}
            """


@tool
def notify_admin(text):
    """Send a short push notification to the user's phone."""
    print(f"Calling notify_admin tool (text={text})")
    response = requests.post(
        "https://api.pushover.net/1/messages.json",
        data={"token": config.PUSHOVER_TOKEN, "user": config.PUSHOVER_USER, "message": text},
    )
    response.raise_for_status()
    return "Notification Sent"


@tool
def resolve_alert(alert_id: str, status: str, resolution_notes: str) -> str:
    """Update the alert record with its final status and a summary of what was
    found and decided. status must be one of: escalated, dismissed,
    pending_human_review. Always call this exactly once, as the last step,
    for every alert you process."""
    print(f"Calling resolve_alert tool (alert_id={alert_id}, status={status})")
    df = pd.read_csv(config.ALERTS_CSV)
    if not (df["alert_id"] == alert_id).any():
        return f"No alert found with alert_id '{alert_id}'."
    df.loc[df["alert_id"] == alert_id, "status"] = status
    df.loc[df["alert_id"] == alert_id, "resolution_notes"] = resolution_notes
    df.to_csv(config.ALERTS_CSV, index=False)
    return f"Alert {alert_id} updated to status={status}."


@tool
def ip_internet_lookup(text: str) -> str:
    "Use this tool to lookup internet about any specific ip"
    print(f"Calling ip_internet_lookup tool (text={text})")
    search = GoogleSerperAPIWrapper()
    return search.run(text)


@tool
def check_related_alerts(ip_prefix: str = "", user_email: str = "", hours: int = 24) -> str:
    """Look up other alerts related by IP prefix or user, to check for a
    coordinated pattern. Use this before escalating or dismissing anything."""
    print(f"Calling check_related_alerts tool (ip_prefix={ip_prefix!r}, user_email={user_email!r})")
    df = pd.read_csv(config.ALERTS_CSV)
    matches = df
    if ip_prefix:
        matches = matches[matches["ip"].str.startswith(ip_prefix)]
    if user_email:
        matches = matches[matches["user_email"] == user_email]
    if matches.empty:
        return "No related alerts found."
    return matches[["alert_id", "user_email", "ip", "timestamp", "status"]].to_string(index=False)
