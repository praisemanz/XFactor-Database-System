"""'Ask the database' page: natural-language questions answered from the database via Claude."""
from __future__ import annotations

import os

from flask import Blueprint, render_template, request

bp = Blueprint("ask", __name__)

EXAMPLES = (
    "Which mentor has won the most series?",
    "What songs did One Direction perform in the live shows?",
    "Which series had the highest average viewers, and who won it?",
    "Which former contestants had the most UK number one singles?",
    "Which song was performed most often across all series?",
)


@bp.route("/ask", methods=["GET", "POST"])
def ask_page():
    answer, error = None, None
    configured = bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"))
    question = request.form.get("question", "") if request.method == "POST" else request.args.get("q", "")
    if request.method == "POST" and configured:
        import anthropic

        from xfactor.nlq.service import ClaudeClient, ask
        try:
            answer = ask(question, ClaudeClient())
        except anthropic.RateLimitError:
            error = "The language model is rate-limited right now. Try again in a minute."
        except anthropic.APIStatusError as exc:
            error = f"Language model error ({exc.status_code})."
        except anthropic.APIConnectionError:
            error = "Could not reach the language model API."
        except RuntimeError as exc:
            error = str(exc)
    return render_template("ask.html", answer=answer, error=error, question=question,
                           examples=EXAMPLES, configured=configured)
