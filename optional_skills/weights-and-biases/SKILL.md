---
kenbun:
  mode: document
  fidelity: high
  tech_stack: [python, bash, wandb]
  discovery_required: false
---

# Weights & Biases: ML Experiment Tracking & MLOps

Track machine learning experiments, log configuration/hyperparameters, visualize metrics in real-time, launch hyperparameter sweeps, version datasets and model artifacts, and collaborate in team workspaces using Weights & Biases (`wandb`).

---

## When to Use
- Track model training runs with automatic metric logging.
- Compare training runs across different hyperparameter combinations.
- Optimize hyperparameters with automated Bayes/random/grid sweeps.
- Version models and datasets using W&B Artifacts to build clear lineage.
- Share training metrics, charts, and custom reports with a team.
- Offline experiment logging in environments with unstable internet access.

---

## Installation & Setup

```bash
# Install W&B
pip install wandb

# Login via CLI (prompts for API key)
wandb login

# Alternatively, set the API key environment variable
export WANDB_API_KEY=your_api_key_here
```

---

## Quick Start

### Basic Experiment Tracking
```python
import wandb

# Initialize a run
run = wandb.init(
    project="my-project",
    config={
        "learning_rate": 0.001,
        "epochs": 10,
        "batch_size": 32,
        "architecture": "ResNet50"
    }
)

# Training loop
for epoch in range(run.config.epochs):
    # Perform training step
    train_loss = train_epoch()
    val_loss = validate()

    # Log metrics
    wandb.log({
        "epoch": epoch,
        "train/loss": train_loss,
        "val/loss": val_loss
    })

# Mark the run as finished
wandb.finish()
```

### PyTorch Integration Example
```python
import torch
import wandb

# Initialize W&B
wandb.init(project="pytorch-demo", config={
    "lr": 0.001,
    "epochs": 10
})

config = wandb.config

# Training Loop
for epoch in range(config.epochs):
    for batch_idx, (data, target) in enumerate(train_loader):
        output = model(data)
        loss = criterion(output, target)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        # Log batches
        if batch_idx % 100 == 0:
            wandb.log({
                "loss": loss.item(),
                "epoch": epoch,
                "batch": batch_idx
            })

# Save and upload model
torch.save(model.state_dict(), "model.pth")
wandb.save("model.pth")

wandb.finish()
```

---

## Core Concepts

### 1. Projects and Runs
- **Project:** A collection of related experiments.
- **Run:** A single execution of a training script.
```python
run = wandb.init(
    project="image-classification",
    name="resnet50-experiment-1",  # Optional custom run name
    tags=["baseline", "resnet"],    # Organize runs with tags
    notes="First baseline run"      # Explanatory notes
)
print(f"Run ID: {run.id} | Run URL: {run.url}")
```

### 2. Configuration Tracking
Maintain hyperparameters in the config dictionary to fetch them programmatically:
```python
config = {
    "model": "ResNet50",
    "pretrained": True,
    "learning_rate": 0.001,
    "batch_size": 32,
    "epochs": 50
}
wandb.init(project="my-project", config=config)

# Access
lr = wandb.config.learning_rate
```

### 3. Rich Metric Logging
```python
# Log metrics with a custom step index
wandb.log({"loss": loss}, step=global_step)

# Log media (images, audio, video)
wandb.log({"examples": [wandb.Image(img) for img in images]})

# Log histograms (e.g. weights/gradients distributions)
wandb.log({"gradients": wandb.Histogram(gradients)})

# Log tables for detailed analysis
table = wandb.Table(columns=["id", "prediction", "ground_truth"])
wandb.log({"predictions": table})
```

---

## Hyperparameter Sweeps

### 1. Define Sweep Configuration
```python
sweep_config = {
    'method': 'bayes',  # options: 'bayes', 'random', 'grid'
    'metric': {
        'name': 'val/accuracy',
        'goal': 'maximize'
    },
    'parameters': {
        'learning_rate': {
            'distribution': 'log_uniform',
            'min': 1e-5,
            'max': 1e-1
        },
        'batch_size': {
            'values': [16, 32, 64, 128]
        },
        'optimizer': {
            'values': ['adam', 'sgd', 'rmsprop']
        }
    }
}

# Create sweep ID
sweep_id = wandb.sweep(sweep_config, project="my-project")
```

### 2. Define Training Function
```python
def train():
    run = wandb.init()
    # Access selected sweep config
    lr = wandb.config.learning_rate
    batch_size = wandb.config.batch_size
    
    # Train
    model = build_model(wandb.config)
    val_acc = validate(model, batch_size)
    
    wandb.log({"val/accuracy": val_acc})

# Start the sweep agent
wandb.agent(sweep_id, function=train, count=50)
```

---

## Artifacts & Lineage

### Log Datasets or Models
```python
artifact = wandb.Artifact(
    name='training-dataset',
    type='dataset',
    description='ImageNet training split',
    metadata={'size': '1.2M images', 'split': 'train'}
)
artifact.add_file('data/train.csv')
artifact.add_dir('data/images/')

# Upload
wandb.log_artifact(artifact)
```

### Retrieve and Download Artifacts
```python
run = wandb.init(project="my-project")

# Download artifact files
artifact = run.use_artifact('training-dataset:latest')
artifact_dir = artifact.download()
```

---

## Framework Integrations

### HuggingFace Transformers
```python
from transformers import Trainer, TrainingArguments

training_args = TrainingArguments(
    output_dir="./results",
    report_to="wandb",  # Automatically logs metrics to W&B
    run_name="bert-finetuning"
)

trainer = Trainer(model=model, args=training_args, ...)
trainer.train()
```

### PyTorch Lightning
```python
from pytorch_lightning import Trainer
from pytorch_lightning.loggers import WandbLogger

wandb_logger = WandbLogger(project="lightning-demo", log_model=True)
trainer = Trainer(logger=wandb_logger, max_epochs=10)
```

---

## Best Practices
1. **descriptive names:** Use run names that communicate architecture/lr config, e.g., `bert-base-lr0.001-bs32-epoch10`.
2. **Offline Logging:** If executing in a closed network, enforce offline mode:
   ```bash
   export WANDB_MODE=offline
   ```
   Sync later using:
   ```bash
   wandb sync <run_directory>
   ```
3. **Structured Grouping:** Use `group="resnet-experiments"` to organize runs within the same test suite.
