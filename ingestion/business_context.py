# ingestion/business_context.py - glossary, rules and notes the model must always follow
# kept in plain memory; edit the defaults here or add entries with the functions below

# term -> what it means in this business
glossary = {}
# things the model must always or never do
rules = []
# background facts worth knowing
notes = []

# what this function does: add or update one glossary term
def add_glossary_term(term, meaning):
  glossary[term] = meaning

# what this function does: add one always/never rule
def add_rule(rule):
  rules.append(rule)

# what this function does: add one background note
def add_note(note):
  notes.append(note)

# what this function does: turn everything into one readable text block for the model
def get_business_context_text():
  lines = [f"Glossary - {term}: {meaning}" for term, meaning in glossary.items()]
  lines += [f"Rule: {rule}" for rule in rules]
  lines += [f"Note: {note}" for note in notes]
  return "\n".join(lines) if lines else "No business context has been added yet."
