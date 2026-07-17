# Chapter 1: Foundations of LLM Inference

A large language model turns text into numbers before it can reason about
anything. Each chunk of text is first split into a **token**, the smallest unit
the model consumes. Every token is then mapped to an **embedding**, a dense
vector that captures its meaning in a high-dimensional space.

When a user sends a request, the text they write is called a **prompt**. The
process of running the model over that prompt to produce an answer is called
**inference**. The time between sending the prompt and receiving the first
response is the **latency** that users feel directly.

A minimal inference call looks like this:

```python
def generate(prompt: str, model) -> str:
    tokens = model.tokenize(prompt)      # split prompt into tokens
    embeddings = model.embed(tokens)     # map each token to an embedding
    output = model.forward(embeddings)   # run inference
    return model.detokenize(output)
```

Two numbers dominate the user experience. First, the number of tokens in the
prompt, because a longer prompt costs more compute. Second, the latency of the
first token, because a slow first token makes the whole system feel sluggish.
Throughout this book we keep returning to these ideas: token, embedding, prompt,
inference, and latency. Getting their definitions right now will save confusion
later.
