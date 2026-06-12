"""
Image transforms for training and evaluation.

Augmentations follow proposal §4.4: rotation ±20°, horizontal flip,
scale 0.9–1.1×, brightness ±0.2. Uses torchvision (no extra dependency).
"""
from torchvision import transforms

from src import config as C


IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def train_transform():
    return transforms.Compose([
        transforms.Resize((C.IMAGE_SIZE + 32, C.IMAGE_SIZE + 32)),
        transforms.RandomResizedCrop(
            C.IMAGE_SIZE,
            scale=(C.SCALE_MIN, C.SCALE_MAX),
            ratio=(0.95, 1.05),
        ),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(C.ROTATION_DEG),
        transforms.ColorJitter(brightness=C.BRIGHTNESS_JITTER,
                               contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def eval_transform():
    return transforms.Compose([
        transforms.Resize((C.IMAGE_SIZE, C.IMAGE_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
