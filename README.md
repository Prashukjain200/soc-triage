# Security Alert Triage

A multi-agent SOC triage system built with LangGraph. Given a queue of pending
security alerts, a supervisor agent delegates to specialist sub-agents (user
lookup, IP reputation, related-alert correlation, internet lookup) to
investigate each one, then hands off to a notifier agent that emails/pages
the admin and records a final resolution — pausing for human approval
whenever it wants to dismiss an alert.

**Live demo:** _add your Streamlit Community Cloud URL here after deploying_

> The public demo processes real alerts through real LLM calls and sends a
> real push notification on dismissal — running the queue is not free and not
> silent. Treat it accordingly.

## How it works

1. Upload a CSV of pending alerts.
2. The supervisor agent investigates each one against company policy,
   checking user history, IP reputation, and related alerts.
3. If it decides to dismiss an alert, it pauses and asks a human reviewer to
   approve or reject that specific resolution before continuing.
4. Every alert's final status and reasoning is written back to the CSV.

## Stack

LangChain · LangGraph (`create_supervisor`, human-in-the-loop middleware) · OpenAI · Streamlit

## Running locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -e .
pip install -r requirements.txt
cp .env.example .env            # fill in OPENAI_API_KEY, SERPER_API_KEY, PUSHOVER_*
streamlit run src/soc_triage/app.py
```
