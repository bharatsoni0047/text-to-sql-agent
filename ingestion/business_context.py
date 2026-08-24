# ingestion/business_context.py - the glossary, rules and notes the model must always follow
# Held in memory only: set it through the API or the Settings panel, and it lasts until the
# server restarts. That is deliberate for now - it keeps the whole file to one page.

# term -> what it means in THIS business
glossary = {}
# things the model must always or never do
rules = []
# background facts worth knowing
notes = []


# what this function does: report everything currently loaded
def summary():
  return {"glossary": dict(glossary), "rules": list(rules), "notes": list(notes),
          "total": len(glossary) + len(rules) + len(notes)}


# what this function does: add or update one glossary term
def add_glossary_term(term, meaning):
  glossary[term] = meaning


# what this function does: add one always/never rule
def add_rule(rule):
  rules.append(rule)


# what this function does: add one background note
def add_note(note):
  notes.append(note)


# what this function does: replace everything in one go, from the Settings panel
def replace(new_glossary=None, new_rules=None, new_notes=None):
  glossary.clear()
  glossary.update(new_glossary or {})
  rules[:] = new_rules or []
  notes[:] = new_notes or []
  return summary()


# what this function does: read a plain text file that a non-technical person can write
def parse_text(text):
  """Three shapes, one per line. Blank lines and lines starting with # are skipped.

      revenue = net amount after refunds, not gross
      rule: always exclude cancelled orders
      note: the financial year starts in April
  """
  new_glossary, new_rules, new_notes = {}, [], []
  for raw in text.splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
      continue
    lowered = line.lower()
    if lowered.startswith("rule:"):
      new_rules.append(line[5:].strip())
    elif lowered.startswith("note:"):
      new_notes.append(line[5:].strip())
    elif "=" in line:
      term, meaning = line.split("=", 1)
      if term.strip():
        new_glossary[term.strip()] = meaning.strip()
  return new_glossary, new_rules, new_notes


# what this function does: turn everything into one readable block for the model
def get_business_context_text():
  lines = [f"Glossary - {term}: {meaning}" for term, meaning in glossary.items()]
  lines += [f"Rule: {rule}" for rule in rules]
  lines += [f"Note: {note}" for note in notes]
  return "\n".join(lines) if lines else "No business context has been added yet."
