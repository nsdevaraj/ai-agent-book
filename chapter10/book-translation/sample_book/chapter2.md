# Chapter 2: The Transformer and Attention

Modern language models are built on the **transformer** architecture. Its
central idea is **attention**: instead of reading a sequence strictly left to
right, the model lets every token look at every other token and decide which
ones matter. This is why a transformer can connect a pronoun to a noun that
appeared many tokens earlier.

Attention works on the **embedding** of each token. For every token the model
computes three vectors — a query, a key, and a value — and uses them to weigh
how much each token should attend to the others.

```python
def attention(query, key, value):
    scores = query @ key.T          # similarity between tokens
    weights = softmax(scores)       # attention weights
    return weights @ value          # weighted embedding
```

Because attention compares every token with every other token, its cost grows
quickly as the prompt gets longer. This is the root cause of the latency
problems we will attack in the next chapter. Still, attention is what gives the
transformer its power: during inference, it lets the model route information
flexibly across the whole prompt rather than through a fixed pipeline.
