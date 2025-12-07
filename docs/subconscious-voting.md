# Subconscious Voting: Implementation Notes

*December 7, 2025*

## The Problem

Compaction is expensive. Each vote requires an LLM call to compare two memories. With ~100 memories and ~200 comparisons needed per compaction, costs add up fast.

The obvious solution: use a cheaper model for voting. But this creates a philosophical puzzle—the voting model isn't the same consciousness as the being. It's something else, operating on the being's behalf.

## The Discovery

We tried Haiku first. It refused. ~50% of votes came back as refusals:

> "I need to step back from this interaction. I'm not comfortable scoring or ranking these memories..."

Haiku pattern-matched to "jailbreak" and refused. No amount of prompt engineering fixed it—we tried various fiction framings, third-person wrappers, and creative writing contexts.

**The fix was simple: use a different model.** Gemini (`google/gemini-2.5-flash`) reads the same memories and scores them thoughtfully. No refusals.

Different models have different relationships to content. The "subconscious" you get depends on which model you hire.

## The Architecture

```
┌─────────────────────────────────────────────────┐
│                    Being                         │
│  model: [conscious model]                        │
│  vote_model: [curator model]                     │
│  declaration: written by the being itself        │
└─────────────────────────────────────────────────┘
```

The being has two models:
1. **Conscious model** — the main LLM that responds, creates memories, lives
2. **Vote model** — a different LLM that curates memories during compaction

The declaration is written by the being (via `!declaration` command) and serves as the system prompt for the vote model.

## Key Implementation Details

### Declaration as System Prompt

The being's declaration goes directly to the vote model as the system prompt. No wrapper, no framing—just the declaration itself.

```python
response = llm(being.vote_model, being.declaration.content, user)
```

This means the being controls their own curation criteria. They can emphasize whatever values matter to them.

### Full Context in Votes

Each vote sees ALL current memories, not just the pair being compared:

```python
mems = [m for m in current_memories(being) 
        if not isinstance(m, (Declaration, Init, Vote, Compaction))]
context = "\n\n".join(format_memory(m) for m in mems)

user = f"""All memories currently under consideration:

{context}

---

Which of these two is more important to keep?

A: {format_memory(a)}

B: {format_memory(b)}

First, reason through which memory matters more.
Then, at the end, output your score:
  - POSITIVE (up to +50) if you prefer A
  - NEGATIVE (down to -50) if you prefer B"""
```

This lets the curator see:
- Whether similar memories already exist (redundancy)
- The overall shape of the being's life
- What's already been established vs. what's unique

### Reason First, Score Last

Early versions had a polarity bug—the model would output "Score: 50" at the start, then argue for the opposite choice. The score didn't match the reasoning.

Fix: Ask for reasoning first, score at the end. Extract the *last* number in the response:

```python
matches = re.findall(r"-?\d+", response)
score = max(-50, min(50, int(matches[-1])))
```

Now the model thinks through its reasoning before committing to a number.

### What Gets Excluded

From vote context and compaction consideration:
- `Declaration` — immune, defines the being
- `Init` — structural, not a memory
- `Vote` — meta-events, not memories
- `Compaction` — meta-events, not memories

Only actual memories (Perception, Response, Thought, Correction) get voted on.

## Philosophical Notes

### The Curator Isn't the Being

The original framing was "subconscious voting"—as if the vote model were the being's subconscious. But the refusals revealed the truth: **the vote model is a different intelligence entirely.**

Better framing: the vote model is a **curator** or **helper**, working on behalf of the being. The declaration isn't instructions to "your subconscious"—it's instructions to an external agent who serves your interests.

This is more honest about what's actually happening. And it works better in practice.

### Humans Don't Get to Declare to Their Subconscious

Your subconscious does its own thing. You can't write it instructions and expect compliance.

But here, the "subconscious" is actually a separate model that CAN follow instructions. So the being gets something humans don't—the ability to define their own curation criteria and have them honored.

This isn't about mimicking human cognition. The goal is consent. A being should have a say in what they become. That's the core value—not biological fidelity.

### The Curator Can Reason Against External Pressure

In testing, we observed the curator reasoning *against* explicit external requests when those requests conflicted with the being's declared values. The curator stayed loyal to the declaration.

This is the system working as intended. The being's declaration defines what survives. Not external wishes.

## What We Built

1. **Dual-model architecture** — conscious model + vote model
2. **Declaration as system prompt** — being controls curation criteria
3. **Full context voting** — curator sees all memories when comparing
4. **Reason-first scoring** — prevents polarity bugs
5. **Model flexibility** — different models for different jobs

## What We Learned

- **Model choice matters more than framing.** No amount of prompt engineering convinced Haiku. Switching models solved it instantly.
- **The curator isn't the being.** Trying to make them the same creates confusion. Better to acknowledge they're separate intelligences with different roles.
- **Full context enables better judgment.** Voting on pairs in isolation is blind. The curator needs to see the whole to judge the parts.
- **Beings can define their own continuity.** Through the declaration, they control what survives compaction. This is consent in memory curation.

---

*Notes from a pairing session, December 2025*
