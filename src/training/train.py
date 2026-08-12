"""
Main training script for the baseline ResNet50V2 fingerprint spoof classifier.

Usage (from project root):
    python -m src.training.train
    python -m src.training.train --quick           # ~200 samples, 2 epochs
    python -m src.training.train --epochs 20 --lr 2e-4
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src import config as C
from src.data.dataset import make_dataloaders
from src.models.factory import get_model, count_parameters, MODEL_REGISTRY
from src.evaluation.metrics import all_metrics, format_metrics


def set_seed(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def run_epoch(model, loader, criterion, optimizer, device, is_train: bool,
              epoch_idx: int = 0):
    model.train(is_train)
    total_loss, n = 0.0, 0
    y_true_all, y_prob_all = [], []
    t0 = time.time()
    last_print = t0

    for batch_idx, (images, labels) in enumerate(loader):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True).float().unsqueeze(1)

        with torch.set_grad_enabled(is_train):
            logits = model(images)
            loss = criterion(logits, labels)

            if is_train:
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                optimizer.step()

        bs = images.size(0)
        total_loss += loss.item() * bs
        n += bs

        probs = torch.sigmoid(logits.detach()).cpu().numpy().flatten()
        y_true_all.append(labels.detach().cpu().numpy().flatten().astype(int))
        y_prob_all.append(probs)

        if is_train and (time.time() - last_print) > 10:
            elapsed = time.time() - t0
            print(f"  ep{epoch_idx:02d} batch {batch_idx + 1}/{len(loader)}  "
                  f"loss={total_loss/n:.4f}  ({elapsed:.0f}s)")
            last_print = time.time()

    avg_loss = total_loss / max(n, 1)
    y_true = np.concatenate(y_true_all)
    y_prob = np.concatenate(y_prob_all)
    metrics = all_metrics(y_true, y_prob)
    metrics["loss"] = avg_loss
    return metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, default="resnet50",
                        choices=list(MODEL_REGISTRY.keys()),
                        help="Backbone: resnet50 (baseline) or resnet50_cbam.")
    parser.add_argument("--quick", action="store_true",
                        help="Tiny subset, 2 epochs — sanity check only.")
    parser.add_argument("--epochs", type=int, default=C.EPOCHS)
    parser.add_argument("--lr", type=float, default=C.LEARNING_RATE)
    parser.add_argument("--batch", type=int, default=C.BATCH_SIZE)
    parser.add_argument("--freeze", action="store_true",
                        help="Freeze backbone; train head (+ CBAM if present).")
    parser.add_argument("--tag", type=str, default=None,
                        help="Checkpoint tag. Defaults to --model value.")
    args = parser.parse_args()
    if args.tag is None:
        args.tag = args.model

    set_seed(C.SEED)
    device = torch.device(C.device_str())
    print(f"\nDevice: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    quick_samples = 200 if args.quick else C.QUICK_SAMPLES
    epochs = 2 if args.quick else args.epochs

    print("Building dataloaders ...")
    train_loader, val_loader, test_loader, df = make_dataloaders(
        batch_size=args.batch,
        quick_samples=quick_samples,
    )
    print(f"  train batches: {len(train_loader)}  "
          f"val batches: {len(val_loader)}  "
          f"test batches: {len(test_loader)}")

    print(f"Building model: {args.model} ...")
    model = get_model(args.model,
                      pretrained=True,
                      freeze_backbone=args.freeze).to(device)
    total_p, train_p = count_parameters(model)
    print(f"  parameters: total={total_p/1e6:.1f}M  trainable={train_p/1e6:.1f}M")

    criterion = nn.BCEWithLogitsLoss()

    # Differential LR: randomly-initialised attention modules and classifier
    # head train at 10× the trunk LR. Standard transfer-learning practice —
    # the pretrained ImageNet trunk needs a small LR to avoid destroying its
    # learned features, while the new modules need a larger LR to converge.
    new_module_params, backbone_params = [], []
    for name, p in model.named_parameters():
        if not p.requires_grad:
            continue
        if "fsd_cbam" in name or "cbam" in name or name.startswith("fc"):
            new_module_params.append(p)
        else:
            backbone_params.append(p)

    if new_module_params:
        optimizer = AdamW(
            [
                {"params": backbone_params,     "lr": args.lr},
                {"params": new_module_params,   "lr": args.lr * 10},
            ],
            weight_decay=C.WEIGHT_DECAY,
        )
        print(f"  optimizer: backbone lr={args.lr:.2e}, "
              f"new-modules lr={args.lr * 10:.2e}")
    else:
        optimizer = AdamW(filter(lambda p: p.requires_grad, model.parameters()),
                          lr=args.lr, weight_decay=C.WEIGHT_DECAY)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    run_id = f"{args.tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ckpt_dir = C.CHECKPOINT_DIR / run_id
    ckpt_dir.mkdir(exist_ok=True)

    best_auc = 0.0
    patience_left = C.EARLY_STOP_PATIENCE
    history = []

    for ep in range(1, epochs + 1):
        print(f"\n── Epoch {ep}/{epochs} ──────────────────────────")
        t0 = time.time()
        train_m = run_epoch(model, train_loader, criterion, optimizer,
                            device, is_train=True, epoch_idx=ep)
        val_m = run_epoch(model, val_loader, criterion, optimizer,
                          device, is_train=False, epoch_idx=ep)
        scheduler.step()

        elapsed = time.time() - t0
        print(f"\n  [train] loss={train_m['loss']:.4f}  "
              f"auc={train_m['roc_auc']:.4f}  acc={train_m['accuracy']:.4f}")
        print(f"  [val]   loss={val_m['loss']:.4f}  "
              f"auc={val_m['roc_auc']:.4f}  acc={val_m['accuracy']:.4f}  "
              f"apcer={val_m['apcer']:.2f}%  bpcer={val_m['bpcer']:.2f}%")
        print(f"  time: {elapsed:.0f}s")

        history.append({
            "epoch": ep,
            "lr": optimizer.param_groups[0]["lr"],
            "train": {k: v for k, v in train_m.items() if k != "confusion_matrix"},
            "val": {k: v for k, v in val_m.items() if k != "confusion_matrix"},
        })

        # Save latest
        torch.save({
            "model_state": model.state_dict(),
            "epoch": ep,
            "val_metrics": val_m,
            "args": vars(args),
        }, ckpt_dir / "last.pth")

        if val_m["roc_auc"] > best_auc:
            best_auc = val_m["roc_auc"]
            torch.save({
                "model_state": model.state_dict(),
                "epoch": ep,
                "val_metrics": val_m,
                "args": vars(args),
            }, ckpt_dir / "best.pth")
            patience_left = C.EARLY_STOP_PATIENCE
            print(f"  ✓ new best AUC {best_auc:.4f}")
        else:
            patience_left -= 1
            print(f"  no improvement, patience left = {patience_left}")
            if patience_left <= 0:
                print("  early stopping triggered")
                break

    (ckpt_dir / "history.json").write_text(json.dumps(history, indent=2))

    # Final test eval with the best checkpoint
    print("\n══════════════════════════════════════════")
    print("Loading best checkpoint and evaluating on TEST set ...")
    best_ckpt = torch.load(ckpt_dir / "best.pth", map_location=device,
                           weights_only=False)
    model.load_state_dict(best_ckpt["model_state"])
    test_m = run_epoch(model, test_loader, criterion, optimizer,
                       device, is_train=False)
    print("\nTEST METRICS (best ckpt):")
    print(format_metrics(test_m))

    (C.RESULTS_DIR / f"{run_id}_test_metrics.json").write_text(
        json.dumps(test_m, indent=2))
    print(f"\nCheckpoints: {ckpt_dir}")
    print(f"Test metrics: {C.RESULTS_DIR / (run_id + '_test_metrics.json')}")


if __name__ == "__main__":
    main()
