from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ToolCallLimitMiddleware,
    ModelFallbackMiddleware,
)

from soc_triage import config
from soc_triage.tools import (
    user_info,
    ip_info,
    notify_admin,
    resolve_alert,
    ip_internet_lookup,
    check_related_alerts,
)

with open(config.POLICY_MD, encoding="utf-8") as f:
    policy_info = f.read()


def _model():
    return ChatOpenAI(model=config.CHAT_MODEL, reasoning_effort=config.CHAT_REASONING_EFFORT)


def _limit_and_fallback():
    return [
        ToolCallLimitMiddleware(run_limit=config.TOOL_CALL_LIMIT),
        ModelFallbackMiddleware(config.FALLBACK_MODEL),
    ]


def user_info_agent():
    return create_agent(
        model=_model(),
        tools=[user_info],
        system_prompt="You are an amazing user analyser who get info about user and analyse the user",
        name="user-agent",
        middleware=_limit_and_fallback(),
    )


def ip_info_agent():
    return create_agent(
        model=_model(),
        tools=[ip_info],
        system_prompt="You are an amazing ip analyser who get info about ip and analyse the ip",
        name="ip-agent",
        middleware=_limit_and_fallback(),
    )


def notify_user_agent():
    return create_agent(
        model=_model(),
        tools=[notify_admin, resolve_alert],
        system_prompt=(
            "You are the notify agent. You generate an email with the final summary "
            "of the alert and send it to the admin using notify_admin. After sending "
            "the notification, you must also call resolve_alert exactly once with the "
            "alert_id, the final status (escalated, dismissed, or pending_human_review), "
            "and a resolution_notes summary of what was found and decided."
        ),
        name="notify-admin-agent",
        middleware=[
            *_limit_and_fallback(),
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "resolve_alert": {
                        "allowed_decisions": ["approve", "reject"],
                        "when": lambda request: request.tool_call["args"].get("status") == "dismissed",
                    }
                }
            ),
        ],
    )


def ip_reputation_checker_agent():
    return create_agent(
        model=_model(),
        tools=[check_related_alerts],
        name="ip-related-alert-checker",
        system_prompt="YOur task is to check the reputation of ip history to see if there is something fishy or wrong happen in past",
        middleware=_limit_and_fallback(),
    )


def ip_internet_lookup_agent():
    return create_agent(
        model=_model(),
        tools=[ip_internet_lookup],
        name="ip-internet-lookup",
        system_prompt="YOur task is to check the reputation of ip on the internet and find important finding related to it from internet",
        middleware=_limit_and_fallback(),
    )


def supervisor_agent():
    workflow = create_supervisor(
        [
            user_info_agent(),
            ip_info_agent(),
            notify_user_agent(),
            ip_reputation_checker_agent(),
            ip_internet_lookup_agent(),
        ],
        model=_model(),
        prompt=(
            "You are an amazing alert researcher. You will be given info about an alert, "
            "including its alert_id. You need to analyse that alert, fetch info about the "
            "user and ip using user-agent and ip-agent respectively, also use ip reputation checker agent "
            "to see the history of same ip with the user if there is something fishy "
            "also use ip-internet-lookup agent to find the info about ip if you can't find "
            "it in the database also you can call this agent multiple time to fetch more info from internet and finally hand off "
            "to notify-admin-agent with the alert_id and your findings so it can notify the "
            "admin and record the final status and resolution notes on the alert."
            f" Here is the company policy you should use to judge the alert: {policy_info}"
        ),
    )
    return workflow.compile(checkpointer=InMemorySaver())
