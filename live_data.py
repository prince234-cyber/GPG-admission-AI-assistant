import os
import re
from urllib.parse import urlparse

from openai import OpenAI


MAX_WEB_SEARCH_ATTEMPTS = int(os.getenv("MAX_WEB_SEARCH_ATTEMPTS", "2"))
WEB_MAX_RESULTS = int(os.getenv("WEB_MAX_RESULTS", "5"))
WEB_MAX_TOTAL_RESULTS = int(os.getenv("WEB_MAX_TOTAL_RESULTS", "5"))
WEB_TIMEOUT = float(os.getenv("WEB_TIMEOUT", "25"))
WEB_MODEL = os.getenv("OPENROUTER_WEB_MODEL", os.getenv("OPENROUTER_MODEL", "openrouter/free"))
if WEB_MODEL.startswith("sk-or-"):
    print("[CONFIG] OPENROUTER_WEB_MODEL contains an API key; using openrouter/free instead.")
    WEB_MODEL = "openrouter/free"

OFFICIAL_DOMAINS = [
    "sites.google.com",
    "gujdiploma.admissions.nic.in",
    "gtu.ac.in",
    "*.gujarat.gov.in",
]

# Broader fallback: still constrained to education/government domains.
RELIABLE_FALLBACK_DOMAINS = [
    *OFFICIAL_DOMAINS,
    "*.nic.in",
    "*.ac.in",
    "*.edu.in",
]


def _client():
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return None
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


def _allowed_domains(attempt):
    if attempt <= 1:
        return OFFICIAL_DOMAINS
    return RELIABLE_FALLBACK_DOMAINS


def _extract_annotations(message):
    """
    Extract web citations from OpenRouter/OpenAI-compatible
    response objects.

    Supports both SDK objects and dictionary responses.
    """

    sources = []

    # --------------------------------------------------------
    # Convert SDK object to dictionary when possible
    # --------------------------------------------------------

    data = None

    if hasattr(message, "model_dump"):

        try:
            data = message.model_dump()

        except Exception:
            data = None


    if data is None and isinstance(message, dict):

        data = message


    # --------------------------------------------------------
    # Get annotations
    # --------------------------------------------------------

    annotations = []

    if isinstance(data, dict):

        annotations = data.get(
            "annotations",
            []
        ) or []


    # Fallback to object attribute

    if not annotations:

        annotations = getattr(
            message,
            "annotations",
            []
        ) or []


    # --------------------------------------------------------
    # Extract URL citations
    # --------------------------------------------------------

    for annotation in annotations:

        if hasattr(
            annotation,
            "model_dump"
        ):

            try:
                annotation = annotation.model_dump()

            except Exception:
                continue


        if not isinstance(
            annotation,
            dict
        ):

            continue


        citation = annotation.get(
            "url_citation"
        )


        if citation is None:

            citation = annotation


        if not isinstance(
            citation,
            dict
        ):

            continue


        url = citation.get(
            "url"
        )


        title = citation.get(
            "title",
            ""
        )


        if not url:

            continue


        sources.append({

            "name":
            title or urlparse(url).netloc,

            "url":
            url

        })


    # --------------------------------------------------------
    # Stable de-duplication
    # --------------------------------------------------------

    unique = []

    seen = set()


    for source in sources:

        url = source["url"]


        if url in seen:

            continue


        seen.add(url)

        unique.append(source)


    return unique


def _strip_marker(text):
    text = text.strip()
    text = re.sub(r"^WEB_ANSWER\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def evaluate_web_results(answer, sources):
    """
    Decide whether OpenRouter returned a usable web-grounded answer.

    We require:
    1. Non-empty answer
    2. Not NOT_FOUND
    3. At least one usable source URL
    """

    if not answer:
        return False

    cleaned = answer.strip()

    if re.search(
        r"\bNOT_FOUND\b",
        cleaned,
        flags=re.IGNORECASE
    ):
        return False

    valid_sources = [
        source
        for source in sources
        if isinstance(source, dict)
        and source.get("url")
    ]

    return bool(valid_sources)


def search_gpg_online(question, attempt=1):
    """
    One bounded OpenRouter web-search request.

    The application controls the number of attempts. OpenRouter's server tool
    controls the result budget. The prompt explicitly tells the model to make
    one focused search and stop once enough evidence is available.
    """
    client = _client()
    if client is None:
        print("[SEARCH] OpenRouter API key missing.")
        return {"found": False, "answer": "", "sources": [], "error": "missing_api_key"}

    allowed_domains = _allowed_domains(attempt)

    system_prompt = """
You are the web fallback for the Government Polytechnic Gandhinagar (GPG)
admission assistant.

The local GPG PDF has already been searched and was NOT sufficient. You may
now use the supplied web-search tool ONLY for the student's question.

Rules:
- Search only for information directly related to GPG, Government Polytechnic
  Gandhinagar, GPG courses, eligibility, admission, fees, documents, merit,
  ACPDC diploma admission, departments, or studying at GPG.
- Prefer official GPG, Gujarat Government, ACPDC, GTU, NIC, AC.IN, or EDU.IN
  sources. Do not rely on blogs, social media, forums, or SEO pages when an
  official source is available.
- Make AT MOST ONE focused web search during this request.
- Do not search again because of uncertainty.
- Do not use your own memory to fill missing facts.
- If reliable evidence is not present in the search results, return exactly:
  NOT_FOUND
- If reliable evidence is present, begin with exactly:
  WEB_ANSWER
  Then answer only the student's question, concisely, using the evidence.
- Do not invent dates, fees, eligibility, seats, merit ranks, deadlines, or
  other admission facts.
- Keep the answer in the same language as the student when practical.
""".strip()

    user_prompt = f"""
Student question:
{question}

Search scope:
Government Polytechnic Gandhinagar (GPG) / GPG admission only.

This is web fallback attempt {attempt} of {MAX_WEB_SEARCH_ATTEMPTS}.
If the search does not produce reliable evidence, output NOT_FOUND.
""".strip()

    try:
        print(f"[SEARCH] OpenRouter web attempt {attempt}/{MAX_WEB_SEARCH_ATTEMPTS}")
        response = client.chat.completions.create(
            model=WEB_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=[
                {
                    "type": "openrouter:web_search",
                    "parameters": {
                        "engine": "exa",
                        "max_results": WEB_MAX_RESULTS,
                        "max_total_results": WEB_MAX_TOTAL_RESULTS,
                        "search_context_size": "medium",
                        "allowed_domains": allowed_domains,
                    },
                }
            ],
            temperature=0,
            max_tokens=700,
            timeout=WEB_TIMEOUT,
        )

        message = response.choices[0].message
        answer = (getattr(message, "content", None) or "").strip()
        sources = _extract_annotations(message)
        found = evaluate_web_results(answer, sources)

        print(
            f"[SEARCH] Reliable answer found: {'YES' if found else 'NO'} | "
            f"sources={len(sources)}"
        )

        return {
            "found": found,
            "answer": _strip_marker(answer) if found else "",
            "sources": sources,
            "error": None,
        }

    except Exception as exc:
        print("[SEARCH] OpenRouter web search error:", exc)
        return {
            "found": False,
            "answer": "",
            "sources": [],
            "error": str(exc),
        }


def get_live_information(question):
    """Backward-compatible name; now uses bounded OpenRouter web search."""
    result = search_gpg_online(question, attempt=1)
    return result.get("sources", []) if result.get("found") else []
