# Chapter 4: Fine-tuning and Deployment

A general model rarely fits a specific product out of the box. The usual fix is
**fine-tuning**: continuing to train the model on a smaller, task-specific
dataset so it adapts to your domain while keeping its general ability.

Fine-tuning changes how the model turns a **prompt** into an answer, but it does
not change the basic pipeline: text becomes a **token**, each token becomes an
**embedding**, and **inference** produces the result. What changes is the
weights the model learned.

```python
def fine_tune(model, dataset):
    for prompt, target in dataset:
        loss = model.loss(prompt, target)   # compare output to target
        model.update(loss)                  # adjust weights
    return model
```

After fine-tuning comes **deployment**: packaging the model behind an API so real
users can send a prompt and get an answer. Here the earlier concerns return with
full force. Latency must stay low, throughput must stay high, and the KV cache
and batching from the previous chapter do the heavy lifting.

The full journey — token, embedding, prompt, inference, latency, fine-tuning,
and deployment — is now complete. A model that was once a research artifact has
become a service that people can actually use.
