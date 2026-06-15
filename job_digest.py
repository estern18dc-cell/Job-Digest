import os
import json
import re
import requests
from datetime import datetime, timezone

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
RESEND_API_KEY = os.environ["RESEND_API_KEY"]

# ---------------- CONFIG: edit these ----------------
EMAIL_TO = "estern18dc@gmail.com"
EMAIL_FROM = "digest@updates.emmettjobs.com"

SEEN_FILE = "seen_postings.json"

BUCKET_NAMES = {
    "1": "Geopolitical Risk (Asia) — Strategic Advisories",
    "2": "Geopolitical Risk (Asia) — Banks",
    "3": "China / Taiwan / Nat-Sec — Top Think Tanks",
    "4": "AI Governance / Catastrophic Risk",
}

CRITERIA = """
I'm a candidate trying to transition into AI governance / catastrophic
risk policy work, but I need to build credibility and relevant
experience first. Find live job openings, fellowships, accelerators,
and expression-of-interest (EOI) forms, and sort everything into
exactly these four buckets (label each item with the bucket number):

BUCKET 1: Geopolitical Risk (Asia) — Strategic Advisories
Analyst/associate roles covering Asia (especially China, Taiwan, the
broader Indo-Pacific) at political risk advisory and consulting firms -
e.g. Eurasia Group, Control Risks, Oxford Analytica, Dragonfly, RWR
Advisory Group, Albright Stonebridge Group, McLarty Associates, The
Asia Group, and similar firms.

BUCKET 2: Geopolitical Risk (Asia) — Banks
Geopolitical / macro / sovereign risk analyst roles focused on Asia at
banks and financial institutions - e.g. JPMorgan Center for
Geopolitics, Goldman Sachs, Morgan Stanley, Citi, and similar
geopolitical research teams.

BUCKET 3: China / Taiwan / Nat-Sec — Top Think Tanks
Research analyst, research associate, or fellow roles on China,
Taiwan, or broader national security / tech competition at top think
tanks - e.g. CSET (Georgetown), CFR (China Strategy Initiative), CNAS,
CSIS (Wadhwani Center, China Power Project, Freeman Chair), RAND,
Brookings, Hudson Institute, AEI, and similar.

BUCKET 4: AI Governance / Catastrophic Risk (TOP PRIORITY)
This is the space I most want to break into, so look especially hard
for fellowships, EOI forms, and entry-to-mid-level roles - things that
help build credibility even if they're short programs, part-time, or
unpaid/stipend-based. Specifically check:
- GovAI (Centre for the Governance of AI) - U.S. AI Policy Program and
  any other fellowships / EOIs
- BlueDot Impact - AI Governance course and related programs
- MATS program (Autumn 2026 and any future cohort announcements)
- Horizon Institute for Public Service - Career Accelerator, Fellowship,
  and AI Innovation & Security Workshop
- ACONA Fellowship
- AI Futures Project - expression of interest
- MIRI Technical Governance Team
- SaferAI
- CSER (Centre for the Study of Existential Risk)
- IAPS (Institute for AI Policy and Strategy)
- FAS (Federation of American Scientists) - AI-related fellowships
- Council on Strategic Risks
- Centre for Long-Term Resilience (CLTR) - check this specifically even
  though they post rarely; anything from them is high-value
- Open Philanthropy
- Founders Pledge
- Longview Philanthropy
- Rethink Priorities
- Wisconsin Project on Nuclear Arms Control
- Encode

For all buckets, flag close adjacent organizations/programs even if not
explicitly named above. In the "reason" field, also note whether the
posting looks realistic for someone early-career / transitioning in, or
whether it's senior (still worth knowing about, but flag it).
"""
# -----------------------------------------------------


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f)


def run_search(seen_urls):
    seen_text = "\n".join(sorted(seen_urls)) if seen_urls else "(none yet)"

    prompt = f"""{CRITERIA}

TODAY'S DATE: {datetime.now(timezone.utc).strftime("%Y-%m-%d")}

Search the web for postings that are currently LIVE (open for
applications right now, accepting on a rolling basis, or with an
upcoming deadline). Do thorough searches across the organizations and
buckets above - aim to use most of your available searches so coverage
is wide, not shallow. Check careers/jobs pages directly, plus the
80,000 Hours job board, and any aggregators that cover this space.

PRIORITIES, in order:
1. NEW & FRESHLY-POSTED opportunities matter most. Strongly favor
   postings you can tell were posted or updated recently. Do not show
   me anything whose URL appears in the "already seen" list below.

ALREADY SEEN - do not return any of these URLs again:
{seen_text}

2. FIT for my actual situation. I'm transitioning into AI governance /
   catastrophic risk and need credibility-building roles. Bucket 4 is
   top priority. Roles realistic for someone early-career/transitioning
   should rank above senior roles I can't yet get.
3. URGENCY. A soon-closing deadline should rank a posting higher.

Score every posting you find from 1-10 on how strongly I should
prioritize applying (10 = drop everything and apply). Then return ONLY
the best 5-10 postings overall, sorted highest score first. Quality
over quantity - if only 3 are genuinely worth my time, return 3. If
there are many strong ones, cap at 10.

Respond with ONLY a JSON array, no markdown fences, no prose before or
after it. Each item:
{{"bucket": "1, 2, 3, or 4", "score": <int 1-10>, "title": "...",
  "org": "...", "url": "...", "deadline": "... or 'rolling'",
  "posted": "approx date posted if known, else ''",
  "reason": "one or two sentences: why it fits, whether it's realistic
  for me early-career vs senior, and why you scored it as you did"}}

If nothing new is found, return []."""

    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 8000,
            "tools": [
                {"type": "web_search_20250305", "name": "web_search", "max_uses": 20}
            ],
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=600,
    )
    response.raise_for_status()
    data = response.json()

    # Take the LAST text block - that's Claude's final answer after all searches.
    text_blocks = [b["text"] for b in data["content"] if b.get("type") == "text"]
    if not text_blocks:
        return []

    final_text = text_blocks[-1].strip()
    final_text = re.sub(r"^```(json)?|```$", "", final_text, flags=re.MULTILINE).strip()

    # Be forgiving: if Claude added stray prose, grab the outermost JSON array.
    try:
        postings = json.loads(final_text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", final_text, flags=re.DOTALL)
        if not match:
            return []
        try:
            postings = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    # Sort best-first and hard-cap at 10 as a safety net.
    postings.sort(key=lambda p: p.get("score", 0), reverse=True)
    return postings[:10]



SUBJECT_LINE = "hey emmett here are your jobs beep boop"


def email_subject():
    return SUBJECT_LINE


def row_html(p):
    score = p.get("score", "?")
    return (
        f"<li><b>[{score}/10] {p.get('title', 'Untitled')}</b> — {p.get('org', 'Unknown')}<br>"
        f"Deadline: {p.get('deadline', 'unknown')}"
        f"{' · posted ' + p['posted'] if p.get('posted') else ''}<br>"
        f"{p.get('reason', '')}<br>"
        f"<a href='{p.get('url', '')}'>View posting</a></li><br>"
    )


def send_email(postings):
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not postings:
        html = "<p>No new matching postings this run.</p>"
    else:
        sections = []
        for bucket_id in ["1", "2", "3", "4"]:
            group = [p for p in postings if str(p.get("bucket")) == bucket_id]
            if not group:
                continue
            rows = "".join(row_html(p) for p in group)
            sections.append(f"<h3>{BUCKET_NAMES[bucket_id]}</h3><ul>{rows}</ul>")

        # Catch anything Claude didn't tag with a recognized bucket
        leftovers = [p for p in postings if str(p.get("bucket")) not in BUCKET_NAMES]
        if leftovers:
            rows = "".join(row_html(p) for p in leftovers)
            sections.append(f"<h3>Other</h3><ul>{rows}</ul>")

        html = "".join(sections)

    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": EMAIL_FROM,
            "to": [EMAIL_TO],
            "subject": email_subject(),
            "html": html,
        },
        timeout=30,
    )
    if not r.ok:
        print(f"Resend error {r.status_code}: {r.text}")
    r.raise_for_status()


def send_test_email():
    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": EMAIL_FROM,
            "to": [EMAIL_TO],
            "subject": email_subject(),
            "html": (
                "<p>Your opportunity digest is set up and working. "
                "This is a one-time test email. From now on you'll get a "
                "ranked digest of the best 5-10 new opportunities every "
                "other day at 9am Eastern.</p>"
            ),
        },
        timeout=30,
    )
    if not r.ok:
        print(f"Resend error {r.status_code}: {r.text}")
    r.raise_for_status()


def main():
    first_run = not os.path.exists(SEEN_FILE)
    if first_run:
        send_test_email()

    seen = load_seen()
    postings = run_search(seen)
    send_email(postings)
    seen.update(p["url"] for p in postings if "url" in p)
    save_seen(seen)


if __name__ == "__main__":
    main()
