"""Diagrams as code: regenerates architecture.svg and devops-workflow.svg.

    python3 docs/diagrams/make_diagrams.py

Keeping diagrams in code means they are reviewed and versioned in git like
everything else, and can't silently drift from the Terraform.
"""

from html import escape
from pathlib import Path

OUT = Path(__file__).parent

COLORS = {
    "networking": "#8c4fff",
    "compute": "#ed7100",
    "storage": "#3f8624",
    "database": "#2e73b8",
    "integration": "#e7157b",
    "security": "#dd344c",
    "ops": "#5a6b86",
    "user": "#232f3e",
    "dev": "#24292f",
}

FONT = "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\""


class Svg:
    def __init__(self, width, height, title):
        self.w, self.h = width, height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'{FONT} role="img" aria-label="{escape(title)}">',
            "<defs>"
            '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#414d5c"/></marker>'
            '<marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#8a96a8"/></marker>'
            "</defs>",
            f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        ]

    def text(self, x, y, s, size=13, weight=400, fill="#16191f", anchor="start", italic=False):
        style = ' font-style="italic"' if italic else ""
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill}" '
            f'text-anchor="{anchor}"{style}>{escape(s)}</text>'
        )

    def group(self, x, y, w, h, label, fill, stroke, dashed=True):
        dash = ' stroke-dasharray="6 4"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="1.5"{dash}/>'
        )
        self.text(x + 14, y + 22, label, size=13, weight=600, fill=stroke)

    def box(self, x, y, w, h, title, lines=(), kind="compute", badge=None):
        color = COLORS[kind]
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="#ffffff" stroke="#c6ccd5" stroke-width="1"/>'
            f'<rect x="{x}" y="{y}" width="6" height="{h}" rx="3" fill="{color}"/>'
        )
        total = 17 + 15 * len(lines)
        ty = y + (h - total) / 2 + 13
        self.text(x + 16, ty, title, size=14, weight=650)
        for i, line in enumerate(lines):
            self.text(x + 16, ty + 18 + 15 * i, line, size=11.5, fill="#4b5563")
        if badge is not None:
            self.badge(x + w - 4, y + 4, badge)

    def badge(self, cx, cy, n):
        self.parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="11" fill="#ff9900" stroke="#ffffff" stroke-width="2"/>'
            f'<text x="{cx}" y="{cy + 4.5}" font-size="12" font-weight="700" fill="#16191f" '
            f'text-anchor="middle">{n}</text>'
        )

    def arrow(self, points, label=None, label_at=None, muted=False, dashed=False, both=False):
        color = "#8a96a8" if muted else "#414d5c"
        marker = "arrow-muted" if muted else "arrow"
        d = "M" + " L".join(f"{x},{y}" for x, y in points)
        dash = ' stroke-dasharray="5 4"' if dashed else ""
        start = f' marker-start="url(#{marker})"' if both else ""
        self.parts.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{dash}{start} '
            f'marker-end="url(#{marker})"/>'
        )
        if label:
            lx, ly = label_at or (
                (points[0][0] + points[-1][0]) / 2,
                (points[0][1] + points[-1][1]) / 2 - 6,
            )
            self.label(lx, ly, label)

    def label(self, x, y, s, anchor="middle"):
        width = 6.3 * len(s) + 10
        rx = x - width / 2 if anchor == "middle" else x - 5
        self.parts.append(
            f'<rect x="{rx}" y="{y - 12}" width="{width}" height="17" rx="4" fill="#ffffff" fill-opacity="0.92"/>'
        )
        self.text(x, y, s, size=11, fill="#414d5c", anchor=anchor, italic=True)

    def save(self, name):
        self.parts.append("</svg>")
        (OUT / name).write_text("\n".join(self.parts) + "\n")


def architecture():
    s = Svg(1280, 860, "AWS architecture for a college event registration website")
    s.text(30, 40, "Campus Event Registration — AWS Architecture", size=22, weight=700)
    s.text(
        30, 62, "Serverless: scales with traffic, multi-AZ by default, near-zero cost when idle", size=13, fill="#4b5563"
    )

    # Users
    s.box(30, 180, 170, 70, "Students", ["browser / phone"], "user")
    s.box(30, 390, 170, 70, "Organisers", ["club co-heads (admin)"], "user")

    # Global edge
    s.group(235, 88, 250, 470, "AWS global edge", "#f5f8ff", "#5b7fcf")
    s.box(255, 120, 210, 62, "Route 53", ["DNS: events.<college>.edu"], "networking", badge=1)
    s.box(255, 230, 210, 74, "CloudFront (CDN)", ["HTTPS, edge caching,", "one domain for site + API"], "networking", 2)
    s.box(255, 330, 210, 62, "AWS WAF", ["rate limit, OWASP rules"], "security", 3)
    s.box(255, 470, 210, 62, "ACM certificate", ["TLS cert for CloudFront,", "free, auto-renewed"], "security")

    # Region
    s.group(520, 88, 735, 470, "Region ap-south-1 (Mumbai)  ·  managed services span 3 Availability Zones",
            "#fff9f0", "#c7790f")
    s.box(545, 120, 210, 66, "S3 bucket (private)", ["HTML / CSS / JS", "readable only by CloudFront"], "storage", 4)
    s.box(545, 230, 210, 74, "API Gateway", ["HTTP API, throttling 429,", "JWT check on admin routes"], "networking", 5)
    s.box(545, 380, 210, 62, "Cognito", ["organiser login → JWT"], "security")
    s.box(800, 230, 200, 74, "Lambda: API", ["FastAPI in a container,", "alias 'live', auto-scales"], "compute", 6)
    s.box(1035, 120, 200, 86, "DynamoDB", ["events · registrations", "on-demand, PITR backups,", "encrypted at rest"],
          "database", 7)
    s.box(800, 380, 200, 62, "SQS queue", ["confirmation emails"], "integration", 8)
    s.box(800, 476, 200, 56, "Dead-letter queue", ["after 5 failed tries"], "integration")
    s.box(1035, 380, 200, 62, "Lambda: worker", ["sends emails in batches"], "compute", 9)
    s.box(1035, 476, 200, 56, "Amazon SES", ["email → student inbox"], "integration")

    # Flows
    s.arrow([(200, 200), (255, 158)], muted=True, dashed=True)
    s.label(214, 172, "DNS", anchor="start")
    s.arrow([(200, 222), (255, 262)], "HTTPS", label_at=(228, 232))
    s.arrow([(200, 410), (255, 290)], "HTTPS + JWT", label_at=(198, 336))
    s.arrow([(360, 304), (360, 330)], both=True, muted=True)
    s.arrow([(465, 248), (505, 248), (505, 153), (545, 153)], "/*  static", label_at=(504, 205))
    s.arrow([(465, 280), (545, 280)], "/api/*", label_at=(505, 274))
    s.arrow([(200, 435), (500, 435), (500, 411), (545, 411)], "sign in", label_at=(340, 431), muted=True)
    s.arrow([(650, 304), (650, 380)], "verify JWT", label_at=(650, 346), muted=True, dashed=True)
    s.arrow([(755, 267), (800, 267)])
    s.arrow([(900, 230), (900, 163), (1035, 163)], "1 transaction", label_at=(967, 157))
    s.text(967, 181, "seat++ & insert", size=11, fill="#414d5c", anchor="middle", italic=True)
    s.arrow([(900, 304), (900, 380)], "enqueue", label_at=(900, 346))
    s.arrow([(1000, 411), (1035, 411)])
    s.arrow([(900, 442), (900, 476)], muted=True)
    s.arrow([(1135, 442), (1135, 476)])

    # Operations band
    s.group(30, 580, 1225, 120, "Observability & security (all components)", "#f6f7f9", "#5a6b86", dashed=False)
    ops = [
        ("CloudWatch Logs", ["JSON logs, 30-day retention"]),
        ("CloudWatch Alarms", ["5xx, p95 latency, throttles,", "DLQ depth"]),
        ("X-Ray", ["per-request trace"]),
        ("SNS → email", ["pages the on-call co-head"]),
        ("IAM roles", ["least privilege per function,", "no keys in code"]),
    ]
    for i, (title, lines) in enumerate(ops):
        s.box(48 + i * 241, 614, 225, 70, title, lines, "security" if title == "IAM roles" else "ops")

    # Delivery band
    s.group(30, 718, 1225, 120, "Delivery (Task 3): everything above is created by Terraform and released by CI/CD",
            "#f6f8fa", "#24292f", dashed=False)
    dev = [
        ("GitHub", ["code + Terraform + docs"], "dev"),
        ("GitHub Actions", ["test, scan, build image"], "dev"),
        ("Amazon ECR", ["image tagged with git SHA"], "compute"),
        ("Lambda alias 'live'", ["smoke-test, then switch"], "compute"),
        ("S3 + CloudFront", ["sync site, invalidate cache"], "storage"),
    ]
    for i, (title, lines, kind) in enumerate(dev):
        x = 48 + i * 241
        s.box(x, 752, 225, 66, title, lines, kind)
        if i:
            s.arrow([(x - 16, 785), (x, 785)])

    s.save("architecture.svg")


def devops_workflow():
    s = Svg(1280, 800, "DevOps workflow from code change to monitoring")
    s.text(30, 40, "DevOps Workflow — from a code change to a monitored release", size=22, weight=700)
    s.text(30, 62, "Every change takes the same automated path. Nothing reaches students untested.", size=13,
           fill="#4b5563")

    # Lane 1: develop
    s.group(30, 85, 1220, 150, "1 · Develop (laptop)", "#f6f8fa", "#24292f", dashed=False)
    s.box(50, 125, 220, 86, "Feature branch", ["git switch -c fix-seat-count", "small, focused commits"], "dev")
    s.box(310, 125, 220, 86, "Run locally", ["docker compose up", "same image as production"], "dev")
    s.box(570, 125, 220, 86, "Test locally", ["pytest · ruff", "concurrency test"], "dev")
    s.box(830, 125, 220, 86, "Pull request", ["review by a teammate,", "CI must be green to merge"], "dev")
    s.box(1090, 125, 140, 86, "Merge", ["to main"], "dev")
    for x in (270, 530, 790, 1050):
        s.arrow([(x, 168), (x + 40, 168)])

    # Lane 2: CI
    s.group(30, 255, 1220, 150, "2 · Continuous Integration (GitHub Actions, every push & PR)", "#fff9f0", "#c7790f",
            dashed=False)
    ci = [
        ("Lint", ["ruff: style, bugs,", "security smells"]),
        ("Unit tests", ["pytest + moto (fake AWS)", "coverage ≥ 80%"]),
        ("Build image", ["docker build", "tag = git SHA"]),
        ("Container tests", ["Lambda emulator smoke test,", "Trivy CVE scan, rush test"]),
        ("Terraform check", ["fmt -check", "validate"]),
    ]
    for i, (title, lines) in enumerate(ci):
        x = 50 + i * 238
        s.box(x, 295, 218, 86, title, lines, "compute")
        if i and i < 4:
            s.arrow([(x - 20, 338), (x, 338)])
    s.text(1240, 397, "any red step = stop, nothing is deployed", size=11.5, fill="#b42318", anchor="end", italic=True)

    # Lane 3: CD
    s.group(30, 425, 1220, 150, "3 · Continuous Delivery (main only, after approval in 'production' environment)",
            "#f3faf2", "#3f8624", dashed=False)
    cd = [
        ("Assume AWS role", ["GitHub OIDC → temporary", "credentials, no stored keys"], "security"),
        ("Push to ECR", ["immutable image", ":<git SHA>"], "compute"),
        ("Publish version N", ["live alias still on N-1", "(no traffic yet)"], "compute"),
        ("Smoke test N", ["invoke /api/health", "on version N directly"], "compute"),
        ("Switch alias → N", ["sync site to S3,", "invalidate CloudFront"], "storage"),
    ]
    for i, (title, lines, kind) in enumerate(cd):
        x = 50 + i * 238
        s.box(x, 465, 218, 86, title, lines, kind)
        if i:
            s.arrow([(x - 20, 508), (x, 508)])

    # Lane 4: operate
    s.group(30, 595, 1220, 165, "4 · Operate: monitor, alert, roll back", "#f5f8ff", "#5b7fcf", dashed=False)
    s.box(50, 635, 218, 96, "Public check", ["GET /api/health returns", "the new git SHA?"], "ops")
    s.box(288, 635, 218, 96, "CloudWatch", ["JSON logs + metrics", "+ X-Ray traces", "dashboard"], "ops")
    s.box(526, 635, 218, 96, "Alarms → SNS", ["5xx, p95 latency,", "throttles, DLQ depth", "→ email on-call"], "ops")
    s.box(764, 635, 218, 96, "Roll back", ["move alias to N-1:", "seconds, no rebuild"], "security")
    s.box(1002, 635, 228, 96, "Learn", ["fix forward on a branch,", "add a test for the bug", "(blameless review)"],
          "dev")
    s.arrow([(268, 683), (288, 683)])
    s.arrow([(506, 683), (526, 683)])
    s.arrow([(744, 683), (764, 683)], muted=True, dashed=True)
    s.arrow([(982, 683), (1002, 683)])

    # Cross-lane connectors
    # (routed through the gaps between lanes and down the left margin, so
    # they never cross a lane title)
    s.arrow([(1160, 211), (1160, 245), (16, 245), (16, 338), (50, 338)], muted=True)
    s.arrow([(1002, 381), (1002, 415), (16, 415), (16, 508), (50, 508)], muted=True)
    s.arrow([(1140, 551), (1140, 585), (16, 585), (16, 683), (50, 683)], muted=True)
    s.arrow([(1116, 635), (1116, 619), (1266, 619), (1266, 100), (1180, 100), (1180, 125)], "next change",
            label_at=(1190, 623), muted=True, dashed=True)

    # IaC note
    s.label(640, 786, "Infrastructure (Terraform) is versioned in the same repo, reviewed in PRs, validated in CI, "
                      "and applied by a maintainer with `terraform plan` → `apply`.")
    s.save("devops-workflow.svg")


if __name__ == "__main__":
    architecture()
    devops_workflow()
    print("wrote", OUT / "architecture.svg", "and", OUT / "devops-workflow.svg")
