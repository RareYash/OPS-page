import os
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw total page numbers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(
                40, 760, "Y corp. Ops — Architecture, Engineering & Concurrency Study Guide"
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(40, 752, 572, 752)

        # Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)

        footer_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(572, 26, footer_text)
        self.drawString(
            40,
            26,
            "Y corp. Confidential · High-Concurrency Operations Study Notes · Oct 2026",
        )
        self.restoreState()


def build_pdf(filename: str):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom palette
    NAVY = colors.HexColor("#1e3a8a")
    SLATE_DARK = colors.HexColor("#0f172a")
    SLATE_MID = colors.HexColor("#334155")
    BLUE_ACCENT = colors.HexColor("#2563eb")
    BG_LIGHT = colors.HexColor("#f8fafc")
    BORDER_COLOR = colors.HexColor("#e2e8f0")
    AMBER_BG = colors.HexColor("#fefce8")
    AMBER_TEXT = colors.HexColor("#854d0e")
    RED_BG = colors.HexColor("#fef2f2")
    RED_TEXT = colors.HexColor("#991b1b")
    GREEN_BG = colors.HexColor("#f0fdf4")
    GREEN_TEXT = colors.HexColor("#166534")

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=28,
        textColor=NAVY,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=SLATE_MID,
        spaceAfter=15,
    )

    h1_style = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=19,
        textColor=NAVY,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "SectionH2",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=SLATE_DARK,
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "BodyDark",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=SLATE_DARK,
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "BulletItem",
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4,
    )

    code_style = ParagraphStyle(
        "CodeBlock",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f1f5f9"),
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=6,
    )

    callout_style = ParagraphStyle(
        "CalloutText",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=13,
        textColor=SLATE_DARK,
    )

    table_header_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    table_cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=SLATE_DARK,
    )

    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        textColor=NAVY,
    )

    story = []

    # ==========================================
    # COVER / HEADER SECTION
    # ==========================================
    story.append(Paragraph("Y corp. Ops — Operations Under Pressure", title_style))
    story.append(
        Paragraph(
            "<b>Comprehensive Architecture, Concurrency Engineering & Study Guide</b><br/>"
            "An In-Depth Reference for Systems Engineers, Concurrency Researchers & Interview Prep",
            subtitle_style,
        )
    )

    story.append(HRFlowable(width="100%", thickness=2, color=NAVY, spaceAfter=12))

    # Executive Summary Card
    exec_text = (
        "<b>Executive Purpose:</b> Y corp. Ops is an enterprise mission-critical work item tracking platform "
        "specifically engineered for high-concurrency operations under extreme pressure (e.g. incident response, "
        "cyber triage, and emergency dispatch). Unlike generic project management tools, every mutation in Y corp. "
        "Ops is defended against race conditions, lost updates, duplicate network submissions, and regulatory breaches."
    )
    story.append(
        Table(
            [[Paragraph(exec_text, body_style)]],
            colWidths=[532],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
                    ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#bfdbfe")),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]
            ),
        )
    )
    story.append(Spacer(1, 12))

    # ==========================================
    # SECTION 1: THE 5 CORE PILLARS OF HIGH CONCURRENCY
    # ==========================================
    story.append(Paragraph("1. The 5 Core Concurrency & Reliability Pillars", h1_style))
    story.append(
        Paragraph(
            "When multiple incident commanders, dispatchers, or automated agents interact with the same system simultaneously, "
            "standard CRUD frameworks silently corrupt data. Y corp. Ops solves these challenges at the relational database level.",
            body_style,
        )
    )

    # Pillar A
    story.append(Paragraph("Pillar A: Atomic Claim (Eliminating Race Conditions)", h2_style))
    story.append(
        Paragraph(
            "<b>The Failure Mode:</b> Two operators simultaneously see a critical unassigned alert. Both click 'Claim'. "
            "A naive application executes <code>SELECT assignee_id FROM work_items WHERE id = 1</code>; both read <code>NULL</code>, "
            "and both execute an <code>UPDATE</code>. Both believe they own the incident, causing split execution or duplicate actions.<br/>"
            "<b>The Engineering Solution:</b> An atomic conditional write executed in a single atomic database statement:",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "UPDATE work_items<br/>"
            "SET assignee_id = :user_id, status = 'in_progress', version = version + 1<br/>"
            "WHERE id = :item_id AND assignee_id IS NULL<br/>"
            "RETURNING *;",
            code_style,
        )
    )
    story.append(
        Paragraph(
            "<b>Guarantee:</b> The database row-level lock serializes the evaluation of <code>WHERE assignee_id IS NULL</code>. "
            "Exactly one operator wins (receives HTTP 200 with the claimed item). The other receives HTTP 409 Conflict with the winner's "
            "name and identity. Verified by 20 parallel threads racing simultaneously in test suite.",
            bullet_style,
        )
    )

    # Pillar B
    story.append(Paragraph("Pillar B: Optimistic Concurrency Control (OCC) via If-Match", h2_style))
    story.append(
        Paragraph(
            "<b>The Failure Mode (Lost Updates):</b> Operator Alice opens an item at version 3. Operator Bob opens the same item at version 3. "
            "Bob changes priority to 'Critical' (writing version 4). Alice then saves her local draft. Without OCC, Alice's write silently "
            "overwrites Bob's priority change.<br/>"
            "<b>The Engineering Solution:</b> Every read response delivers a monotonic integer <code>version</code>. Every mutating request "
            "(<code>PATCH /items/{id}</code>, <code>POST /assign</code>, <code>POST /transition</code>) mandates the standard HTTP header:",
            body_style,
        )
    )
    story.append(Paragraph("If-Match: &lt;version&gt;", code_style))
    story.append(
        Paragraph(
            "• Missing header returns <b>HTTP 428 Precondition Required</b>.<br/>"
            "• If the database version is higher than <code>If-Match</code>, the write aborts with <b>HTTP 409 Conflict</b>.<br/>"
            "• <b>Client-Side Draft Preservation:</b> The UI presents a Conflict Resolution Modal displaying the server's changes, "
            "preventing the operator's uncommitted work from being wiped.",
            bullet_style,
        )
    )

    # Pillar C
    story.append(Paragraph("Pillar C: Cryptographic Idempotency Engine", h2_style))
    story.append(
        Paragraph(
            "<b>The Failure Mode:</b> High network packet loss causes a mobile dispatcher's HTTP POST to hang. The dispatcher taps 'Create' "
            "three times. Or an automated proxy re-sends a failed TCP connection. Result: 3 duplicate tickets with different IDs.<br/>"
            "<b>The Engineering Solution:</b> The client sends an <code>Idempotency-Key: &lt;UUID&gt;</code> header. The server computes a SHA-256 fingerprint:",
            body_style,
        )
    )
    story.append(
        Paragraph("fingerprint = SHA-256(request.method + request.path + request.body)", code_style)
    )
    story.append(
        Paragraph(
            "• <b>Exact Match (Retry):</b> The server returns the cached HTTP status, headers, and body immediately (HTTP 201 Replay).<br/>"
            "• <b>Tampering / Mismatch:</b> Reusing a key with a altered payload returns <b>HTTP 422 Unprocessable Entity</b>.<br/>"
            "• <b>Guaranteed Single Execution:</b> Prevents duplicate financial, logistical, or triage allocations under retries.",
            bullet_style,
        )
    )

    # Pillar D
    story.append(Paragraph("Pillar D: The Transactional Outbox Pattern", h2_style))
    story.append(
        Paragraph(
            "<b>The Failure Mode (The Dual-Write Problem):</b> When an item status changes, we must notify assignees and audit systems. "
            "If an application commits to PostgreSQL and then attempts an external webhook/email: if the network dies in between, "
            "the database updated but notifications were lost forever. If we notify before committing, a rollback causes phantom alerts.<br/>"
            "<b>The Engineering Solution:</b> Both the work item update and an <code>outbox</code> row are inserted inside the "
            "<b>exact same ACID database transaction</b>. Either both persist or neither does.",
            body_style,
        )
    )
    story.append(
        Paragraph(
            "SELECT id FROM outbox<br/>"
            "WHERE status = 'pending' AND next_attempt_at &lt;= :now<br/>"
            "ORDER BY id<br/>"
            "FOR UPDATE SKIP LOCKED<br/>"
            "LIMIT :limit;",
            code_style,
        )
    )
    story.append(
        Paragraph(
            "• <b>SKIP LOCKED:</b> Multiple worker processes can run concurrently without lock contention. Each worker locks unique rows.<br/>"
            "• <b>Exponential Backoff + Jitter:</b> Retries on failure capped at 15 minutes ([5s, 10s, 20s, 40s, 60s, 900s]).<br/>"
            "• <b>Stuck Job Recovery:</b> If a worker crashes mid-processing, locks older than 60 seconds are automatically reclaimed.",
            bullet_style,
        )
    )

    # Pillar E
    story.append(
        Paragraph("Pillar E: Multi-Tenant Team RBAC & The Four-Eyes Principle", h2_style)
    )
    story.append(
        Paragraph(
            "<b>Multi-Tenant Isolation:</b> Every resource is scoped to a <code>team_id</code>. Requesting an item outside your authorized teams "
            "returns <b>HTTP 404 Not Found</b> (never 403, preventing adversarial resource enumeration).<br/>"
            "<b>Four-Eyes Principle (Separation of Duties):</b> High-risk operations require dual authorization. "
            "When an item has <code>requires_approval = True</code>, it enters <code>pending_approval</code>. "
            "<b>Policy strictly forbids self-approval:</b> Even if an operator is a Team Admin or Lead, if "
            "<code>item.assignee_id == current_user.id</code>, the approval endpoint rejects with <b>HTTP 403 Forbidden</b>. "
            "An independent peer Lead or Admin must inspect and approve the resolution.",
            body_style,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # SECTION 2: SYSTEM ARCHITECTURE & CODEBASE TOUR
    # ==========================================
    story.append(Paragraph("2. System Architecture & Codebase Tour", h1_style))
    story.append(
        Paragraph(
            "Y corp. Ops follows clean vertical separation between API handling, business policy, workflow state machines, and asynchronous processing.",
            body_style,
        )
    )

    # Architecture Table
    arch_data = [
        [
            Paragraph("Module / File", table_header_style),
            Paragraph("Component Role", table_header_style),
            Paragraph("Core Architectural Responsibility", table_header_style),
        ],
        [
            Paragraph("<code>backend/app/main.py</code>", table_cell_bold),
            Paragraph("FastAPI Engine", table_cell_style),
            Paragraph(
                "App entrypoint, request ID injection, security headers, CORS origin enforcement, error handlers.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/db.py</code>", table_cell_bold),
            Paragraph("Database Engine", table_cell_style),
            Paragraph(
                "SQLAlchemy engine, connection pool configuration (pool_size=20, max_overflow=10), request session dependency.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/models.py</code>", table_cell_bold),
            Paragraph("Relational Schema", table_cell_style),
            Paragraph(
                "Declarative models: User, Team, Membership, WorkItem, ItemEvent, Notification, Outbox, IdempotencyRecord.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/policy.py</code>", table_cell_bold),
            Paragraph("RBAC Policy", table_cell_style),
            Paragraph(
                "Authorization engine: viewer (0), member (10), lead (20), admin (30). Four-eyes principle and cross-team check.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/workflow.py</code>", table_cell_bold),
            Paragraph("State Machine", table_cell_style),
            Paragraph(
                "Finite State Machine (FSM): validates allowed state transitions and prevents illegal bypasses (e.g. open -> resolved).",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/idempotency.py</code>", table_cell_bold),
            Paragraph("Idempotency", table_cell_style),
            Paragraph(
                "Cryptographic SHA-256 payload hashing, replay cache retrieval, and conflict detection.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>backend/app/worker/</code>", table_cell_bold),
            Paragraph("Async Outbox Worker", table_cell_style),
            Paragraph(
                "Independent background daemon executing FOR UPDATE SKIP LOCKED batch polling and notification fanout.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>frontend/src/App.tsx</code>", table_cell_bold),
            Paragraph("Client Coordinator", table_cell_style),
            Paragraph(
                "URL synchronization, view routing (dashboard, items, approvals, detail), back/forward popstate handling.",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>frontend/src/pages/</code>", table_cell_bold),
            Paragraph("User Interfaces", table_cell_style),
            Paragraph(
                "LoginPage (personas), DashboardPage (SLA clocks), ItemsPage (keyset pagination), ApprovalsPage (sign-off queue), ItemDetailPage (timeline).",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>frontend/src/components/</code>", table_cell_bold),
            Paragraph("UI Building Blocks", table_cell_style),
            Paragraph(
                "Navbar (team switcher, notification drawer), Logo (Y corp. industrial cog badge), ConflictModal (OCC recovery).",
                table_cell_style,
            ),
        ],
    ]

    arch_table = Table(arch_data, colWidths=[120, 110, 302])
    arch_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ]
        )
    )
    story.append(arch_table)
    story.append(Spacer(1, 10))

    # ==========================================
    # SECTION 3: WORKFLOW FINITE STATE MACHINE (FSM)
    # ==========================================
    story.append(Paragraph("3. Finite State Machine (FSM) Transition Rules", h1_style))
    story.append(
        Paragraph(
            "Every work item status transition is strictly constrained. Arbitrary status jumps are prevented by the workflow engine:",
            body_style,
        )
    )

    fsm_data = [
        [
            Paragraph("Current State", table_header_style),
            Paragraph("Permitted Target States", table_header_style),
            Paragraph("Authorization Requirement", table_header_style),
            Paragraph("Audit & Outbox Trigger", table_header_style),
        ],
        [
            Paragraph("<code>open</code>", table_cell_bold),
            Paragraph("<code>in_progress</code> (via Claim or Assign)", table_cell_style),
            Paragraph("Member (Claim) or Lead/Admin (Assign)", table_cell_style),
            Paragraph("<code>item.claimed</code> or <code>item.assigned</code>", table_cell_style),
        ],
        [
            Paragraph("<code>in_progress</code>", table_cell_bold),
            Paragraph(
                "<code>pending_approval</code> (if required)<br/><code>resolved</code> (if no approval needed)<br/><code>open</code> (release)",
                table_cell_style,
            ),
            Paragraph("Assignee or Team Lead", table_cell_style),
            Paragraph(
                "<code>item.submitted_approval</code> or <code>item.resolved</code>",
                table_cell_style,
            ),
        ],
        [
            Paragraph("<code>pending_approval</code>", table_cell_bold),
            Paragraph(
                "<code>resolved</code> (Approve)<br/><code>in_progress</code> (Reject with comment)",
                table_cell_style,
            ),
            Paragraph("<b>Peer Lead/Admin Only (Four-Eyes Principle)</b>", table_cell_style),
            Paragraph(
                "<code>item.approved</code> or <code>item.rejected</code>", table_cell_style
            ),
        ],
        [
            Paragraph("<code>resolved</code>", table_cell_bold),
            Paragraph(
                "<code>closed</code> (Final sign-off)<br/><code>open</code> (Re-open)",
                table_cell_style,
            ),
            Paragraph("Lead or Admin", table_cell_style),
            Paragraph("<code>item.closed</code> or <code>item.reopened</code>", table_cell_style),
        ],
        [
            Paragraph("<code>closed</code>", table_cell_bold),
            Paragraph("<code>open</code> (Re-activate)", table_cell_style),
            Paragraph("Admin Only", table_cell_style),
            Paragraph("<code>item.reopened</code>", table_cell_style),
        ],
    ]

    fsm_table = Table(fsm_data, colWidths=[90, 150, 150, 142])
    fsm_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_DARK),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ]
        )
    )
    story.append(fsm_table)
    story.append(Spacer(1, 10))

    # ==========================================
    # SECTION 4: DATABASE SCHEMA & INDEXING STRATEGY
    # ==========================================
    story.append(Paragraph("4. Relational Schema & Indexing Strategy", h1_style))
    story.append(
        Paragraph(
            "• <b>Keyset Cursor Pagination Index:</b> An index on <code>(created_at DESC, id DESC)</code> enables stable $O(1)$ cursor lookups. "
            "Unlike <code>OFFSET 10000</code> (which must read and discard 10,000 disk pages), keyset pagination queries "
            "<code>WHERE (created_at, id) &lt; (:last_created_at, :last_id) ORDER BY created_at DESC, id DESC LIMIT 50</code>, "
            "navigating directly to B-Tree leaves.<br/>"
            "• <b>Append-Only Audit Log:</b> The <code>item_events</code> table records every state change with actor ID and serialized JSON payload. "
            "Database triggers strictly prevent <code>UPDATE</code> or <code>DELETE</code> operations on audit records.<br/>"
            "• <b>Full-Text Search:</b> On PostgreSQL, a generated <code>tsvector</code> column indexed with GIN enables instant stem-matching "
            "across 50,000+ incident logs with fallback prefix matching on SQLite.",
            body_style,
        )
    )

    story.append(PageBreak())

    # ==========================================
    # SECTION 5: "DID I MISS SOMETHING?" (DEEP-DIVE GOTCHAS)
    # ==========================================
    story.append(Paragraph("5. What You Might Have Missed — 10 Advanced Insights", h1_style))
    story.append(
        Paragraph(
            "Below are the critical edge cases, subtle gotchas, and architectural insights that distinguish senior systems engineers "
            "during technical reviews, architecture defenses, or interviews:",
            body_style,
        )
    )

    gotchas = [
        (
            "1. The Test Database Isolation Trap (Why dev.db was wiped)",
            "In <code>backend/tests/conftest.py</code>, the test runner defaulted to <code>settings.database_url</code>. "
            "Because development was pointing to <code>dev.db</code>, running <code>pytest</code> executed the test suite's teardown "
            "(<code>table.delete()</code>) against the active database, emptying the users table! "
            "<b>The Fix:</b> We permanently decoupled test execution by setting <code>TEST_DATABASE_URL = 'sqlite:///test.db'</code>. "
            "Always keep development and test databases strictly separated.",
        ),
        (
            "2. Monotonic Counters vs. Wall-Clock Timestamps for OCC",
            "Why use an integer <code>version = version + 1</code> instead of <code>updated_at</code> for Optimistic Concurrency Control? "
            "Because wall-clock timestamps suffer from <b>NTP clock drift, leap seconds, and precision truncation</b>. Two transactions "
            "occurring within the same millisecond could receive identical timestamps. An integer increment is mathematically monotonic and immutable.",
        ),
        (
            "3. At-Least-Once Delivery in the Outbox Requires Consumer Idempotency",
            "The Outbox worker guarantees <i>At-Least-Once</i> delivery. If a worker picks up message #42, delivers an in-app notification, "
            "and crashes before updating <code>outbox.status = 'done'</code>, the stuck job recovery will re-process message #42! "
            "Therefore, downstream consumers must use a unique <code>dedupe_key</code> on the notifications table to prevent duplicate alerts.",
        ),
        (
            "4. Cross-Team 404 vs 403 (Security Timing & Enumeration)",
            "If User Alice asks for an item belonging to Team B (which she is not a member of), returning HTTP 403 tells Alice: "
            "'This item exists, but you aren't allowed to see it.' This permits enumeration attacks. "
            "Returning <b>HTTP 404 Not Found</b> completely conceals the resource's existence from unauthorized tenants.",
        ),
        (
            "5. Constant-Time Password Hashing (Mitigating Timing Attacks)",
            "In <code>backend/app/routers/auth.py</code>, if an attacker queries for a nonexistent email, a naive system returns 'User not found' "
            "in 1 millisecond. If the user exists, hashing takes 80 milliseconds. Attackers use this timing difference to enumerate valid company emails. "
            "Y corp. Ops executes a dummy password verification on unknown emails to ensure identical computation time regardless of user existence.",
        ),
        (
            "6. Connection Pool Starvation Under High Contention",
            "Under severe concurrent load, if workers or API requests hold database transactions open while awaiting external webhooks, "
            "the SQLAlchemy connection pool (<code>pool_size=20, max_overflow=10</code>) becomes exhausted, causing HTTP 500 timeouts. "
            "Y corp. Ops enforces a strict 'Zero External I/O inside DB transactions' policy — outbox messages decouple all external fanout.",
        ),
        (
            "7. Separation of Duties Policy Bypasses",
            "What if an Admin creates an item, assigns it to themselves, and tries to approve it? "
            "Policy enforcement checks <code>item.assignee_id == user.id</code>, NOT creator ID. An operator who worked on a task can never sign off on it. "
            "Furthermore, rejecting an item requires a mandatory comment explaining the deficiencies, enforcing audit accountability.",
        ),
        (
            "8. Keyset Pagination Edge Case: Tie-Breaking by Primary Key",
            "If two items share the exact same <code>created_at</code> timestamp down to the microsecond, paginating strictly on <code>created_at</code> "
            "could skip or duplicate rows across page boundaries. Y corp. Ops uses compound keysets <code>(created_at, id)</code>: the UUID acts as "
            "an infallible tie-breaker.",
        ),
        (
            "9. Mass Assignment Attack Defense via Explicit Pydantic Schemas",
            "In poorly designed APIs, sending <code>{'status': 'closed', 'version': 99}</code> in a PATCH request directly modifies internal columns. "
            "Y corp. Ops isolates mutating payloads into strict Pydantic schemas (<code>ItemUpdate</code>) where protected fields (status, version, assignee_id) "
            "are forbidden and rejected.",
        ),
        (
            "10. Idempotency Key Expiry and Cache Invalidation",
            "Idempotency records cannot grow unbounded. In enterprise production, an automated cron cleans keys older than 24-48 hours. "
            "Retrying an action after 48 hours is treated as a deliberate new action rather than a network retry.",
        ),
    ]

    for title, desc in gotchas:
        g_story = []
        g_story.append(Paragraph(f"<b>{title}</b>", h2_style))
        g_story.append(Paragraph(desc, body_style))
        story.append(KeepTogether(g_story))
        story.append(Spacer(1, 4))

    story.append(PageBreak())

    # ==========================================
    # SECTION 6: TEST SUITE & DEMO PERSONAS
    # ==========================================
    story.append(Paragraph("6. Test Suite Matrix & Demo Personas", h1_style))
    story.append(
        Paragraph(
            "All 30 backend automated tests pass with 100% assertions across concurrency, workflow FSM, idempotency, and authorization:",
            body_style,
        )
    )

    test_data = [
        [
            Paragraph("Test Module", table_header_style),
            Paragraph("Tests", table_header_style),
            Paragraph("Concurrency & Reliability Guarantees Verified", table_header_style),
            Paragraph("Status", table_header_style),
        ],
        [
            Paragraph("<code>test_concurrency.py</code>", table_cell_bold),
            Paragraph("4", table_cell_style),
            Paragraph(
                "20 parallel threads racing for atomic claim; stale If-Match updates rejected with 409; missing header returns 428.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_idempotency.py</code>", table_cell_bold),
            Paragraph("3", table_cell_style),
            Paragraph(
                "Replays cached 201 response on identical key; returns 422 on payload tampering; rejects missing key.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_workflow.py</code>", table_cell_bold),
            Paragraph("5", table_cell_style),
            Paragraph(
                "Enforces Four-Eyes principle (no self-approval); requires rejection comments; blocks illegal status jumps.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_outbox.py</code>", table_cell_bold),
            Paragraph("3", table_cell_style),
            Paragraph(
                "SKIP LOCKED polling; notification deduplication; automatic recovery of stuck locks older than 60s.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_permissions.py</code>", table_cell_bold),
            Paragraph("4", table_cell_style),
            Paragraph(
                "Cross-team 404 isolation; viewer strictly read-only; members cannot assign work; leads can assign.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_items.py</code>", table_cell_bold),
            Paragraph("5", table_cell_style),
            Paragraph(
                "Keyset cursor pagination; malformed cursor handling; limit caps; mass assignment protection; field lengths.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_events.py</code>", table_cell_bold),
            Paragraph("2", table_cell_style),
            Paragraph(
                "Append-only triggers preventing UPDATE and DELETE on audit log; verifies every mutation generates an event.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
        [
            Paragraph("<code>test_auth.py</code>", table_cell_bold),
            Paragraph("4", table_cell_style),
            Paragraph(
                "Timing attack resistance (constant-time response); login/logout flow; inactive user rejection; expired sessions.",
                table_cell_style,
            ),
            Paragraph("<b>PASSED</b>", table_cell_bold),
        ],
    ]

    test_table = Table(test_data, colWidths=[120, 45, 315, 52])
    test_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ]
        )
    )
    story.append(test_table)
    story.append(Spacer(1, 12))

    # Persona Table
    story.append(Paragraph("Demo Account Matrix (All passwords: <code>password123</code>)", h2_style))
    persona_data = [
        [
            Paragraph("Email", table_header_style),
            Paragraph("Operator Name", table_header_style),
            Paragraph("Team: Platform", table_header_style),
            Paragraph("Team: Product", table_header_style),
            Paragraph("Team: Security", table_header_style),
        ],
        [
            Paragraph("<code>alice@example.com</code>", table_cell_style),
            Paragraph("Alice Chen", table_cell_bold),
            Paragraph("<b>Admin</b>", table_cell_style),
            Paragraph("Viewer", table_cell_style),
            Paragraph("—", table_cell_style),
        ],
        [
            Paragraph("<code>bob@example.com</code>", table_cell_style),
            Paragraph("Bob Patel", table_cell_bold),
            Paragraph("<b>Lead</b>", table_cell_style),
            Paragraph("—", table_cell_style),
            Paragraph("Member", table_cell_style),
        ],
        [
            Paragraph("<code>charlie@example.com</code>", table_cell_style),
            Paragraph("Charlie Kim", table_cell_bold),
            Paragraph("Member", table_cell_style),
            Paragraph("Member", table_cell_style),
            Paragraph("—", table_cell_style),
        ],
        [
            Paragraph("<code>diana@example.com</code>", table_cell_style),
            Paragraph("Diana Müller", table_cell_bold),
            Paragraph("—", table_cell_style),
            Paragraph("<b>Admin</b>", table_cell_style),
            Paragraph("<b>Lead</b>", table_cell_style),
        ],
        [
            Paragraph("<code>ethan@example.com</code>", table_cell_style),
            Paragraph("Ethan Osei", table_cell_bold),
            Paragraph("—", table_cell_style),
            Paragraph("Member", table_cell_style),
            Paragraph("—", table_cell_style),
        ],
        [
            Paragraph("<code>faye@example.com</code>", table_cell_style),
            Paragraph("Faye Nakamura", table_cell_bold),
            Paragraph("Member", table_cell_style),
            Paragraph("<b>Lead</b>", table_cell_style),
            Paragraph("—", table_cell_style),
        ],
        [
            Paragraph("<code>george@example.com</code>", table_cell_style),
            Paragraph("George Torres", table_cell_bold),
            Paragraph("Viewer", table_cell_style),
            Paragraph("—", table_cell_style),
            Paragraph("<b>Admin</b>", table_cell_style),
        ],
        [
            Paragraph("<code>hana@example.com</code>", table_cell_style),
            Paragraph("Hana Al-Rashid", table_cell_bold),
            Paragraph("—", table_cell_style),
            Paragraph("Member", table_cell_style),
            Paragraph("Member", table_cell_style),
        ],
    ]

    persona_table = Table(persona_data, colWidths=[140, 110, 95, 95, 92])
    persona_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), SLATE_DARK),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, BG_LIGHT]),
            ]
        )
    )
    story.append(persona_table)
    story.append(Spacer(1, 14))

    # ==========================================
    # SECTION 7: QUICK OPERATIONAL COMMAND REFERENCE
    # ==========================================
    story.append(Paragraph("7. Operational Command Cheat Sheet", h1_style))
    story.append(
        Paragraph(
            "<b>Start Backend API Server:</b><br/>"
            "<code>d:\\project\\.venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000</code><br/><br/>"
            "<b>Start Asynchronous Outbox Worker:</b><br/>"
            "<code>d:\\project\\.venv\\Scripts\\python.exe -m app.worker.outbox_worker</code><br/><br/>"
            "<b>Start Frontend Web Client:</b><br/>"
            "<code>cd frontend && npm run dev</code> (Available at http://localhost:5173)<br/><br/>"
            "<b>Run Complete Test Suite:</b><br/>"
            "<code>d:\\project\\.venv\\Scripts\\python.exe -m pytest tests/ -v</code><br/><br/>"
            "<b>Run Type Checks & Linters:</b><br/>"
            "<code>mypy app --ignore-missing-imports && ruff check . && npm run type-check</code><br/><br/>"
            "<b>Re-seed Database (Standard 20 Items or Large 50,000 Items):</b><br/>"
            "<code>python -m app.seed</code> &nbsp;&nbsp;|&nbsp;&nbsp; <code>python -m app.seed --large</code>",
            code_style,
        )
    )

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated PDF: {filename}")


if __name__ == "__main__":
    out_path = sys.argv[1] if len(sys.argv) > 1 else "Y_Corp_Ops_Study_Guide.pdf"
    build_pdf(out_path)
