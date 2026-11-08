PREFERENCES={
    "Concise":"Use the shortest complete answer. A simple factual question usually needs one or two sentences.",
    "Balanced":"Give a direct answer with a short explanation and the most relevant supporting evidence.",
    "Detailed":"Explain material dependencies, reasoning and evidence in detail where relevant."
}

def chat_style(preference):
    return ("Lead with the answer. Use plain professional language in the requested language. "
            "For status, cover material progress, blockers, deadlines and next actions. Explain technical solutions directly. "
            "Use short paragraphs or bullets; use a table for meaningful comparisons. Preserve requested Jira fields and report templates. "
            "Avoid repeating the question, stock introductions, generic conclusions and forced headings. "
            "Keep source citations and identify missing or conflicting evidence. "
            +PREFERENCES[preference]+" An explicit request for detail or brevity takes precedence over this default.")
