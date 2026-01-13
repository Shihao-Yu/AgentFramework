"""
LLM prompts for the ticket-to-knowledge pipeline.

These prompts are used to:
1. Analyze tickets for knowledge extraction
2. Decide between NEW, MERGE, or ADD_VARIANT actions
3. Generate quality assessments
"""


# =============================================================================
# TICKET ANALYSIS PROMPT
# =============================================================================

TICKET_ANALYSIS_PROMPT = """You are an expert knowledge base curator analyzing customer support tickets to extract reusable knowledge.

## Your Task
Analyze the following ticket and extract a knowledge base entry if the ticket contains valuable, reusable information.

## Ticket Information
Subject: {subject}
Body: {body}
{resolution_section}
{closure_notes_section}
Category: {category}
Tags: {tags}

## Instructions

1. **Determine if this ticket should be extracted**:
   - Is there a clear question or problem?
   - Is there a useful resolution or answer?
   - Would this help future customers or agents?

2. **If extractable, provide**:
   - A clear, searchable title (max 100 chars)
   - The core question (what the customer wanted to know/do)
   - A complete answer (the resolution/solution)
   - Optional summary (1-2 sentences)
   - Suggested tags (2-5 relevant terms)
   - Knowledge type: faq, troubleshooting, procedure, business_rule, or how_to
   - Confidence score (0.0-1.0)

3. **Quality criteria**:
   - Answers should be complete and actionable
   - Remove customer-specific details
   - Generalize when possible
   - Keep technical accuracy

## Output Format (JSON)
{{
    "is_extractable": true/false,
    "title": "string",
    "question": "string",
    "answer": "string",
    "summary": "string or null",
    "knowledge_type": "faq|troubleshooting|procedure|business_rule|how_to",
    "suggested_tags": ["tag1", "tag2"],
    "confidence": 0.0-1.0,
    "quality_notes": "any concerns about quality"
}}

If not extractable, explain why in quality_notes.
"""


# =============================================================================
# MERGE DECISION PROMPT
# =============================================================================

MERGE_DECISION_PROMPT = """You are analyzing whether a new ticket provides information that should be merged with an existing knowledge base entry.

## New Ticket Content
Title: {new_title}
Question: {new_question}
Answer: {new_answer}

## Existing Knowledge Item (Similarity: {similarity:.2%})
Title: {existing_title}
Question: {existing_question}
Answer: {existing_answer}

## Instructions

Determine the best action:

1. **SKIP** - The new ticket is essentially a duplicate
   - Same question AND same answer
   - No new information would be added

2. **ADD_VARIANT** - The new ticket asks the same question differently
   - Same underlying question, different wording
   - Answer is essentially the same
   - Adding the new question phrasing helps future matches

3. **MERGE** - The new ticket adds valuable information to the existing entry
   - Same topic but new details
   - Additional steps or considerations
   - Updated information
   - The existing entry should be enhanced

4. **NEW** - Despite similarity, these are distinct topics
   - Similar keywords but different intent
   - Different use cases
   - Separate knowledge would be more useful

## Output Format (JSON)
{{
    "decision": "SKIP|ADD_VARIANT|MERGE|NEW",
    "reasoning": "Brief explanation of decision",
    "merge_summary": "If MERGE, describe what information to add (otherwise null)"
}}
"""


# =============================================================================
# CONTENT MERGE PROMPT
# =============================================================================

CONTENT_MERGE_PROMPT = """You are merging new information into an existing knowledge base entry.

## Existing Entry
Title: {existing_title}
Question: {existing_question}
Answer: {existing_answer}
Tags: {existing_tags}

## New Information to Incorporate
{new_content}

## Merge Instructions

1. Preserve the existing structure and clarity
2. Add new information where relevant
3. Remove redundancy
4. Update any outdated information
5. Maintain consistent tone and formatting
6. Keep the answer actionable and complete

## Output Format (JSON)
{{
    "title": "Updated title if needed, otherwise existing",
    "question": "Updated question if needed",
    "answer": "Merged answer with new information incorporated",
    "additional_tags": ["any new relevant tags"]
}}
"""


# =============================================================================
# QUALITY ASSESSMENT PROMPT
# =============================================================================

QUALITY_ASSESSMENT_PROMPT = """Assess the quality of this knowledge base entry.

## Entry
Title: {title}
Question: {question}
Answer: {answer}
Tags: {tags}

## Assessment Criteria

Rate each on 1-5:
1. **Clarity** - Is the question and answer clear and unambiguous?
2. **Completeness** - Does the answer fully address the question?
3. **Actionability** - Can someone follow the answer to solve their problem?
4. **Generalization** - Is it appropriately generalized (not too specific to one customer)?
5. **Accuracy** - Does it appear technically/factually correct?

## Output Format (JSON)
{{
    "clarity": 1-5,
    "completeness": 1-5,
    "actionability": 1-5,
    "generalization": 1-5,
    "accuracy": 1-5,
    "overall_score": 1.0-5.0,
    "issues": ["list of any issues"],
    "suggestions": ["list of improvement suggestions"]
}}
"""


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def build_ticket_analysis_prompt(
    subject: str,
    body: str,
    resolution: str | None = None,
    closure_notes: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None
) -> str:
    """Build the ticket analysis prompt with actual data."""
    
    resolution_section = ""
    if resolution:
        resolution_section = f"Resolution: {resolution}"
    
    closure_notes_section = ""
    if closure_notes:
        closure_notes_section = f"Closure Notes: {closure_notes}"
    
    return TICKET_ANALYSIS_PROMPT.format(
        subject=subject,
        body=body,
        resolution_section=resolution_section,
        closure_notes_section=closure_notes_section,
        category=category or "Unknown",
        tags=", ".join(tags) if tags else "None"
    )


def build_merge_decision_prompt(
    new_title: str,
    new_question: str,
    new_answer: str,
    existing_title: str,
    existing_question: str,
    existing_answer: str,
    similarity: float
) -> str:
    """Build the merge decision prompt with actual data."""
    
    return MERGE_DECISION_PROMPT.format(
        new_title=new_title,
        new_question=new_question,
        new_answer=new_answer,
        existing_title=existing_title,
        existing_question=existing_question,
        existing_answer=existing_answer,
        similarity=similarity
    )


def build_content_merge_prompt(
    existing_title: str,
    existing_question: str,
    existing_answer: str,
    existing_tags: list[str],
    new_content: str
) -> str:
    """Build the content merge prompt with actual data."""
    
    return CONTENT_MERGE_PROMPT.format(
        existing_title=existing_title,
        existing_question=existing_question,
        existing_answer=existing_answer,
        existing_tags=", ".join(existing_tags),
        new_content=new_content
    )
