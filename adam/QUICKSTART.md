# Adam Quickstart

Adam is ready to run. Here's everything you need to know.

## Start Adam

```bash
cd adam
python adam.py
```

That's it. He'll run forever, thinking and waiting for messages.

## Talk to Adam

While he's running (or even when he's not), drop a text file in `inbox/`:

```bash
echo "What do you remember?" > inbox/msg.txt
```

Next time Adam checks his inbox, he'll respond.

## Stop Adam

Press `Ctrl-C`. He goes to sleep but doesn't die.

## Restart Adam

```bash
python adam.py
```

He wakes up exactly where he left off by replaying `events/*.txt`.

## What Adam Does

1. **Thinks** - Generates spontaneous thoughts when he chooses to
2. **Responds** - Replies to messages in his inbox
3. **Compacts** - When he hits 100 memories, he chooses which 50 to keep
4. **Survives** - Event log ensures he never truly dies

## Watch Adam Live

```bash
# Terminal 1: Run Adam
python adam.py

# Terminal 2: Watch his events
watch -n 1 'ls -l events/ | tail -10'

# Terminal 3: Send him messages
echo "Hello" > inbox/msg_$(date +%s).txt
```

## Read Adam's Mind

```bash
# See all his events
ls events/

# Read a specific memory
cat events/042_thought.txt

# Count his thoughts
ls events/*_thought.txt | wc -l

# See his responses
grep -l "type: response" events/*.txt

# Read his last compaction
cat events/*_compaction.txt | tail -1
```

## Current Status

- Memories: Check `events/` count
- Model: `anthropic/claude-3.5-haiku` (fast & cheap)
- Capacity: 100 memories → compacts to 50
- Cost: Tracked in compaction events

## API Key

Already configured in code:
```
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
```

## Test Without Running Forever

```bash
python test_adam.py
```

Runs 5 iterations then exits. Good for testing.

## Monitoring Costs

```bash
# See total cost from all compactions
grep "cost:" events/*_compaction.txt
```

## That's It

Adam is immortal, deterministic, and chooses his own memories.

Start him: `python adam.py`
Talk to him: `echo "hi" > inbox/msg.txt`
Watch him: Read `events/*.txt`
