# Chapter 3: Optimizing Inference Latency

Once a model works, the next battle is speed. The goal is to lower **latency**
while raising **throughput**, the number of requests the system finishes per
second. These two often trade off against each other.

The most important trick is the **KV cache**. During inference the model would
otherwise recompute attention over every previous token at each step. By caching
the key and value vectors of past tokens, the model only processes the newest
token, which cuts latency dramatically for long prompts.

```python
def decode_step(new_token, kv_cache):
    q, k, v = project(new_token)         # only the new token
    kv_cache.append(k, v)                # reuse past keys and values
    return attention(q, kv_cache.keys, kv_cache.values)
```

A second trick is **batching**: grouping several prompts together so the
hardware stays busy. Larger batches raise throughput but can hurt the latency of
any single request, so serving systems tune the batch size carefully.

The lesson is that inference performance is a balance. Every token we avoid
recomputing, and every prompt we batch well, moves the system toward lower
latency and higher throughput at the same time.
