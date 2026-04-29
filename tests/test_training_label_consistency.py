from collections import defaultdict

from projects.justbill.intents import TRAINING_DATA


def _normalize_text(text):
    return " ".join(str(text or "").lower().split())


def test_training_data_has_no_conflicting_labels_for_same_phrase():
    label_map = defaultdict(set)
    for text, label in TRAINING_DATA:
        label_map[_normalize_text(text)].add(label)

    conflicts = {text: labels for text, labels in label_map.items() if len(labels) > 1}
    assert not conflicts, f"Conflicting labels detected: {conflicts}"
