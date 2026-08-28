import pandas as pd
from langgraph.types import Command

from soc_triage import config
from soc_triage.agents import supervisor_agent


def load_pending_alerts(path=None) -> pd.DataFrame:
    df = pd.read_csv(path or config.ALERTS_CSV)
    return df[df["status"] == "pending"]


def format_alert_info(row) -> str:
    return f"""
    Required Info
    Alert ID = {row["alert_id"]}
    Email = {row["user_email"]}
    Time = {row["timestamp"]}
    IP = {row["ip"]}
    MFA USED = {row["mfa_used"]}
    Resource Accessed = {row["resource_accessed"]}
    Raw Description = {row["raw_description"]}
    """


def run_alert(supervisor, row):
    """Kick off triage for one alert. Returns the graph result, which may
    contain "__interrupt__" if the agent wants to dismiss and needs approval."""
    thread_config = {"configurable": {"thread_id": row["alert_id"]}}
    return supervisor.invoke(
        {"messages": [{"role": "user", "content": format_alert_info(row)}]},
        config=thread_config,
    )


def resume_alert(supervisor, alert_id, approved: bool):
    """Resume an interrupted alert after a human approve/reject decision."""
    thread_config = {"configurable": {"thread_id": alert_id}}
    decision = {"type": "approve"} if approved else {"type": "reject", "message": "Rejected by human reviewer"}
    return supervisor.invoke(Command(resume={"decisions": [decision]}), config=thread_config)


def process_alerts(path=None):
    """CLI entrypoint: process every pending alert, prompting on the terminal
    whenever the agent needs human approval before dismissing one."""
    df = pd.read_csv(path or config.ALERTS_CSV)
    supervisor = supervisor_agent()
    pending = df[df["status"] == "pending"]
    for _, row in pending.iterrows():
        result = run_alert(supervisor, row)

        if "__interrupt__" in result:
            interrupt = result["__interrupt__"][0]
            print(row["alert_id"], "- needs human approval before resolving:")
            print(interrupt.value)
            answer = input("Approve this resolution? (y/n): ").strip().lower()
            result = resume_alert(supervisor, row["alert_id"], approved=(answer == "y"))

        print(row["alert_id"], "->", result["messages"][-1].content)


if __name__ == "__main__":
    process_alerts()
